"""Trusted API worker entry point; deny network syscalls on supported Linux hosts.

This is one containment control, not an arbitrary-code sandbox. API arguments
remain fixed and validated; container filesystem and resource limits still apply.
"""
from __future__ import annotations

import ctypes
import errno
import os
import platform


def deny_network() -> str:
    if os.name != "posix" or platform.system() != "Linux":
        # Host development is restricted to the same trusted mock CLI tools.
        return "trusted_tools_only"
    architectures = {
        "x86_64": (0xC000003E, (41, 42)),  # socket, connect
        "aarch64": (0xC00000B7, (198, 203)),
    }
    if platform.machine() not in architectures:
        raise RuntimeError("network containment unavailable for this architecture")
    arch, forbidden = architectures[platform.machine()]

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                    ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ushort), ("filters", ctypes.POINTER(Filter))]

    deny = 0x00050000 | errno.EPERM  # SECCOMP_RET_ERRNO
    rules = [(0x20, 0, 0, 4), (0x15, 1, 0, arch), (0x06, 0, 0, 0x80000000),
             (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, deny)]
    # Reject io_uring as well: it can create/connect sockets without these syscalls.
    for syscall in (*forbidden, 425, 426, 427):
        rules += [(0x15, 0, 1, syscall), (0x06, 0, 0, deny)]
    rules.append((0x06, 0, 0, 0x7FFF0000))  # SECCOMP_RET_ALLOW
    filters = (Filter * len(rules))(*(Filter(*row) for row in rules))
    program = Program(len(rules), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    # Neither installation nor later children can acquire new privileges/remove the filter.
    if libc.prctl(38, 1, 0, 0, 0) or libc.prctl(22, 2, ctypes.addressof(program), 0, 0):
        raise OSError(ctypes.get_errno(), "worker network containment failed")
    return "seccomp_network_denied"


def main():
    deny_network()
    from blackgrid.cli import main as cli
    return cli()


if __name__ == "__main__":
    raise SystemExit(main())
