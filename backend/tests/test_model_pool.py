"""The model pool: escalate across models on quota, never on a bad request.

These tests carry the demo's most fragile assumption. The free tier caps
`generate_content` at 20/day *per model*, so the chain is the only reason a
rehearsal and a live run can both show real AI on the same free key. If
escalation silently stops working, nothing fails — the app just quietly serves
keyword-classified output, which is exactly the failure these tests exist to
make loud.
"""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.services import model_pool


class _Resp:
    def __init__(self, model: str) -> None:
        self.text = f"answered by {model}"


class _Models:
    """Stands in for `client.models`, refusing every model in `refuse`."""

    def __init__(self, refuse: dict[str, Exception]) -> None:
        self.refuse = refuse
        self.tried: list[str] = []

    def generate_content(self, *, model: str, contents, config=None):  # noqa: ANN001
        self.tried.append(model)
        if model in self.refuse:
            raise self.refuse[model]
        return _Resp(model)


class _Client:
    def __init__(self, models: _Models) -> None:
        self.models = models


@pytest.fixture(autouse=True)
def _fresh_cursor():
    """Every test starts at the pinned model. The cursor is process-global by
    design — see the module docstring — so it has to be reset between tests or
    ordering decides the outcome."""
    model_pool.reset_cursor()
    yield
    model_pool.reset_cursor()


@pytest.fixture
def chain() -> list[str]:
    return get_settings().gemini_model_chain


def _install(monkeypatch, refuse: dict[str, Exception]) -> _Models:
    models = _Models(refuse)
    monkeypatch.setattr(model_pool, "client", lambda: _Client(models))
    return models


def test_the_chain_starts_with_the_pinned_model(chain):
    """`gemini_model` is what the docs, deck and demo script name. It must be
    tried first, or the pin is decorative."""
    assert chain[0] == get_settings().gemini_model


def test_the_chain_has_no_duplicates(chain):
    assert len(chain) == len(set(chain)), "a repeated model wastes a round trip on a known 429"


def test_every_model_in_the_chain_is_multimodal(chain):
    """The same pool transcribes audio and reads photographs. A text-only rung
    would accept a voice note and silently return nothing."""
    for model in chain:
        assert "flash" in model or "pro" in model, f"{model} is not a flash/pro multimodal model"
        for excluded in ("-tts", "-image", "gemma", "deep-research", "computer-use"):
            assert excluded not in model, f"{model} cannot serve audio or vision"


def test_quota_exhaustion_escalates_to_the_next_model(monkeypatch, chain):
    err = Exception("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: ...")
    models = _install(monkeypatch, {chain[0]: err})

    resp = model_pool.generate("hello", {"temperature": 0.0})

    assert models.tried == [chain[0], chain[1]]
    assert resp.text == f"answered by {chain[1]}"


@pytest.mark.parametrize(
    "message",
    [
        "429 RESOURCE_EXHAUSTED. Quota exceeded",
        "404 NOT_FOUND. models/x is not found",
        "503 UNAVAILABLE. The model is overloaded",
    ],
)
def test_all_three_model_level_failures_escalate(monkeypatch, chain, message):
    models = _install(monkeypatch, {chain[0]: Exception(message)})
    model_pool.generate("hello")
    assert len(models.tried) == 2


def test_a_bad_request_raises_instead_of_walking_the_chain(monkeypatch, chain):
    """A 400 fails identically on all seven models. Retrying would turn one fast
    failure into seven slow ones and burn a request from every daily bucket."""
    err = Exception("400 INVALID_ARGUMENT. Request contains an invalid argument")
    models = _install(monkeypatch, {name: err for name in chain})

    with pytest.raises(Exception, match="400"):
        model_pool.generate("hello")

    assert models.tried == [chain[0]], "a malformed request must not be retried on other models"


def test_it_walks_the_whole_chain_before_giving_up(monkeypatch, chain):
    err = Exception("429 RESOURCE_EXHAUSTED")
    models = _install(monkeypatch, {name: err for name in chain})

    with pytest.raises(Exception, match="429"):
        model_pool.generate("hello")

    assert models.tried == chain, "every bucket must be tried before degrading"


def test_the_cursor_remembers_the_exhausted_model(monkeypatch, chain):
    """The point of the cursor: a demo makes many calls, and re-trying an
    exhausted primary on each one costs a round trip of dead air per report."""
    models = _install(monkeypatch, {chain[0]: Exception("429 RESOURCE_EXHAUSTED")})

    model_pool.generate("first")
    models.tried.clear()
    model_pool.generate("second")

    assert models.tried == [chain[1]], "the second call must skip the model that already refused"


def test_current_model_reports_where_the_pool_settled(monkeypatch, chain):
    """`/capabilities` surfaces this so an operator can see mid-demo that the
    pinned model is spent without reading the logs."""
    assert model_pool.current_model() == chain[0]
    _install(monkeypatch, {chain[0]: Exception("429 RESOURCE_EXHAUSTED")})
    model_pool.generate("hello")
    assert model_pool.current_model() == chain[1]


def test_no_key_raises_rather_than_returning_none(monkeypatch):
    """Callers distinguish "no model" from "model said nothing". Returning None
    here would make an empty transcript indistinguishable from a missing key."""
    monkeypatch.setattr(model_pool, "client", lambda: None)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        model_pool.generate("hello")
