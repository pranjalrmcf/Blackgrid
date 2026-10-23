"""Private offline API-state snapshots. Never overwrite an existing state tree."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import time
from contextlib import ExitStack, contextmanager, closing
from pathlib import Path, PurePosixPath

VERSION = "blackgrid-state-v1"
MAX_FILES = 100_000
MAX_BYTES = 4*1024**3
MAX_MANIFEST = 32*1024**2
MANIFEST = "snapshot.json"


def unsafe(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info,"st_file_attributes",0) & 0x400)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024**2),b""): h.update(block)
    return h.hexdigest()


@contextmanager
def lease(path):
    if path.exists() and unsafe(path): raise ValueError("unsafe state lease")
    with path.open("a+b") as held:
        try:
            if os.name == "nt":
                import msvcrt
                held.write(b"0"); held.flush(); held.seek(0)
                msvcrt.locking(held.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise ValueError("state in use; stop API and workers first") from None
        yield


def paths(root):
    if unsafe(root) or not root.is_dir(): raise ValueError("invalid state directory")
    found, size = [], 0
    for path in root.rglob("*"):
        if unsafe(path): raise ValueError("state contains link or reparse point")
        if path.is_dir(): continue
        if not path.is_file(): raise ValueError("unsupported state file")
        size += path.stat().st_size
        found.append(path)
        if len(found) > MAX_FILES or size > MAX_BYTES: raise ValueError("snapshot limits exceeded")
    return sorted(found)


def destination_path(source, destination):
    # Reject links before resolve can hide their identity.
    for parent in (destination,*destination.parents):
        if (parent.exists() or parent.is_symlink()) and unsafe(parent): raise ValueError("unsafe snapshot destination")
    destination = destination.absolute()
    if destination.exists() or not destination.parent.is_dir(): raise ValueError("destination must be new; parent must exist")
    a,b = source.resolve(),destination.resolve()
    if a.is_relative_to(b) or b.is_relative_to(a): raise ValueError("snapshot and state must be separate")
    return destination


def sqlite_file(path):
    with path.open("rb") as stream: return stream.read(16) == b"SQLite format 3\x00"


def check_database(path):
    # Finalized snapshot databases have no writers or journal dependency. Immutable
    # reads also prevent SQLite from adding WAL/SHM files during verification.
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro&immutable=1",uri=True,timeout=1)) as db:
        if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]: raise ValueError("invalid snapshot database")


def create(state, destination):
    state,destination = Path(state),Path(destination)
    destination = destination_path(state,destination)
    if not (state/"api/jobs.sqlite").is_file(): raise ValueError("API state database missing")
    started = time.monotonic()
    with ExitStack() as stack:
        stack.enter_context(lease(state/"api/service.lock"))
        files = paths(state)
        if state/MANIFEST in files: raise ValueError("reserved snapshot manifest in state")
        for path in files:
            if path.name == "execution.lock": stack.enter_context(lease(path))
        with tempfile.TemporaryDirectory(prefix=".blackgrid-backup-",dir=destination.parent) as temporary:
            payload = Path(temporary)/"payload"
            payload.mkdir(mode=0o700)
            records, total = {},0
            for path in files:
                relative = path.relative_to(state).as_posix()
                if path.name.endswith(("-wal","-shm")) or path.name in ("service.lock","execution.lock"):
                    continue
                output = payload/relative
                output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                if sqlite_file(path):
                    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=1)) as source, closing(sqlite3.connect(output)) as target:
                        def progress(*args):
                            if time.monotonic()-started > 120: raise ValueError("snapshot deadline")
                        source.backup(target,pages=256,progress=progress)
                        # A WAL source copies its journal mode too. Publish one
                        # self-contained database, never a hidden sidecar dependency.
                        target.execute("PRAGMA journal_mode=DELETE").fetchone()
                    check_database(output)
                else:
                    if path.suffix in (".sqlite", ".db"): raise ValueError("unrecognized state database")
                    shutil.copyfile(path,output)
                output.chmod(0o600)
                total += output.stat().st_size
                if total > MAX_BYTES or time.monotonic()-started > 120: raise ValueError("snapshot limits exceeded")
                records[relative] = dict(bytes=output.stat().st_size,sha256=digest(output),sqlite=sqlite_file(output))
            manifest = dict(version=VERSION,files=records,bytes=total)
            (payload/MANIFEST).write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            (payload/MANIFEST).chmod(0o600)
            os.rename(payload,destination)
    return dict(version=VERSION,files=len(records),bytes=total,seconds=time.monotonic()-started)


def verify(snapshot):
    snapshot = Path(snapshot)
    files = paths(snapshot)
    manifest_path = snapshot/MANIFEST
    if manifest_path.stat().st_size > MAX_MANIFEST: raise ValueError("oversized snapshot manifest")
    def unique(pairs):
        result = {}
        for key,value in pairs:
            if key in result: raise ValueError("duplicate snapshot field")
            result[key] = value
        return result
    raw = json.loads(manifest_path.read_bytes(),object_pairs_hook=unique)
    if not isinstance(raw,dict) or raw.get("version") != VERSION or not isinstance(raw.get("files"),dict): raise ValueError("invalid snapshot manifest")
    records = raw["files"]
    if not 1 <= len(records) <= MAX_FILES: raise ValueError("invalid snapshot count")
    expected = set(records)|{MANIFEST}
    if {p.relative_to(snapshot).as_posix() for p in files} != expected: raise ValueError("snapshot file set changed")
    total = 0
    for name, item in records.items():
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name
                or relative.as_posix() != name or name == MANIFEST): raise ValueError("unsafe snapshot path")
        path = snapshot/name
        if not isinstance(item,dict) or type(item.get("bytes")) is not int or type(item.get("sqlite")) is not bool:
            raise ValueError("invalid snapshot record")
        if path.stat().st_size != item["bytes"] or digest(path) != item.get("sha256"): raise ValueError("snapshot checksum mismatch")
        total += item["bytes"]
        if item["sqlite"]: check_database(path)
    if total != raw.get("bytes") or total > MAX_BYTES: raise ValueError("invalid snapshot size")
    return raw


def restore(snapshot, destination):
    snapshot,destination = Path(snapshot),Path(destination)
    destination = destination_path(snapshot,destination)
    started = time.monotonic()
    manifest = verify(snapshot)  # All validation precedes publishing any restored state.
    with tempfile.TemporaryDirectory(prefix=".blackgrid-restore-",dir=destination.parent) as temporary:
        payload = Path(temporary)/"payload"
        payload.mkdir(mode=0o700)
        for name, item in manifest["files"].items():
            output = payload/name
            output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copyfile(snapshot/name,output)
            output.chmod(0o600)
            if digest(output) != item["sha256"]: raise ValueError("snapshot changed during restore")
            if time.monotonic()-started > 120: raise ValueError("restore deadline")
        os.rename(payload,destination)
    return dict(version=VERSION,files=len(manifest["files"]),bytes=manifest["bytes"],seconds=time.monotonic()-started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=("create","verify","restore"))
    parser.add_argument("source",type=Path)
    parser.add_argument("destination",type=Path,nargs="?")
    args = parser.parse_args()
    try:
        if args.operation == "verify":
            verified = verify(args.source)
            result = dict(version=VERSION,verified=True,files=len(verified["files"]),bytes=verified["bytes"])
        else:
            if args.destination is None: parser.error("destination required")
            result = (create if args.operation == "create" else restore)(args.source,args.destination)
        print(json.dumps(result))
        return 0
    except (OSError,ValueError,sqlite3.Error,KeyError,TypeError):
        print(json.dumps({"status":"failed","code":"snapshot_rejected"}))
        return 1


if __name__ == "__main__": raise SystemExit(main())
