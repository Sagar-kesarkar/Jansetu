"""Test browser: establish the same cookie/retry contract as the citizen UI.

Boundary rejection tests deliberately use the unmodified TestClient instead.
"""
from uuid import uuid4
from fastapi.testclient import TestClient


class BrowserTestClient(TestClient):
    def request(self, method, url, **kwargs):
        from app.services.browser_session import browser_path
        from app.services.submission_guard import COOKIE
        if browser_path(str(url)):
            if not self.cookies.get(COOKIE):
                response = super().request('GET', '/intake/session', headers={'X-Submission-Consent': 'required'})
                assert response.status_code == 200, response.text
            if str(url).startswith('/intake/'):
                kwargs['headers'] = {'Idempotency-Key': uuid4().hex, **(kwargs.get('headers') or {})}
        return super().request(method, url, **kwargs)
