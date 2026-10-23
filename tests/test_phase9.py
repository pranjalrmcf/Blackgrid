"""Release gates reject incomplete tests, stale scans and unsafe promotion."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from scripts.release_gate import junit, security


def scan():
    return {
        "CreatedAt": datetime.now(UTC).isoformat(),
        "Results": [{"Type": "debian", "Vulnerabilities": []}, {"Type": "python-pkg"}],
    }


@pytest.mark.parametrize("scope", ["local-restricted", "public"])
def test_release_refuses_critical_or_fixable_high(scope):
    for severity, fixed in [("CRITICAL", ""), ("HIGH", "1.2.3")]:
        report = scan()
        report["Results"][0]["Vulnerabilities"] = [
            {"Severity": severity, "FixedVersion": fixed}
        ]
        with pytest.raises(ValueError):
            security(report, scope, now=time.time())


def test_residual_high_only_allows_explicit_restricted_scope():
    report = scan()
    report["Results"][0]["Vulnerabilities"] = [{"Severity": "HIGH"}]
    assert security(report, "local-restricted", now=time.time())["high"] == 1
    with pytest.raises(ValueError):
        security(report, "public", now=time.time())


def test_missing_coverage_and_stale_scan_cannot_promote():
    report = scan()
    with pytest.raises(ValueError):
        security(report, "local-restricted", now=time.time() + 86401)
    report["Results"].pop()
    with pytest.raises(ValueError):
        security(report, "local-restricted", now=time.time())


def test_junit_rejects_failure_unexpected_skip_and_empty_collection(tmp_path):
    path = tmp_path / "report.xml"
    for body in [
        "",
        "<testcase><failure/></testcase>" * 675,
        '<testcase><skipped message="unavailable"/></testcase>' * 675,
    ]:
        path.write_text("<testsuite>" + body + "</testsuite>")
        with pytest.raises(ValueError):
            junit(path)
    path.write_text("<testsuite>" + "<testcase/>" * 675 + "</testsuite>")
    assert junit(path)["passed"] == 675


def test_ci_has_no_production_secrets_or_automatic_deployment():
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    assert all(job["runs-on"] == "ubuntu-24.04" for job in workflow["jobs"].values())
    for job in workflow["jobs"].values():
        assert job["timeout-minutes"] <= 30
        for step in job["steps"]:
            if "uses" in step:
                assert len(step["uses"].rsplit("@", 1)[1]) == 40
    text = Path(".github/workflows/ci.yml").read_text()
    assert "secrets." not in text and "pull_request_target" not in text
    assert "docker push" not in text and "deploy_phase9" not in text


def test_release_and_package_versions_match():
    import tomllib
    from blackgrid import __version__

    project = tomllib.loads(Path("pyproject.toml").read_text())
    protocol = json.loads(Path("protocols/production_phase9_v1.json").read_text())
    assert (
        project["project"]["version"] == protocol["release"] == __version__ == "1.0.0"
    )
