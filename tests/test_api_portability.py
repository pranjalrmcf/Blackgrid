"""Explicit API-only decimal portability; frozen hashes and strict default remain intact."""
import copy
import json

import pytest

from blackgrid.evaluation import sprint7
from blackgrid.analysis.decisions import BeliefSpec, summarize

PROFILE = "api-beliefs-portability-v1"


@pytest.mark.parametrize("field", ["mean", "credible_interval_95", "predictive_block_10"])
def test_profile_allows_tiny_derived_drift_but_exact_default_does_not(field):
    recorded = summarize(BeliefSpec(), [])
    actual = copy.deepcopy(recorded)
    if field == "mean":
        actual["methods"]["A"][field] += 5e-14
    else:
        actual["methods"]["A"][field][0] += 5e-14
    assert not sprint7.beliefs_match(actual, recorded)
    assert sprint7.beliefs_match(actual, recorded, PROFILE)


@pytest.mark.parametrize("change", ["alpha", "count", "count_type", "parameter_type", "large", "nan", "bool", "shape", "identity"])
def test_profile_rejects_substantive_and_malformed_changes(change):
    recorded = summarize(BeliefSpec(), [])
    actual = copy.deepcopy(recorded)
    if change == "alpha":
        actual["methods"]["A"]["alpha"] += 5e-14
    elif change == "count":
        actual["observations"] += 1
    elif change == "count_type":
        actual["observations"] = float(actual["observations"])
    elif change == "parameter_type":
        actual["methods"]["A"]["alpha"] = float(actual["methods"]["A"]["alpha"])
    elif change == "large":
        actual["methods"]["A"]["mean"] += 1e-5
    elif change in ("nan", "bool"):
        actual["methods"]["A"]["mean"] = float("nan") if change == "nan" else True
    elif change == "shape":
        actual["methods"]["A"]["credible_interval_95"].append(.5)
    else:
        actual["identity"] = "changed"
    assert not sprint7.beliefs_match(actual, recorded, PROFILE)


def test_read_only_profile_verifies_without_rewriting_and_keeps_hash_gate(tmp_path, monkeypatch):
    root = tmp_path / "source"
    assert sprint7.run(root)["status"] == "completed"
    before = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
    original = sprint7.summarize
    def drift(spec, observations):
        result = original(spec, observations)
        result["methods"]["A"]["predictive_block_10"][0] += 5e-14
        return result
    monkeypatch.setattr(sprint7, "summarize", drift)
    with pytest.raises(ValueError, match="belief evidence mismatch"):
        sprint7.verify(root)
    assert sprint7.verify(root, numerical_profile=PROFILE)["numerical_profile"] == PROFILE
    assert before == {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
    path = root / "beliefs.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="artifact integrity"):
        sprint7.verify(root, numerical_profile=PROFILE)


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="unknown"):
        sprint7.beliefs_match({}, {}, "other")
