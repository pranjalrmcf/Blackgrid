"""Gracefully stop the local console without changing workflow graph semantics."""
from __future__ import annotations

import signal
import threading


def run_console(httpd, console, grace_seconds: float = 30) -> bool:
    """Stop admission, close listener, drain action threads for a bounded interval.

    Return False on a drain timeout. The process then exits; unfinished workflow
    records retain crash-recovery semantics, not a fabricated completed status.
    """
    def stop(_signum=None, _frame=None):
        console.stop_admission()
        # shutdown() must run off the serve_forever thread to avoid deadlock.
        threading.Thread(target=httpd.shutdown, name="console-stop", daemon=True).start()

    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, stop)
    try:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.stop_admission()
    finally:
        console.stop_admission()
        httpd.server_close()
        drained = console.drain(grace_seconds)
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
    return drained
