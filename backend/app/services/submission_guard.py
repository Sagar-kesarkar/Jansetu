"""Durable anonymous quotas, exact matching and fenced submission retries.

Transactions lock one reporter only. Extraction runs without a write lock; the
pipeline reacquires it before writing and finalises cases and quota together.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import secrets
import time

from fastapi import HTTPException
from sqlalchemy import Float, Integer, String, Text, select, update, delete
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db.database import Base

browser_context: ContextVar[tuple[str, str | None] | None] = ContextVar('submission_browser', default=None)
COOKIE = 'jansetu_visitor'
RETENTION = 90 * 86400
LEASE = 300
IST = timezone(timedelta(hours=5, minutes=30))


class ReporterLock(Base):
    __tablename__ = 'submission_reporters'
    reporter: Mapped[str] = mapped_column(String(64), primary_key=True)
    touched: Mapped[float] = mapped_column(Float)
    attempt_window: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class SubmissionAttempt(Base):
    __tablename__ = 'submission_attempts'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reporter: Mapped[str] = mapped_column(String(64), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    state: Mapped[str] = mapped_column(String(16))
    lease: Mapped[float] = mapped_column(Float)
    fence: Mapped[str] = mapped_column(String(32))
    charged: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)


def digest(value: str) -> str:
    secret = get_settings().submission_secret
    if len(secret) < 32:
        raise HTTPException(503, detail={'code': 'configuration', 'message': 'Submission protection is not configured. Please try again later.'})
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def new_cookie() -> str:
    value = f'{int(time.time())}.{secrets.token_hex(24)}'
    return value + '.' + digest('cookie:' + value)


def cookie_identity(value: str | None) -> str | None:
    if not value or len(value) > 180:
        return None
    try:
        issued, random, signature = value.split('.')
        age = time.time() - int(issued)
        if not 0 <= age < RETENTION or not re.fullmatch(r'[a-f0-9]{48}', random):
            return None
        if not hmac.compare_digest(signature, digest('cookie:' + issued + '.' + random)):
            return None
        return digest('browser:' + issued + '.' + random)
    except (ValueError, TypeError):
        return None


def now_day():
    now = datetime.now(IST)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return now.date().isoformat(), reset


def quota(db, reporter, period=None):
    day, reset = period or now_day()
    records = db.scalars(select(SubmissionAttempt).where(
        SubmissionAttempt.reporter == reporter, SubmissionAttempt.day == day)).all()
    used = sum(r.charged for r in records)
    pending = sum(r.state == 'PROCESSING' and r.lease > time.time() for r in records)
    limit = max(1, get_settings().daily_submission_limit)
    return dict(limit=limit, used=used, pending=pending,
                remaining=max(0, limit-used-pending), reset_at=reset.isoformat())


def lock_reporter(db, reporter):
    # An upsert followed by UPDATE locks before any read on both supported DBs.
    dialect = db.bind.dialect.name
    if dialect == 'sqlite':
        from sqlalchemy.dialects.sqlite import insert
    elif dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        raise RuntimeError('Submission protection requires SQLite or PostgreSQL')
    db.execute(insert(ReporterLock).values(reporter=reporter, touched=time.time(), attempts=0,
        attempt_window=0).on_conflict_do_nothing(index_elements=['reporter']))
    db.execute(update(ReporterLock).where(ReporterLock.reporter == reporter).values(touched=time.time()))


def fingerprint(payload):
    fields = {k: payload.get(k) for k in ('text', 'location_text')}
    fields['language'] = payload.get('language', 'hi')
    for name, default in (('audio', 'audio/webm'), ('image', 'image/jpeg')):
        data = payload.get(name)
        fields[name] = hashlib.sha256(data).hexdigest() if data else None
        fields[name + '_mime'] = payload.get(name + '_mime', default) if data else None
    return digest('content:v1:' + json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def problem(code, message, status=409, **extra):
    raise HTTPException(status, detail=dict(code=code, message=message, **extra),
                        headers={'Retry-After': str(extra.get('retry_after', 3))} if status == 429 or code == 'processing' else None)


def reserve(db, reporter, fp, key):
    from app.db.models import CitizenRequest
    attempt_id = digest('retry:' + reporter + ':' + key)
    lock_reporter(db, reporter)
    now = time.time()
    # Fix the reservation's calendar day once under the reporter lock. A request
    # crossing midnight must not check yesterday and then charge today.
    period = now_day()
    # Retain case-linked attempts for duplicate checks, delete only old empty work.
    db.execute(delete(SubmissionAttempt).where(SubmissionAttempt.reporter == reporter,
        SubmissionAttempt.lease < now - RETENTION,
        ~SubmissionAttempt.id.in_(select(CitizenRequest.submission_guard_id).where(CitizenRequest.submission_guard_id.is_not(None)))))
    old = db.get(SubmissionAttempt, attempt_id)
    if old:
        if old.fingerprint != fp:
            problem('retry_mismatch', 'This retry belongs to different content. Start a new submission.')
        if old.state == 'DONE':
            result = json.loads(old.result)
            db.commit()
            return None, result
        if old.state == 'PROCESSING' and old.lease > now:
            problem('processing', 'Your submission is still being processed. Please retry shortly with the same message.')

    active = db.scalars(select(CitizenRequest).join(SubmissionAttempt,
        CitizenRequest.submission_guard_id == SubmissionAttempt.id).where(
        SubmissionAttempt.reporter == reporter, SubmissionAttempt.fingerprint == fp,
        CitizenRequest.status.not_in(['RESOLVED', 'REJECTED']))).all()
    if active:
        problem('duplicate', 'You already submitted this complaint. Follow the existing case below.',
            complaints=[dict(token=r.track_token, status=r.status, reason=r.triage_reason) for r in active],
            quota=quota(db, reporter, period), fingerprint=fp)
    pending = db.scalar(select(SubmissionAttempt).where(SubmissionAttempt.reporter == reporter,
        SubmissionAttempt.fingerprint == fp, SubmissionAttempt.state == 'PROCESSING', SubmissionAttempt.lease > now))
    if pending:
        problem('processing', 'This complaint is already being processed. Please wait before trying again.')
    usage = quota(db, reporter, period)
    if usage['remaining'] <= 0:
        problem('daily_limit', 'You have reached today’s submission limit. Please try again after midnight IST.',
            429, quota=usage, retry_after=max(1, int((datetime.fromisoformat(usage['reset_at']) - datetime.now(IST)).total_seconds())))
    counter = db.get(ReporterLock, reporter)
    window = int(now // 60)
    counter.attempts = counter.attempts + 1 if counter.attempt_window == window else 1
    counter.attempt_window = window
    if counter.attempts > 12:
        db.commit()
        problem('attempt_limit', 'Please wait a minute before trying again.', 429, retry_after=60)
    fence = secrets.token_hex(16)
    if old is None:
        old = SubmissionAttempt(id=attempt_id, reporter=reporter, fingerprint=fp)
        db.add(old)
    old.day = period[0]
    old.state, old.lease, old.fence, old.charged, old.result = 'PROCESSING', now + LEASE, fence, 0, None
    db.commit()
    return (attempt_id, reporter, fence), None


def fence_write(db):
    claim = db.info.get('submission_claim')
    if not claim:
        return
    attempt_id, reporter, fence = claim
    # End any read-only transaction opened by provider idempotency checks first.
    db.rollback()
    lock_reporter(db, reporter)
    record = db.get(SubmissionAttempt, attempt_id, populate_existing=True)
    if not record or record.fence != fence or record.state != 'PROCESSING' or record.lease <= time.time():
        problem('processing', 'Processing expired safely. Retry this submission.')


def persist(db):
    if db.info.get('submission_claim'):
        from app.db.models import CitizenRequest
        for row in db.new:
            if isinstance(row, CitizenRequest):
                row.submission_guard_id = db.info['submission_claim'][0]
        db.flush()
    else:
        db.commit()


def guarded_ingest(db, core, payload):
    from app.models.schemas import IntakeEnvelope
    context = browser_context.get()
    raw = payload.get('citizen_ref')
    if context:
        reporter, key = context
        # Conversational adapters still need their existing sender reference for
        # follow-up routing. It never controls the browser's quota identity.
        payload['citizen_ref'] = raw or 'browser:' + reporter
    elif raw:
        reporter = digest('sender:' + raw.strip())
        key = digest('provider-event:' + payload['message_id']) if payload.get('message_id') else None
    else:
        # Internal callers without an identity. Public intake is gated by middleware.
        return core(db, **payload)
    key = key or secrets.token_hex(16)
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{8,200}', key):
        problem('retry_key', 'Invalid submission retry identifier.', 422)
    fp = fingerprint(payload)
    claim = None
    try:
        claim, result = reserve(db, reporter, fp, key)
        if result is not None:
            result['quota'] = quota(db, reporter)
            return IntakeEnvelope.model_validate(result)
        db.info['submission_claim'] = claim
        result = core(db, **payload)
        # Clarification and provider retry returns may not have entered persistence.
        if not db.info.pop('submission_write_started', False):
            fence_write(db)
        from app.db.models import CitizenRequest
        record = db.get(SubmissionAttempt, claim[0], populate_existing=True)
        record.charged = int(db.scalar(select(CitizenRequest.id).where(CitizenRequest.submission_guard_id == claim[0]).limit(1)) is not None)
        record.state = 'DONE'
        db.flush()
        result.fingerprint = fp
        result.quota = quota(db, reporter)
        record.result = result.model_dump_json()
        db.commit()
        return result
    except Exception:
        db.rollback()
        if claim:
            db.execute(update(SubmissionAttempt).where(SubmissionAttempt.id == claim[0],
                SubmissionAttempt.fence == claim[2], SubmissionAttempt.state == 'PROCESSING').values(state='FAILED', lease=time.time()))
            db.commit()
        raise
    finally:
        db.info.pop('submission_claim', None)
        db.info.pop('submission_write_started', None)


def begin_write(db):
    fence_write(db)
    if db.info.get('submission_claim'):
        db.info['submission_write_started'] = True
