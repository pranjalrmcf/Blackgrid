"""Optional owner-scoped deterministic cache policy; never a result or LLM cache."""
import hashlib
import platform
import sys
import time
from pathlib import Path

MAX_ENTRIES = 512
MAX_BYTES = 128*1024**2
MAX_AGE_SECONDS = 7*24*3600


def implementation_identity(root):
    digest = hashlib.sha256(b'blackgrid-api-tool-cache-v1')
    digest.update(repr((sys.version,platform.machine(),platform.libc_ver())).encode())
    for path in sorted((root/'src/blackgrid').rglob('*.py'))+[root/'uv.lock']:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def prune(root, *, now=None, max_entries=MAX_ENTRIES, max_bytes=MAX_BYTES):
    """One API worker: bound retained data before/after jobs, including rejected/temp files."""
    if not root.exists(): return
    if root.is_symlink(): raise ValueError('unsafe tool cache root')
    now = time.time() if now is None else now
    files = []
    for path in root.rglob('*'):
        if path.is_symlink(): raise ValueError('unsafe tool cache entry')
        if path.is_file():
            info = path.stat()
            if now-info.st_mtime > MAX_AGE_SECONDS:
                path.unlink()
            else:
                files.append((info.st_mtime,path,info.st_size))
    total = sum(row[2] for row in files)
    count = len(files)
    for _,path,size in sorted(files):
        if count <= max_entries and total <= max_bytes: break
        path.unlink()
        count -= 1
        total -= size


def directory(root, owner, mode, config_hash, code_hash):
    """Fail open to recomputation, never to a stale/other-owner result."""
    try:
        prune(root)
        owner_hash = hashlib.sha256(owner.encode()).hexdigest()
        epoch = hashlib.sha256(f'{mode}:{config_hash}:{code_hash}'.encode()).hexdigest()
        path = root/owner_hash/epoch
        for parent in (root,root/owner_hash,path):
            if parent.is_symlink(): return None
        path.mkdir(parents=True,exist_ok=True,mode=0o700)
        return path
    except (OSError,ValueError):
        return None
