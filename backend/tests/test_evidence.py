"""Photograph retention: what is kept, where, and who can reach it.

This module guards a reversal. For most of the project's life a citizen's
photograph was read for a description and discarded, and several docstrings said so
in as many words. Retaining it is a deliberate trade — an officer asked to dispatch
a crew should be able to look at the thing they are being told about — and these
tests are what stop the trade quietly becoming a worse one than the one that was
argued for.

Specifically: the file must not be enumerable, must not be named after anything
about the reporter, must not be reachable outside the console's own route, and a
row that claims a file must actually have one.
"""
from __future__ import annotations

import base64

import pytest

from app.services import evidence

#: A 1×1 PNG. Small enough to be a literal, real enough that a decoder accepts it.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)

TOKEN = "JS-TEST-0001"


@pytest.fixture(autouse=True)
def _clean_evidence_dir():
    """Each test starts with no files. The directory is process-wide (one temp path
    per run, set in conftest), so a leftover from an earlier test would let a
    `resolve` assertion pass against the wrong file."""
    yield
    for leftover in evidence.directory().glob("*"):
        leftover.unlink(missing_ok=True)


# ---------- the storage module ----------

def test_a_stored_photo_is_named_after_the_token_and_nothing_else():
    """The filename is the whole privacy surface of the file itself. A phone names
    photos `IMG_20260823_110815.jpg`, which is a precise capture time; WhatsApp
    names them after the sender. Neither may survive."""
    name = evidence.store(TOKEN, PNG, "image/png")
    assert name == f"{TOKEN}.png"
    assert evidence.resolve(name).read_bytes() == PNG


def test_the_extension_comes_from_the_mime_type_not_the_upload():
    assert evidence.store(TOKEN, PNG, "image/jpeg") == f"{TOKEN}.jpg"
    assert evidence.store(TOKEN, PNG, "image/webp; charset=binary") == f"{TOKEN}.webp"


@pytest.mark.parametrize(
    ("token", "data", "mime"),
    [
        (None, PNG, "image/png"),          # no token: nothing to name it after
        (TOKEN, None, "image/png"),        # no bytes: no photograph was sent
        (TOKEN, b"", "image/png"),         # empty upload, e.g. a cancelled picker
        (TOKEN, PNG, "application/pdf"),   # not an image at all
        (TOKEN, PNG, "image/gif"),         # an image Gemini will not read inline
    ],
)
def test_store_returns_none_rather_than_raising(token, data, mime):
    """Every failure here must be survivable. The text is the complaint; losing the
    corroboration is an inconvenience, losing the report is a person's problem
    going unrecorded."""
    assert evidence.store(token, data, mime) is None


@pytest.mark.parametrize(
    "name",
    [
        "../../app/main.py",
        "..\\..\\jansetu.db",
        "JS-TEST-0001.png/../../secret",
        "/etc/passwd",
        "JS-TEST-0001.exe",
        "JS-TEST-0001",
        "",
        None,
    ],
)
def test_resolve_refuses_anything_that_is_not_a_stored_name(name):
    """`resolve` turns a database string into a file read — the one place in the app
    that does. It is treated as untrusted input even though `store` is what writes
    the column today."""
    assert evidence.resolve(name) is None


def test_resolve_returns_none_for_a_name_with_no_file():
    """A row can legitimately reference a file that is gone — a container restart,
    a manual cleanup. The console needs None, not an exception."""
    assert evidence.resolve("JS-GONE-0000.jpg") is None


def test_media_type_is_derived_from_the_extension_we_wrote():
    assert evidence.media_type("JS-A-1.png") == "image/png"
    assert evidence.media_type("JS-A-1.jpg") == "image/jpeg"
    # A name that got past validation must still not produce a script content type.
    assert evidence.media_type("JS-A-1.svg") == "application/octet-stream"


def test_purge_removes_the_file_and_is_safe_to_repeat():
    name = evidence.store(TOKEN, PNG, "image/png")
    assert evidence.purge(name) is True
    assert evidence.resolve(name) is None
    assert evidence.purge(name) is False


# ---------- the intake and console routes ----------

def _file_a_report_with_a_photo(client):
    return client.post(
        "/intake/report",
        data={
            "text": "Hamare ward mein sadak toot gayi hai, gaddhe bhare hain",
            "language": "hi",
            "location_text": "Kalahandi, Odisha",
            "channel": "text",
        },
        files={"image": ("IMG_20260823_110815.jpg", PNG, "image/jpeg")},
    )


def test_an_uploaded_photo_is_retained_and_reachable(client):
    filed = _file_a_report_with_a_photo(client)
    assert filed.status_code == 200, filed.text
    body = filed.json()
    request_id, token = body["request_id"], body["track_token"]

    detail = client.get(f"/requests/{request_id}").json()
    assert detail["has_photo"] is True
    assert detail["photo_stored"] is True
    # The officer sees the citizen's own reference — it is what names the download
    # and what a caller quotes down a phone line.
    assert detail["track_token"] == token

    shown = client.get(f"/requests/{request_id}/photo")
    assert shown.status_code == 200
    assert shown.content == PNG
    assert shown.headers["content-type"] == "image/jpeg"
    # Inline by default: the console shows it beside the description it corroborates.
    assert shown.headers["content-disposition"].startswith("inline")


def test_the_download_is_named_after_the_tracking_token(client):
    """The point of the feature: a file on an officer's desktop that can be matched
    back to a docket without a lookup. It must also carry nothing from the upload —
    the request above sends `IMG_20260823_110815.jpg`, a precise capture time."""
    body = _file_a_report_with_a_photo(client).json()
    token = body["track_token"]

    got = client.get(f"/requests/{body['request_id']}/photo", params={"download": "1"})

    assert got.status_code == 200
    disposition = got.headers["content-disposition"]
    assert disposition == f'attachment; filename="{token}.jpg"'
    assert "IMG_2026" not in disposition


def test_a_report_with_no_photo_has_nothing_to_serve(client):
    filed = client.post(
        "/intake/text",
        json={"text": "Gaon mein bijli nahi hai", "language": "hi", "channel": "text"},
    )
    request_id = filed.json()["request_id"]

    detail = client.get(f"/requests/{request_id}").json()
    assert detail["has_photo"] is False
    assert detail["photo_stored"] is False
    assert client.get(f"/requests/{request_id}/photo").status_code == 404


def test_a_missing_request_and_a_missing_photo_both_answer_404(client):
    """Same status either way. A different code for "no such docket" would let an
    unauthenticated caller enumerate which dockets exist by asking for photographs."""
    assert client.get("/requests/99999999/photo").status_code == 404


def test_the_photo_route_cannot_be_walked_out_of_its_directory(client):
    """The path parameter is an int, so traversal has to be rejected by routing
    rather than by the storage layer. Asserting it here means a future change to a
    string identifier cannot silently open the hole."""
    assert client.get("/requests/..%2F..%2Fjansetu.db/photo").status_code in (404, 422)


def test_the_citizen_response_does_not_leak_the_stored_filename(client):
    """`IntakeResult` is what the public web form and the WhatsApp reply render. The
    file's name is an internal detail of the console; a citizen learning it gains
    nothing and it would put a token in a second place it does not need to be."""
    body = _file_a_report_with_a_photo(client).json()
    assert "photo_path" not in body
    assert "photo_stored" not in body
