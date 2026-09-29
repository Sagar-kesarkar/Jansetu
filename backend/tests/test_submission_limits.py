"""Behavioural tests against a real file-backed database and HTTP boundary."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.main import app
from app.db.database import Base
from app.db.models import CitizenRequest
from app.services import submission_guard as guard
from app.services.pipeline import ingest_submission
from app.models.schemas import Channel


@pytest.fixture
def database(tmp_path):
    engine = create_engine('sqlite:///' + (tmp_path / 'limits.db').as_posix(), connect_args={'timeout': 20})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def submit(engine, reporter, text='The road has dangerous potholes', key=None, **extra):
    token = guard.browser_context.set((reporter, key or uuid.uuid4().hex))
    try:
        with Session(engine, expire_on_commit=False) as db:
            return ingest_submission(db, text=text, language='en', location_text='Test village', channel=Channel.TEXT, **extra)
    finally:
        guard.browser_context.reset(token)


def assert_problem(code, operation):
    with pytest.raises(Exception) as error:
        operation()
    assert getattr(error.value, 'detail', {}).get('code') == code, str(error.value)
    return error.value


def test_daily_limit_and_independent_reporters(database):
    for i in range(6):
        result = submit(database, 'one', f'The road has dangerous potholes near block {i}')
        assert result.quota['remaining'] == 5-i
    assert_problem('daily_limit', lambda: submit(database, 'one', 'The water supply is broken'))
    assert submit(database, 'two').quota['remaining'] == 5


@pytest.mark.parametrize('status', ['NEW', 'ACKNOWLEDGED', 'UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS', 'NEEDS_LOCATION', 'INVALID'])
def test_nonterminal_duplicate(database, status):
    result = submit(database, 'one')
    with Session(database) as db:
        db.get(CitizenRequest, result.request_id).status = status
        db.commit()
    error = assert_problem('duplicate', lambda: submit(database, 'one'))
    assert error.detail['complaints'][0]['status'] == status
    assert error.detail['quota']['used'] == 1


@pytest.mark.parametrize('status', ['RESOLVED', 'REJECTED'])
def test_closed_allows_new_and_reopen_blocks(database, status):
    first = submit(database, 'one')
    with Session(database) as db:
        db.get(CitizenRequest, first.request_id).status = status
        db.commit()
    second = submit(database, 'one')
    assert second.request_id != first.request_id
    with Session(database) as db:
        db.get(CitizenRequest, second.request_id).status = status
        db.get(CitizenRequest, first.request_id).status = 'IN_PROGRESS'
        db.commit()
    assert_problem('duplicate', lambda: submit(database, 'one'))


def test_retry_and_key_mismatch(database):
    first = submit(database, 'one', key='retry-12345678')
    second = submit(database, 'one', key='retry-12345678')
    assert first.request_id == second.request_id
    assert second.quota['used'] == 1
    assert_problem('retry_mismatch', lambda: submit(database, 'one', text='Different road problem', key='retry-12345678'))


def test_duplicate_before_quota_and_changed_text(database):
    for i in range(6):
        submit(database, 'one', f'Road potholes {i}')
    assert_problem('duplicate', lambda: submit(database, 'one', 'Road potholes 0'))


def test_midnight_does_not_release_duplicate(database, monkeypatch):
    submit(database, 'one')
    day, reset = guard.now_day()
    monkeypatch.setattr(guard, 'now_day', lambda: (reset.date().isoformat(), reset + timedelta(days=1)))
    assert_problem('duplicate', lambda: submit(database, 'one'))
    assert submit(database, 'one', 'Different road potholes').quota['used'] == 1


def test_parallel_same_content(database):
    def run(_):
        try:
            return submit(database, 'one').request_id
        except Exception as exc:
            assert exc.detail['code'] in ('processing', 'duplicate')
            return None
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, range(6)))
    assert sum(r is not None for r in results) == 1
    with Session(database) as db:
        assert len(db.scalars(select(CitizenRequest)).all()) == 1


def test_parallel_distinct_content(database):
    def run(i):
        try:
            return submit(database, 'one', f'Road potholes {i}').request_id
        except Exception as exc:
            assert exc.detail['code'] == 'daily_limit'
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(8)))
    assert sum(r is not None for r in results) == 6


def test_expired_lease_fences_old_worker(database):
    with Session(database) as first:
        claim, _ = guard.reserve(first, 'one', 'fingerprint', 'retry-12345678')
        record = first.get(guard.SubmissionAttempt, claim[0])
        record.lease = 0
        first.commit()
        with Session(database) as second:
            replacement, _ = guard.reserve(second, 'one', 'fingerprint', 'retry-12345678')
        first.info['submission_claim'] = claim
        assert replacement[2] != claim[2]
        assert_problem('processing', lambda: guard.begin_write(first))


def test_failure_releases_capacity(database):
    token = guard.browser_context.set(('one', 'retry-12345678'))
    try:
        with Session(database) as db:
            def fail(db, **payload):
                raise RuntimeError('synthetic processing failure')
            with pytest.raises(RuntimeError):
                guard.guarded_ingest(db, fail, {'text': 'road problem'})
            assert guard.quota(db, 'one')['remaining'] == 6
    finally:
        guard.browser_context.reset(token)


def test_fingerprint_exact_content():
    original = dict(text='Road problem', location_text='Village', language='en', image=b'one')
    assert guard.fingerprint(original) == guard.fingerprint({**original, 'channel': 'voice', 'filename': 'new.jpg'})
    for change in ({'text': 'road problem'}, {'text': 'Road problem '}, {'location_text': 'Town'}, {'language': 'hi'}, {'image': b'two'}, {'audio': b'voice'}):
        assert guard.fingerprint(original) != guard.fingerprint({**original, **change})


def test_cookie_and_http_boundary():
    with TestClient(app) as browser:
        assert browser.post('/intake/text', json={'text': 'Road problem'}).status_code == 428
        first = browser.get('/intake/session', headers={'X-Submission-Consent': 'required'})
        assert first.status_code == 200
        assert first.json()['confirmed'] is False
        assert 'HttpOnly' in first.headers['set-cookie']
        assert browser.get('/intake/session', headers={'X-Submission-Consent': 'required'}).json()['confirmed'] is True
        assert browser.post('/intake/text', json={'text': 'Road problem'}).status_code == 422
        response = browser.post('/intake/text', json={'text': 'Road potholes in village', 'language': 'en', 'citizen_ref': 'spoof'}, headers={'Idempotency-Key': uuid.uuid4().hex})
        assert response.status_code == 200, response.text
        duplicate = browser.post('/intake/text', json={'text': 'Road potholes in village', 'language': 'en', 'citizen_ref': 'changed'}, headers={'Idempotency-Key': uuid.uuid4().hex})
        assert duplicate.status_code == 409, duplicate.text
        assert browser.post('/intake/text', json={'text': 'Road'}, headers={'Origin': 'https://untrusted.example'}).status_code == 403
    value = guard.new_cookie()
    assert guard.cookie_identity(value)
    assert guard.cookie_identity(value + 'x') is None


def test_multi_issue_waits_for_all_cases(database, monkeypatch):
    from app.services import pipeline
    from app.models.schemas import ExtractedSubmission, ExtractedIssue, Classification
    monkeypatch.setattr(pipeline, 'extract_submission', lambda *a, **k: ExtractedSubmission(
        classification=Classification.VALID_MULTI_ISSUE, detected_language='en', issues=[
            ExtractedIssue(title='Road', category='ROADS', summary_en='Road potholes', summary_native='Road potholes', urgency=2, confidence=.9),
            ExtractedIssue(title='Water', category='WATER_SUPPLY', summary_en='Water supply', summary_native='Water supply', urgency=2, confidence=.9)]))
    result = submit(database, 'one')
    assert len(result.requests) == 2
    assert result.quota['used'] == 1
    with Session(database) as db:
        db.get(CitizenRequest, result.requests[0].request_id).status = 'RESOLVED'
        db.commit()
    assert_problem('duplicate', lambda: submit(database, 'one'))
    with Session(database) as db:
        db.get(CitizenRequest, result.requests[1].request_id).status = 'REJECTED'
        db.commit()
    assert submit(database, 'one').quota['used'] == 2


def test_invalid_counts_and_clarification_does_not(database, monkeypatch):
    from app.services import pipeline
    from app.models.schemas import ExtractedSubmission, Classification
    monkeypatch.setattr(pipeline, 'extract_submission', lambda *a, **k: ExtractedSubmission(
        classification=Classification.INVALID_OR_SPAM, detected_language='en', triage_reason='Test invalid', issues=[]))
    result = submit(database, 'one')
    assert result.quota['used'] == 1
    assert_problem('duplicate', lambda: submit(database, 'one'))
    monkeypatch.setattr(pipeline, 'extract_submission', lambda *a, **k: ExtractedSubmission(
        classification=Classification.NEEDS_CLARIFICATION, detected_language='en', issues=[]))
    assert submit(database, 'one', 'Please help').quota['used'] == 1


def test_case_and_usage_rollback_together(database, monkeypatch):
    from app.services import pipeline
    original = pipeline._envelope
    def fail_after_flush(*a, **k):
        raise RuntimeError('lost before commit')
    monkeypatch.setattr(pipeline, '_envelope', fail_after_flush)
    with pytest.raises(RuntimeError):
        submit(database, 'one', key='same-retry-1234')
    with Session(database) as db:
        assert db.scalar(select(CitizenRequest.id)) is None
        assert guard.quota(db, 'one')['remaining'] == 6
    monkeypatch.setattr(pipeline, '_envelope', original)
    assert submit(database, 'one', key='same-retry-1234').quota['used'] == 1


def test_attempt_throttle_after_failures(database):
    for i in range(12):
        token = guard.browser_context.set(('one', f'failed-retry-{i:03}'))
        try:
            with Session(database) as db:
                def fail(*a, **k):
                    raise ValueError('Synthetic invalid input')
                with pytest.raises(ValueError):
                    guard.guarded_ingest(db, fail, {'text': f'road {i}'})
        finally:
            guard.browser_context.reset(token)
    assert_problem('attempt_limit', lambda: submit(database, 'one'))


def test_new_connection_preserves_usage(database):
    submit(database, 'one')
    url = str(database.url)
    database.dispose()
    restarted = create_engine(url)
    try:
        assert_problem('duplicate', lambda: submit(restarted, 'one'))
        assert submit(restarted, 'one', 'Another road problem').quota['used'] == 2
    finally:
        restarted.dispose()


def test_missing_secret_fails_closed(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), 'submission_secret', '')
    with TestClient(app) as browser:
        assert browser.get('/intake/session', headers={'X-Submission-Consent': 'required'}).status_code == 503


def test_voice_report_and_text_share_limit(monkeypatch):
    from app.services import pipeline
    monkeypatch.setattr(pipeline, 'transcribe', lambda *a, **k: 'Road potholes in village')
    with TestClient(app) as browser:
        browser.get('/intake/session', headers={'X-Submission-Consent': 'required'})
        for i in range(6):
            headers = {'Idempotency-Key': uuid.uuid4().hex}
            if i % 3 == 0:
                response = browser.post('/intake/voice', files={'audio': ('note.webm', f'audio{i}'.encode(), 'audio/webm')}, headers=headers)
            elif i % 3 == 1:
                response = browser.post('/intake/report', data={'text': f'Road potholes {i}', 'language': 'en', 'citizen_ref': f'fake{i}'}, headers=headers)
            else:
                response = browser.post('/intake/text', json={'text': f'Road potholes {i}', 'language': 'en', 'channel': 'ivr'}, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()['quota']['used'] == i+1
        response = browser.post('/intake/report', data={'text': 'Another water problem'}, headers={'Idempotency-Key': uuid.uuid4().hex})
        assert response.status_code == 429


def test_extraction_does_not_hold_reporter_write_lock(database, monkeypatch):
    from app.services import pipeline
    from threading import Barrier
    original = pipeline.extract_submission
    barrier = Barrier(2, timeout=10)
    def extract(*a, **k):
        barrier.wait()
        return original(*a, **k)
    monkeypatch.setattr(pipeline, 'extract_submission', extract)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda i: submit(database, 'one', f'Road issue {i}'), range(2)))
    assert len({r.request_id for r in results}) == 2


def test_migration_keeps_legacy_case(database, monkeypatch):
    from app.db import database as database_module
    from sqlalchemy import text, inspect
    # A disposable copy of the old table has no guard column.
    with database.begin() as connection:
        connection.execute(text('DROP INDEX ix_citizen_requests_submission_guard_id'))
        connection.execute(text('ALTER TABLE citizen_requests DROP COLUMN submission_guard_id'))
        connection.execute(text("INSERT INTO citizen_requests (category, urgency, raw_text, summary_en, language, channel, confidence, created_at) VALUES ('ROADS', 2, 'legacy', 'legacy', 'en', 'text', 1, '2026-09-01')"))
    monkeypatch.setattr(database_module, 'engine', database)
    database_module.init_db()
    assert 'submission_guard_id' in {c['name'] for c in inspect(database).get_columns('citizen_requests')}
    with Session(database) as db:
        assert db.scalar(select(CitizenRequest.raw_text)) == 'legacy'


def process_submit(arguments):
    url, number = arguments
    engine = create_engine(url, connect_args={'timeout': 20})
    try:
        try:
            return submit(engine, 'shared-process-reporter', f'Road problem {number}').request_id
        except Exception as exc:
            if getattr(exc, 'detail', {}).get('code') != 'daily_limit':
                raise
            return None
    finally:
        engine.dispose()


def test_daily_limit_across_processes(database):
    from concurrent.futures import ProcessPoolExecutor
    import multiprocessing
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
        results = list(pool.map(process_submit, [(str(database.url), i) for i in range(8)]))
    assert sum(result is not None for result in results) == 6


def test_consent_required_and_revocation():
    with TestClient(app) as browser:
        response = browser.get('/intake/session')
        assert response.status_code == 428
        assert 'set-cookie' not in response.headers
        assert not browser.cookies.get(guard.COOKIE)
        response = browser.get('/intake/session', headers={'X-Submission-Consent': 'required'})
        assert response.status_code == 200
        assert browser.cookies.get(guard.COOKIE)
        assert browser.post('/intake/session/revoke').status_code == 200
        assert not browser.cookies.get(guard.COOKIE)
        response = browser.post('/intake/text', json={'text': 'Road potholes'}, headers={'Idempotency-Key': uuid.uuid4().hex})
        assert response.status_code == 428


def test_reservation_crossing_midnight_charges_the_checked_day(database, monkeypatch):
    original_day, reset = guard.now_day()
    calls = []
    def changing_clock():
        calls.append(True)
        return (original_day, reset) if len(calls) == 1 else (reset.date().isoformat(), reset + timedelta(days=1))
    monkeypatch.setattr(guard, 'now_day', changing_clock)
    with Session(database) as db:
        claim, _ = guard.reserve(db, 'one', 'original-fingerprint', 'midnight-retry')
        assert db.get(guard.SubmissionAttempt, claim[0]).day == original_day
