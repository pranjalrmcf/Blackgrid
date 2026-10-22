"""Create a localhost-only development certificate; preserve existing key material."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(".secrets"))
    parser.add_argument("--openssl", default=shutil.which("openssl"))
    args = parser.parse_args()
    executable = args.openssl
    if not executable and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/openssl.exe"
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        parser.error("OpenSSL is required; supply --openssl with its executable path")
    directory = args.directory.resolve()
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    cert, key = directory / "server-cert.pem", directory / "server-key.pem"
    if cert.exists() or key.exists():
        if not (cert.is_file() and key.is_file()) or cert.is_symlink() or key.is_symlink():
            parser.error("incomplete or unsafe existing TLS files; inspect without overwriting")
        print("Existing TLS files preserved.")
        return
    # Generate privately before publishing either file; no private material reaches stdout.
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        temporary = Path(tmp)
        subprocess.run([executable, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "90",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-addext", "extendedKeyUsage=serverAuth", "-keyout", str(temporary / "key.pem"),
            "-out", str(temporary / "cert.pem")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for source, target in ((temporary / "key.pem", key), (temporary / "cert.pem", cert)):
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(source.read_bytes())
    print("Local TLS certificate created for localhost and 127.0.0.1 (90 days).")


if __name__ == "__main__":
    main()
