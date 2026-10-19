"""D-063: a provider that ignores max_tokens (D-062: 40,576 tokens against 16,000) is reserved for, not trusted."""

from __future__ import annotations

import io
import json
from dataclasses import replace

import pytest
from pydantic import ValidationError

from blackgrid.agent import providers
from blackgrid.agent.budget import COMPLETION_OVERSHOOT, BudgetLedger, Pricing
from blackgrid.contracts import BudgetLimits, LLMConfig
from blackgrid.agent.providers import OpenRouterProvider

from tests.test_workflow import Counting, dev_config, start

PRICE = Pricing(model="fake-live", prompt_usd_per_token=1.99e-8, completion_usd_per_token=4.5e-7, source="test",
                fetched_utc="t")


def test_reservation_covers_the_observed_overrun_and_still_halts_beyond_it():
    ledger = BudgetLedger(limits=BudgetLimits(), pricing=PRICE)
    reservation = ledger.reserve("x" * 6_000, 16_000)
    assert reservation.requested_completion_tokens == 16_000
    assert reservation.max_completion_tokens == 16_000 * COMPLETION_OVERSHOOT
    ledger.commit(1_972, 40_576)  # the D-062 reply: now inside its reservation
    assert ledger.halted is None
    ledger.reserve("x" * 6_000, 16_000)
    ledger.commit(2_000, 100_000)  # beyond overshoot x 2x price safety (96,000-token equivalent): stop
    assert ledger.halted and "above its" in ledger.halted


class Overrunning(Counting):
    """Fake paid provider that returns 2.54x the requested max_tokens, like D-062."""

    def complete(self, role, payload, messages, max_tokens):
        done = super().complete(role, payload, messages, max_tokens)
        return replace(done, completion_tokens=int(max_tokens * 2.54))


def test_live_workflow_survives_a_provider_that_ignores_max_tokens(tmp_path):
    out = start(tmp_path, Overrunning(live=True), None, config=dev_config("live"), allow_paid=True)
    assert out.outcome.status == "completed", out.outcome.reason
    budget = json.loads((out.run_dir / "budget.json").read_text(encoding="utf-8"))
    assert not any(e["event"] == "reservation_exceeded" for e in budget["events"])


def test_openrouter_request_bounds_reasoning_tokens(capture_openrouter_http):
    sent = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        sent.update(json.loads(request.data.decode("utf-8")))
        return Response(json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode())

    capture_openrouter_http(fake_urlopen)
    OpenRouterProvider("m", "sk-test", reasoning_max_tokens=12_000).complete("analyst", {}, [], 16_000)
    assert sent["max_tokens"] == 16_000 and sent["reasoning"] == {"max_tokens": 12_000}
    sent.clear()
    OpenRouterProvider("m", "sk-test").complete("analyst", {}, [], 16_000)
    assert "reasoning" not in sent  # unchanged when not configured


def test_reasoning_budget_must_leave_room_for_the_answer():
    assert LLMConfig(max_tokens_per_call=16_000, reasoning_max_tokens=12_000).reasoning_max_tokens == 12_000
    with pytest.raises(ValidationError, match="leaving room"):
        LLMConfig(max_tokens_per_call=4_000, reasoning_max_tokens=4_000)
