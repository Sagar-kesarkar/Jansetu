"""Short-lived transport tickets for first-party cookies across hosting domains.

Only a confirmed HttpOnly cookie can mint a ticket. The raw ticket lives in
browser memory; the database stores its hash, origin and five-minute expiry.
"""
import hashlib
import secrets
import time

from sqlalchemy import String, Float, delete
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class BrowserTicket(Base):
    __tablename__ = 'browser_tickets'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    reporter: Mapped[str] = mapped_column(String(64), index=True)
    origin: Mapped[str] = mapped_column(String(255))
    expires: Mapped[float] = mapped_column(Float, index=True)


def issue(db, reporter, origin):
    token = secrets.token_urlsafe(32)
    db.execute(delete(BrowserTicket).where(BrowserTicket.expires <= time.time()))
    db.add(BrowserTicket(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                         reporter=reporter, origin=origin, expires=time.time() + 300))
    db.commit()
    return token


def identity(db, token, origin):
    if not token or len(token) > 100 or not origin:
        return None
    row = db.get(BrowserTicket, hashlib.sha256(token.encode()).hexdigest())
    return row.reporter if row and row.expires > time.time() and row.origin == origin else None


def revoke(db, reporter):
    db.execute(delete(BrowserTicket).where(BrowserTicket.reporter == reporter))
    db.commit()
