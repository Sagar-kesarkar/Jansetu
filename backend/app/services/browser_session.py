"""HTTP boundary for the anonymous browser identity; provider webhooks are separate."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db, SessionLocal
from app.services import browser_ticket
from app.services.submission_guard import COOKIE, RETENTION, browser_context, cookie_identity, new_cookie, quota

router = APIRouter()


def browser_path(path):
    return path in ('/intake/report', '/intake/text', '/intake/voice') or any(
        path == prefix + '/simulate' or path.startswith(prefix + '/sessions')
        for prefix in ('/ivr', '/api/v1/ivr'))


async def submission_boundary(request, call_next):
    if request.method == 'OPTIONS' or not browser_path(request.url.path):
        return await call_next(request)
    try:
        origin = request.headers.get('origin')
        if origin and origin not in get_settings().cors_origin_list:
            raise HTTPException(403, detail={'code': 'origin', 'message': 'This website is not allowed to submit.'})
        reporter = cookie_identity(request.cookies.get(COOKIE))
        if not reporter:
            with SessionLocal() as db:
                reporter = browser_ticket.identity(db, request.headers.get('x-submission-ticket'), origin)
        if not reporter:
            raise HTTPException(428, detail={'code': 'session_required', 'message': 'Enable site cookies, then reconnect before submitting.'})
        retry_key = request.headers.get('idempotency-key')
        if request.url.path.startswith('/intake/') and not retry_key:
            raise HTTPException(422, detail={'code': 'retry_key', 'message': 'A submission retry identifier is required.'})
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
    token = browser_context.set((reporter, retry_key))
    try:
        return await call_next(request)
    finally:
        browser_context.reset(token)


@router.get('/intake/session')
def session(request: Request, response: Response, db: Session = Depends(get_db)):
    origin = request.headers.get('origin') or request.headers.get('x-submission-origin')
    if origin and origin not in get_settings().cors_origin_list:
        raise HTTPException(403, 'Website not allowed')
    if request.headers.get('x-submission-consent') != 'required':
        raise HTTPException(428, detail={'code': 'consent_required', 'message': 'Accept required cookies before connecting.'})
    value = request.cookies.get(COOKIE)
    reporter = cookie_identity(value)
    confirmed = reporter is not None
    if not reporter:
        value = new_cookie()
        reporter = cookie_identity(value)
        settings = get_settings()
        response.set_cookie(COOKIE, value, max_age=RETENTION, httponly=True,
            secure=settings.submission_cookie_secure, samesite=settings.submission_cookie_samesite, path='/')
    response.headers['Cache-Control'] = 'no-store'
    result = {'confirmed': confirmed, 'quota': quota(db, reporter)}
    if confirmed and origin:
        result['ticket'] = browser_ticket.issue(db, reporter, origin)
    return result


@router.post('/intake/session/revoke')
def revoke(request: Request, response: Response, db: Session = Depends(get_db)):
    origin = request.headers.get('origin') or request.headers.get('x-submission-origin')
    if origin and origin not in get_settings().cors_origin_list:
        raise HTTPException(403, 'Website not allowed')
    reporter = cookie_identity(request.cookies.get(COOKIE))
    if reporter:
        browser_ticket.revoke(db, reporter)
    response.delete_cookie(COOKIE, path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {'revoked': True}
