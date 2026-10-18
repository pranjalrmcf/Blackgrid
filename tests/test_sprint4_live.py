"""Sprint 4 live pilot plumbing, offline: a fake *paid* provider stands in for OpenRouter."""

from __future__ import annotations

import json

import pytest

from blackgrid.budget import Pricing
from blackgrid.providers import MockProvider
from blackgrid.sprint4_live import MODEL, claim_diagnostics, run_pilot
from blackgrid.validation import S4LIVE_CASE_IDS, S4_CASE_IDS, S4V2_CASE_IDS, CASE_IDS, generator_seed


class FakePaid(MockProvider):
    model = MODEL

    def __init__(self, usd_per_token: float = 1e-7) -> None:
        super().__init__()
        self.price = Pricing(model=MODEL, prompt_usd_per_token=usd_per_token, completion_usd_per_token=usd_per_token,
                             source="test", fetched_utc="t")
        self.calls = 0

    def pricing(self):
        return self.price

    def complete(self, role, payload, messages, max_tokens):
        self.calls += 1
        return super().complete(role, payload, messages, max_tokens)


def test_live_case_seeds_are_fresh():
    live = {generator_seed(c) + k for c in S4LIVE_CASE_IDS for k in range(4)}
    other = {generator_seed(c) + k for c in CASE_IDS + S4_CASE_IDS + S4V2_CASE_IDS for k in range(4)}
    assert not live & other and max(live) < 10_000


def test_pilot_needs_explicit_paid_authorization(tmp_path):
    with pytest.raises(PermissionError):
        run_pilot(tmp_path / "p")
    with pytest.raises(ValueError):
        run_pilot(tmp_path / "q", cap_usd=0.51, allow_paid=True)


def test_pilot_runs_scores_and_exports_blinded_claims(tmp_path):
    fake = FakePaid()
    out = run_pilot(tmp_path / "runs" / "pilot", allow_paid=True, runs_dir=tmp_path / "runs", provider=fake,
                    case_ids=("val-301", "val-319"))
    suite = json.loads((out / "suite.json").read_text(encoding="utf-8"))
    assert suite["status"] == "completed" and 0 < suite["pilot_usd"] <= 0.50 and fake.calls > 0
    rows = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))["rows"]
    assert sorted((r["case"], r["condition"]) for r in rows) == sorted(
        (c, a) for c in ("val-301", "val-319") for a in ("baseline", "tool_only", "validated"))
    assert (out / "blinded_claims.csv").read_text(encoding="utf-8").startswith("review_id,claim")
    mapping = json.loads((out / "evaluator_private" / "blind_mapping.json").read_text(encoding="utf-8"))
    assert all(m["arm"] in ("tool_only", "validated") for m in mapping)  # baseline templates are not reviewed


def test_pilot_cap_stops_live_runs_and_keeps_them_in_the_denominator(tmp_path):
    fake = FakePaid(usd_per_token=5e-6)  # expensive: worst-case reservations quickly exhaust a small cap
    out = run_pilot(tmp_path / "runs" / "pilot", cap_usd=0.05, allow_paid=True, runs_dir=tmp_path / "runs",
                    provider=fake, case_ids=("val-301", "val-302", "val-303"))
    suite = json.loads((out / "suite.json").read_text(encoding="utf-8"))
    assert suite["pilot_usd"] <= 0.05 + 1e-9
    rows = json.loads((out / "evaluation.json").read_text(encoding="utf-8"))["rows"]
    assert len(rows) == 9  # every attempt stays in the denominator
    statuses = {r["status"] for r in rows if r["condition"] != "baseline"}
    assert "not_run_budget" in statuses or "budget_exhausted" in statuses
    assert all(r["status"] != "not_run_budget" for r in rows if r["condition"] == "baseline")


def test_claim_diagnostics_check_numbers_and_wording():
    docs = {"experiment_report.json": {"primary": {"result": {"observed_statistic": 0.4123, "p_value": 0.01}}}}
    links = ["experiment_report.json#/primary/result/observed_statistic", "experiment_report.json#/primary/result/p_value"]
    good = claim_diagnostics({"text": "Q = 0.412 with p = 0.01.", "evidence": links}, docs)
    bad = claim_diagnostics({"text": "Strong structure (Q = 0.5), preregistered.", "evidence": links}, docs)
    assert good["numbers_bound"] and not good["strength_wording"]
    assert not bad["numbers_bound"] and bad["strength_wording"] and bad["preregistered_wording"]
