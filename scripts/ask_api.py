"""Submit a question to local BLACKGRID, showing progress without exposing credentials."""
from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question")
    parser.add_argument("--live", action="store_true", help="Explicitly authorize this paid request within the retained server limits")
    parser.add_argument("--subject", default="alice")
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--job-id", help="Watch an existing job without submitting another")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.subject):
        parser.error("invalid subject")
    if args.job_id and not re.fullmatch(r"[a-f0-9]{32}", args.job_id):
        parser.error("invalid job ID")
    if not args.job_id and (not args.question or not 1 <= len(args.question.strip()) <= 500):
        parser.error("provide a question of 1 to 500 characters")
    key = args.idempotency_key or uuid.uuid4().hex
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key):
        parser.error("invalid idempotency key")
    root = Path(__file__).resolve().parents[1]
    token = (root / ".secrets" / (args.subject + ".token")).read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        parser.error("invalid token file")
    context = ssl.create_default_context(cafile=str(root / ".secrets/server-cert.pem"))
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context))

    def request(path, body=None):
        headers = {"Authorization": "Bearer " + token, "Idempotency-Key": key}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = Request("https://localhost:8765" + path, data=data, headers=headers)
        try:
            response = opener.open(req, timeout=15)
        except HTTPError as exc:
            detail = json.loads(exc.read()).get("error", {})
            raise RuntimeError(f"HTTP {exc.code}: {detail.get('code', 'request_failed')}") from None
        with response:
            return json.loads(response.read())

    print("Mode:", "watch existing job" if args.job_id else
          "live (paid; retained server budget applies)" if args.live else "mock", flush=True)
    if not args.job_id:
        print("Idempotency key:", key, flush=True)
    try:
        if args.job_id:
            job_id = args.job_id
        else:
            body = {"question": args.question.strip(), "mode": "live" if args.live else "mock"}
            if args.live:
                body["allow_paid"] = True
            job_id = request("/api/v1/jobs", body)["job_id"]
        print("Job:", job_id, flush=True)
        previous = None
        deadline = time.monotonic() + 1000
        while time.monotonic() < deadline:
            row = request("/api/v1/jobs/" + job_id)
            progress = {"mode": row.get("mode"), "state": row["state"], "error_code": row.get("error_code"),
                        **row.get("progress", {})}
            if progress != previous:
                print(json.dumps(progress), flush=True)
                previous = progress
            if row["state"] not in ("queued", "running"):
                break
            time.sleep(2)
        if row["state"] == "completed":
            print(json.dumps(request(f"/api/v1/jobs/{job_id}/results"), indent=2))
            return 0
        print("Retain this job ID. Paused/interrupted/uncertain work requires inspection; no automatic replay.")
        return 1
    except (OSError, URLError, RuntimeError) as exc:
        print(str(exc) if isinstance(exc, RuntimeError) else "Connection failed; retry submission with the SAME idempotency key above.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
