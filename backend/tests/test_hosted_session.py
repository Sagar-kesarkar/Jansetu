"""Hosting-domain transport preserves cookie identity and revokes tickets."""
from fastapi.testclient import TestClient
from app.main import app
from app.services import browser_ticket, evidence
from app.db.database import SessionLocal

ORIGIN = 'http://localhost:5173'


def test_ticket_requires_confirmed_cookie_and_origin_and_revokes():
    with TestClient(app) as browser:
        headers = {'X-Submission-Consent': 'required', 'X-Submission-Origin': ORIGIN}
        first = browser.get('/intake/session', headers=headers).json()
        assert first['confirmed'] is False and 'ticket' not in first
        second = browser.get('/intake/session', headers=headers).json()
        ticket = second['ticket']
        with SessionLocal() as db:
            assert browser_ticket.identity(db, ticket, ORIGIN)
            assert browser_ticket.identity(db, ticket, 'https://wrong.example') is None
            row = db.get(browser_ticket.BrowserTicket, browser_ticket.hashlib.sha256(ticket.encode()).hexdigest())
            row.expires = 0
            db.commit()
            assert browser_ticket.identity(db, ticket, ORIGIN) is None
        ticket = browser.get('/intake/session', headers=headers).json()['ticket']
        with TestClient(app) as direct:
            # Ticket passes identity boundary; missing retry key is the next check.
            response = direct.post('/intake/text', headers={'Origin': ORIGIN, 'X-Submission-Ticket': ticket}, json={})
            assert response.status_code == 422
            assert response.json()['detail']['code'] == 'retry_key'
        assert browser.post('/intake/session/revoke', headers={'Origin': ORIGIN}).status_code == 200
        with SessionLocal() as db:
            assert browser_ticket.identity(db, ticket, ORIGIN) is None


def test_database_photo_survives_local_cache_loss(monkeypatch):
    monkeypatch.setattr(evidence, 'durable', lambda: True)
    name = evidence.store('JS-HOST-TEST', b'photo-test-bytes', 'image/jpeg')
    path = evidence.resolve(name)
    assert path.read_bytes() == b'photo-test-bytes'
    path.unlink()
    assert evidence.resolve(name).read_bytes() == b'photo-test-bytes'
    assert evidence.purge(name)
    assert evidence.resolve(name) is None
