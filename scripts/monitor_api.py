"""Read local BLACKGRID monitoring using the existing private token and TLS CA."""
from __future__ import annotations

import argparse
import json
import re
import ssl
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def connection(subject="alice"):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", subject):
        raise ValueError("invalid subject")
    token = (ROOT / ".secrets" / (subject + ".token")).read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        raise ValueError("invalid token")
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context(
        cafile=str(ROOT / ".secrets/server-cert.pem"))))

    def request(path, body=None, key=None, raw=False):
        headers = {"Authorization": "Bearer " + token}
        data = None
        if body is not None:
            headers.update({"Content-Type": "application/json", "Idempotency-Key": key})
            data = json.dumps(body).encode()
        try:
            with opener.open(Request("https://localhost:8765"+path, data=data, headers=headers), timeout=30) as reply:
                result = reply.read(2*1024*1024).decode()
                return result if raw else json.loads(result)
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}: monitoring request failed") from None
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="alice")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--trace", metavar="JOB_ID")
    mode.add_argument("--metrics", action="store_true")
    mode.add_argument("--dashboard", action="store_true")
    args = parser.parse_args()
    if args.trace and not re.fullmatch(r"[a-f0-9]{32}", args.trace):
        parser.error("invalid job ID")
    try:
        request = connection(args.subject)
        if args.dashboard:
            page = request("/api/v1/monitoring", raw=True)
            output = ROOT / "tmp" / "blackgrid-monitoring.html"
            output.parent.mkdir(exist_ok=True)
            output.write_text(page, encoding="utf-8")
            print("Saved current dashboard:", output)
        elif args.metrics:
            print(request("/api/v1/metrics", raw=True), end="")
        else:
            path = f"/api/v1/jobs/{args.trace}/trace" if args.trace else "/api/v1/monitoring.json"
            print(json.dumps(request(path), indent=2))
    except (OSError, RuntimeError, ValueError):
        print("Monitoring unavailable. Check readiness, TLS and the credential's operator permission.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
