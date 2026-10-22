"""Reuse retained live authorization and copy only the provider key into private mounts.

No pricing lookup or paid provider call is performed. Existing API policy is never renewed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


def main():
    from blackgrid.agent.live_allowance import read_allowance
    from blackgrid.agent.providers import KEY_NAMES
    from blackgrid.operations.live import LivePolicy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="alice")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.subject):
        parser.error("invalid subject")
    root = Path(__file__).resolve().parents[1]
    directory = root / ".secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    policy_path = directory / "live-policy.json"
    if policy_path.exists():
        retained_policy = LivePolicy.model_validate_json(policy_path.read_bytes())
        portable = retained_policy.model_dump(mode="json")
        portable.update(config=retained_policy.config.as_posix(), key_file=retained_policy.key_file.as_posix())
        if portable != json.loads(policy_path.read_bytes()):
            policy_path.write_text(json.dumps(portable, indent=2) + "\n")
        print("Existing live policy preserved; no authorization was renewed.")
        return
    runs = root / "runs"
    allowance = runs / "console-project-allowance.json"
    if not allowance.exists():
        allowance = runs / "sprint5-live-allowance.json"
    retained = read_allowance(allowance, runs)
    if retained["remaining_usd"] < .15:
        parser.error("retained authorization has insufficient remaining budget; no new grant was created")
    # A legacy allowance's spent_usd is relative; the absolute ceiling minus remainder
    # retains all historical spend and unresolved reservations in the imported baseline.
    prior = retained["ceiling_project_usd"] - retained["remaining_usd"]
    fields = {}
    source = root / ".env"
    if source.is_file():
        for line in source.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                fields[name.strip().removeprefix("export ")] = value.strip().strip('"').strip("'")
    key = next((os.environ.get(name) or fields.get(name) for name in KEY_NAMES
                if os.environ.get(name) or fields.get(name)), None)
    if not key or not key.isascii() or any(c.isspace() for c in key):
        parser.error("provider key missing or invalid; secret contents were not displayed")
    secret = directory / "openrouter-key.txt"
    if secret.exists():
        if secret.read_text().strip() != key:
            parser.error("existing provider key differs; explicit rotation is required")
    else:
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(key + "\n")
    policy = LivePolicy(model=retained["model"], prior_spend_usd=prior,
        ceiling_project_usd=retained["ceiling_project_usd"], subjects=(args.subject,),
        config=Path("/app/configs/collegemsg_live.json"), key_file=Path("/run/secrets/openrouter-key.txt"))
    fd = os.open(policy_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        portable = policy.model_dump(mode="json")
        portable.update(config=policy.config.as_posix(), key_file=policy.key_file.as_posix())
        stream.write(json.dumps(portable, indent=2) + "\n")
    print(json.dumps({"retained_project_ceiling_usd": policy.ceiling_project_usd,
        "imported_spend_and_reservations_usd": prior, "per_job_cap_usd": policy.max_per_job_usd,
        "paid_calls_made": 0}))


if __name__ == "__main__":
    main()
