"""Regenerate the CollegeMsg parser/window fixtures and their hand-derived expectations.

    uv run --frozen python tests/fixtures/collegemsg/make_fixtures.py

Expected values are written by hand from the construction below, not computed by the loader,
so the tests check the loader against an independent answer. Files are written as exact bytes;
`.gitattributes` marks this directory binary so line endings (including the CRLF case) survive.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAY, HOUR = 86_400, 3_600


def star(hub: int, first_leaf: int, n: int, ts: int) -> str:
    return "".join(f"{hub} {first_leaf + i} {ts}\n" for i in range(n))


FIXTURES: dict[str, tuple[bytes, dict]] = {
    # Schema problems, repeats, a self-loop, and one out-of-order timestamp.
    "messy.txt": (
        b"1 2 100\n1 2 100\n2 1 150\n3 3 160\n\n# comment\n1 2\na b 170\n4 5 -1\n4 5 120\n",
        dict(valid_events=5, malformed_rows=3, exact_duplicate_rows=1, self_loop_events=1,
             timestamp_decreases=1, chosen_index=0, window_events=5, window_active_nodes=5,
             window_unique_edges=2),
    ),
    # Windows line endings must parse identically.
    "crlf.txt": (
        b"1 2 100\r\n2 3 200\r\n3 3 300\r\n",
        dict(valid_events=3, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=1,
             timestamp_decreases=0, chosen_index=0, window_events=3, window_active_nodes=3,
             window_unique_edges=2),
    ),
    # Tabs, repeated spaces, and padding are whitespace, not malformed.
    "whitespace.txt": (
        b"1\t2\t100\n2   3  200\n  3 4 300  \n",
        dict(valid_events=3, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=0, chosen_index=0, window_events=3, window_active_nodes=4,
             window_unique_edges=3),
    ),
    # Half-open window: t0 + 7d - 1 is inside, t0 + 7d is outside.
    "boundary.txt": (
        f"1 2 1000\n2 3 {1000 + 7 * DAY - 1}\n3 4 {1000 + 7 * DAY}\n".encode(),
        dict(valid_events=3, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=0, chosen_index=0, window_events=2, window_active_nodes=3,
             window_unique_edges=2),
    ),
    # The anchor is the minimum timestamp, not the first row.
    "unsorted.txt": (
        b"5 6 500\n1 2 100\n2 3 300\n",
        dict(valid_events=3, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=1, chosen_index=0, window_events=3, window_active_nodes=5,
             window_unique_edges=3),
    ),
    # 7d and 3d hold 1,102 nodes (> 1,000); 1d holds only the first star (501 nodes).
    "fallback_1d.txt": (
        (star(0, 1, 500, 1000) + star(5000, 5001, 600, 1000 + 2 * DAY)).encode(),
        dict(valid_events=1100, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=0, chosen_index=2, window_events=500, window_active_nodes=501,
             window_unique_edges=500),
    ),
    # 7d, 3d, and 1d all hold both stars; only 6h excludes the second.
    "fallback_6h.txt": (
        (star(0, 1, 500, 1000) + star(5000, 5001, 600, 1000 + 7 * HOUR)).encode(),
        dict(valid_events=1100, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=0, chosen_index=3, window_events=500, window_active_nodes=501,
             window_unique_edges=500),
    ),
    # 1,001 nodes in one second: every candidate exceeds the node cap, so the rule abstains.
    "abstain_nodes.txt": (
        star(0, 1, 1000, 1000).encode(),
        dict(valid_events=1000, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=0, chosen_index=None, window_events=None, window_active_nodes=None,
             window_unique_edges=None),
    ),
    # No valid events at all.
    "empty.txt": (
        b"# header only\n\n",
        dict(valid_events=0, malformed_rows=0, exact_duplicate_rows=0, self_loop_events=0,
             timestamp_decreases=0, chosen_index=None, window_events=None, window_active_nodes=None,
             window_unique_edges=None),
    ),
}


def main() -> None:
    expected = {}
    for name, (data, values) in FIXTURES.items():
        (HERE / name).write_bytes(data)
        expected[name] = {"sha256": hashlib.sha256(data).hexdigest(), **values}
    (HERE / "expected.json").write_bytes((json.dumps(expected, indent=2, sort_keys=True) + "\n").encode())
    print(f"wrote {len(FIXTURES)} fixtures to {HERE}")


if __name__ == "__main__":
    main()
