"""Where a citizen's photograph is kept, and what that decision cost.

For most of this project's life the photograph was read and thrown away. Gemini
described the damage into `image_verification`, and the bytes were never written:
no blob column, no upload directory. That was a defensible position — a picture
of a broken culvert also contains faces, door plates, name boards and EXIF
coordinates, which is most of what constraint 5 exists to keep out.

It is retained now, deliberately, because the description alone asks an officer to
dispatch a crew on the strength of a sentence they cannot check. A photograph is
the one piece of a citizen report that is hard to fabricate, and removing it
removed the officer's only means of verification.

Four things keep the blast radius small.

**Not web-served.** The directory sits outside anything mounted statically. The
only way to the bytes is `GET /requests/{id}/photo`, the officials' console route,
so the file is behind whatever door the rest of the case is behind. Mounting a
`StaticFiles` directory would have been three lines and would have made every
photograph in the system enumerable by anyone who guessed one filename.

**Named by tracking token, not by anything about the reporter.** `JS-GDDV-TAXX.jpg`
carries a case reference and nothing else — no phone number, no citizen_ref, no
timestamp, no original filename. Phone cameras name files things like
`IMG_20260823_110815.jpg`, which is a precise capture time, and WhatsApp names
them after the sender; keeping either would have smuggled metadata into a field
nobody declared. Tokens are unguessable by construction (see
`services/tracking.py`), so the filename is also not a walkable sequence the way
`636.jpg` would have been.

**Extension from the sniffed mime type, never from the upload.** The filename the
browser sends is attacker-controlled; `../../app/main.py` is a valid one, and so is
its backslash spelling. Nothing here uses it.

**Still not part of the data model.** `image_verification` remains what the
analytics layer and the citizen-facing API see. The file is casework evidence
attached to one docket, and `purge` exists so a retention policy has something to
call — the honest statement is now "photographs are retained for casework", not
"photographs are never stored", and `docs/DPG_COMPLIANCE.md` has to say so.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)

#: Mime type to extension. Only the formats `routers/intake.py` already accepts,
#: because an extension is a claim about content and this is the one place that
#: has actually seen the bytes.
_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}

#: A stored name is `<token>.<ext>` and nothing else. Enforced on the way out as
#: well as the way in: the column is written by `store` today, but a filename that
#: reaches `resolve` from a database row is still untrusted input as far as a path
#: join is concerned.
_SAFE_NAME = re.compile(r"^[A-Z0-9-]{4,32}\.(jpg|png|webp|heic|heif)$")


def directory() -> Path:
    """The evidence directory, created on first use.

    Created lazily rather than at import: a test run that never uploads anything
    should not leave a directory behind, and on a read-only container filesystem
    an import-time mkdir would stop the whole app from booting over a feature that
    may never be exercised.
    """
    path = Path(get_settings().evidence_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def store(token: str | None, data: bytes | None, mime: str) -> str | None:
    """Write one photograph and return its filename, or None if nothing was kept.

    Returns None rather than raising on every failure mode — no token, no bytes,
    an unknown format, a read-only disk. A photograph that cannot be filed must not
    cost the citizen their report: the text is the complaint, the image is
    corroboration, and losing the second is an inconvenience while losing the first
    is a person's problem going unrecorded.
    """
    if not token or not data:
        return None

    extension = _EXTENSIONS.get(mime.split(";")[0].strip().lower())
    if extension is None:
        log.warning("Not storing photograph for %s: unsupported mime %r", token, mime)
        return None

    name = f"{token}.{extension}"
    if not _SAFE_NAME.match(name):
        # Only reachable if the token format changes without this being revisited.
        log.warning("Not storing photograph: %r is not a safe filename", name)
        return None

    try:
        (directory() / name).write_bytes(data)
    except OSError as exc:
        log.warning("Could not write photograph %s: %s", name, exc)
        return None

    log.info("Stored photograph %s (%d bytes)", name, len(data))
    return name


def resolve(name: str | None) -> Path | None:
    """A stored filename to a readable path, or None.

    Validates the name against `_SAFE_NAME` before joining, then confirms the
    resolved path is still inside the evidence directory. Both, not one: the regex
    rejects the obvious traversal, and the containment check catches whatever the
    regex did not anticipate on a filesystem with its own opinions about symlinks
    and short names. This is the cheapest possible guard on the one route in the
    app that turns a database string into a file read.
    """
    if not name or not _SAFE_NAME.match(name):
        return None
    root = Path(get_settings().evidence_dir).resolve()
    candidate = (root / name).resolve()
    if root not in candidate.parents:
        log.warning("Refusing to serve %r: resolves outside the evidence directory", name)
        return None
    return candidate if candidate.is_file() else None


def media_type(name: str) -> str:
    """The mime type a stored filename implies. Derived from the extension this
    module wrote, not from the database or the request, so a row cannot dictate a
    response Content-Type."""
    extension = name.rsplit(".", 1)[-1].lower()
    for mime, ext in _EXTENSIONS.items():
        if ext == extension:
            return mime
    return "application/octet-stream"


def purge(name: str | None) -> bool:
    """Delete one stored photograph. Returns whether a file was removed.

    Nothing calls this yet. It exists because retention is now a policy question
    this project has to be able to answer — "photographs are deleted when a case
    closes" needs a function to be true, and adding it later alongside the endpoint
    that needs it is how a rule ends up documented but unimplemented.
    """
    path = resolve(name)
    if path is None:
        return False
    try:
        path.unlink()
        return True
    except OSError as exc:
        log.warning("Could not delete photograph %s: %s", name, exc)
        return False
