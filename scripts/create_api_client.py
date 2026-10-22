"""Provision a local service client; never print its bearer credential."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path


def main():
    from blackgrid.operations.api import Client, Credentials, load_credentials
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--directory", type=Path, default=Path(".secrets"))
    args = parser.parse_args()
    token = secrets.token_urlsafe(32)
    client = Client(subject=args.subject, token_sha256=hashlib.sha256(token.encode()).hexdigest())
    directory = args.directory.resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    registry = directory / "clients.json"
    clients = list(load_credentials(registry).clients) if registry.exists() else []
    if any(c.subject == client.subject for c in clients):
        parser.error("subject already exists; remove its old registry entry before rotating")
    validated = Credentials(clients=tuple(clients + [client]))
    secret = directory / (client.subject + ".token")
    # Exclusive creation prevents accidental replacement of an existing credential.
    fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(token + "\n")
    pending = directory / "clients.pending"
    try:
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(validated.model_dump_json(indent=2) + "\n")
        os.replace(pending, registry)
    except Exception:
        secret.unlink()
        raise
    print("Client created. Keep .secrets private; restart the API to load the registry.")


if __name__ == "__main__":
    main()
