"""Turning channel identifiers into something we are allowed to store.

Messaging channels hand us directly identifying data whether we want it or not:
the WhatsApp Cloud API delivers the sender's phone number in `messages[0].from`,
and an IVR gateway delivers the calling line. But `CitizenRequest.citizen_ref`
is documented as *opaque*, and `docs/DPG_COMPLIANCE.md` indicator 7 claims
nothing in the schema can re-identify a citizen. Both claims are only true if
the raw value never reaches the database, so this module is the choke point that
makes them true — called from `pipeline.ingest`, which every channel funnels
through.

Why HMAC rather than a plain digest: an Indian mobile number is ten digits, so
there are only ~10^10 candidates and an unsalted SHA-256 of one is recoverable
by exhaustive search in seconds. Keying the hash with a server-side secret makes
the stored digest useless to anyone who obtains the database on its own.

The ref stays *stable* for a given sender and salt, which is the only reason the
column exists: it allows duplicate-report detection and per-sender rate limiting
without knowing who the sender is.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import get_settings

# Used when no CITIZEN_REF_SALT is configured. Regenerated every process start,
# so the default posture is "unlinkable across restarts" rather than "linkable
# with a guessable key".
_EPHEMERAL_SALT = secrets.token_hex(32)

_PREFIX = "anon_"
_DIGEST_CHARS = 24  # 96 bits of the digest — collision-safe at this scale


def pseudonymise(raw: str | None) -> str | None:
    """Return a stable, non-reversible reference for a channel identifier.

    Applied unconditionally, including to values that already look opaque: a
    check for "opaque enough" would be a fragile guess, and hashing an already
    random token costs nothing.
    """
    if raw is None:
        return None

    value = raw.strip()
    if not value:
        return None

    salt = get_settings().citizen_ref_salt or _EPHEMERAL_SALT
    digest = hmac.new(salt.encode("utf-8"), value.encode("utf-8"), hashlib.sha256)
    return _PREFIX + digest.hexdigest()[:_DIGEST_CHARS]


def mint_ref() -> str:
    """A fresh reference for a channel that carries no identifier to hash.

    The web form is the case: there is no phone number, no calling line, and no
    session, so there is nothing to derive a stable handle from. Returning None
    was defensible while nothing read the column, but the officials' console has
    to be able to say which reporter a case came from and attach a reply to it,
    and "unknown" for every request filed through the demo is not a console.

    So a random token, issued per request and handed back to the citizen as a
    docket reference. Two consequences worth being straight about: a repeat filer
    on the web gets a new handle each time, because the platform genuinely does
    not know it is the same person and guessing would mean storing something that
    identifies them; and the token is the citizen's only way back to their case,
    which is a property of capability references, not a lapse.

    Deliberately the same shape as a pseudonymised handle. Nothing downstream
    should branch on how a ref was produced — both are opaque, and a format that
    advertised "this one is unlinkable" would invite exactly that branch.
    """
    return _PREFIX + secrets.token_hex(_DIGEST_CHARS // 2)
