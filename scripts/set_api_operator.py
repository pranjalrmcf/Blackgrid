"""Grant/revoke local monitoring permission without rotating a bearer token."""
from __future__ import annotations
import argparse
import os
from pathlib import Path


def main():
    from blackgrid.operations.api import Credentials, load_credentials
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--directory", type=Path, default=Path(".secrets"))
    args = parser.parse_args()
    directory = args.directory.resolve()
    registry = directory / "clients.json"
    clients = load_credentials(registry)
    if not any(c.subject == args.subject for c in clients.clients):
        parser.error("subject does not exist")
    backup = directory / "clients.pre-phase5.json"
    if not backup.exists():
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(registry.read_bytes())
    updated = Credentials(clients=tuple(c.model_copy(update={"operator": not args.disable})
        if c.subject == args.subject else c for c in clients.clients))
    # Existing file ACL remains in place; never print credential material.
    with registry.open("r+b") as stream:
        stream.write((updated.model_dump_json(indent=2)+"\n").encode())
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    print("Monitoring permission updated; restart the API to load it. Token unchanged.")


if __name__ == "__main__":
    main()
