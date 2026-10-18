"""Budget enforcement for LLM calls (Sprint 1 Day 8).

Every call is *reserved* before it is made. The reservation assumes the worst case: a
conservative prompt-token estimate plus the full `max_tokens` completion. If the reservation would
exceed any cap, the call is never sent. Caps covered: calls, tokens, USD per investigation, USD
for the sprint (persisted across runs), retries per call, and revision rounds. Actual usage is
reconciled after each call. Retries and failed billable calls count.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from blackgrid.contracts import BudgetLimits, Contract, NonEmpty


class BudgetExceeded(RuntimeError):
    """The next call would break a budget cap; it was not made."""


class Pricing(Contract):
    model: NonEmpty
    prompt_usd_per_token: float
    completion_usd_per_token: float
    source: NonEmpty
    fetched_utc: NonEmpty


FREE = Pricing(model="mock", prompt_usd_per_token=0.0, completion_usd_per_token=0.0, source="mock (no spend)",
               fetched_utc="n/a")


PRICE_SAFETY = 2.0  # reserve 2x list price: one live call was charged 1.39x price x tokens (D-039)
MESSAGE_OVERHEAD_TOKENS = 64  # chat-template tokens per message


def estimate_tokens(text: str) -> int:
    """Typical token count (about 3 characters per token); used for the token cap."""
    return math.ceil(len(text) / 3) + 8


def prompt_token_bound(text: str, messages: int = 2) -> int:
    """Upper bound on prompt tokens: byte-level tokenizers never emit more tokens than input bytes."""
    return len(text.encode("utf-8")) + MESSAGE_OVERHEAD_TOKENS * messages


@dataclass
class Reservation:
    prompt_tokens: int  # typical estimate (token cap)
    prompt_token_bound: int  # strict bound (money)
    max_completion_tokens: int
    usd: float


@dataclass
class BudgetLedger:
    limits: BudgetLimits
    pricing: Pricing
    sprint_ledger: Path | None = None
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_usd: float = 0.0
    actual_usd: float = 0.0
    revisions: int = 0
    halted: str | None = None  # set when a charge exceeded its reservation: no further paid calls
    pending: Reservation | None = None
    events: list[dict] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def sprint_spent(self) -> float:
        if self.sprint_ledger is None or not self.sprint_ledger.is_file():
            return 0.0
        return float(json.loads(self.sprint_ledger.read_text(encoding="utf-8")).get("total_usd", 0.0))

    def reserve(self, prompt: str, max_completion_tokens: int, messages: int = 2) -> Reservation:
        """Book the worst case before a call: strict prompt bound + full completion, at 2x list price.

        The money caps are hard limits provided the provider honours max_tokens and charges at most
        2x its list price; any charge above the reservation halts all further paid calls (commit).
        """
        est = estimate_tokens(prompt)
        bound = prompt_token_bound(prompt, messages)
        usd = PRICE_SAFETY * (bound * self.pricing.prompt_usd_per_token
                              + max_completion_tokens * self.pricing.completion_usd_per_token)
        checks = [
            (self.halted is not None, f"paid calls halted: {self.halted}"),
            (self.calls + 1 > self.limits.max_llm_calls, f"call cap ({self.limits.max_llm_calls}) reached"),
            (self.tokens + est + max_completion_tokens > self.limits.max_tokens,
             f"token cap ({self.limits.max_tokens}) would be exceeded"),
            (self.actual_usd + usd > self.limits.max_usd_per_investigation,
             f"per-investigation USD cap ({self.limits.max_usd_per_investigation}) would be exceeded"),
            (self.sprint_spent() + self.actual_usd + usd > self.limits.max_usd_total,
             f"sprint USD cap ({self.limits.max_usd_total}) would be exceeded"),
        ]
        for broken, reason in checks:
            if broken:
                self.events.append({"event": "stop", "reason": reason, "reserved_usd": usd})
                raise BudgetExceeded(reason)
        self.calls += 1
        self.estimated_usd += usd
        self.events.append({"event": "reserve", "prompt_tokens_est": est, "prompt_token_bound": bound,
                            "max_completion": max_completion_tokens, "usd": usd})
        self.pending = Reservation(prompt_tokens=est, prompt_token_bound=bound,
                                   max_completion_tokens=max_completion_tokens, usd=usd)
        return self.pending

    def commit(self, prompt_tokens: int, completion_tokens: int, reported_usd: float | None = None) -> float:
        usd = (prompt_tokens * self.pricing.prompt_usd_per_token
               + completion_tokens * self.pricing.completion_usd_per_token)
        if reported_usd is not None:
            usd = max(usd, reported_usd)  # never under-count spend
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.actual_usd += usd
        self.events.append({"event": "commit", "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens, "usd": usd})
        reserved = self.pending.usd if self.pending else 0.0
        self.pending = None
        if usd > reserved + 1e-12:
            self.halted = f"a call was charged ${usd:.6f}, above its ${reserved:.6f} reservation"
            self.events.append({"event": "reservation_exceeded", "charged_usd": usd, "reserved_usd": reserved})
        return usd

    def commit_unknown(self) -> float:
        """A failed call whose billing is unknown: book the whole reservation as spent (worst case)."""
        r = self.pending
        if r is None:
            return 0.0
        self.pending = None
        self.prompt_tokens += r.prompt_tokens
        self.completion_tokens += r.max_completion_tokens
        self.actual_usd += r.usd
        self.events.append({"event": "assumed_charge", "reason": "failed call; billing unknown", "usd": r.usd,
                            "prompt_tokens": r.prompt_tokens, "completion_tokens": r.max_completion_tokens})
        return r.usd

    def begin_revision(self) -> None:
        if self.revisions + 1 > self.limits.max_revision_rounds:
            self.events.append({"event": "stop", "reason": "revision cap reached"})
            raise BudgetExceeded(f"revision cap ({self.limits.max_revision_rounds}) reached")
        self.revisions += 1

    def persist_sprint_total(self) -> None:
        """Add this investigation's actual spend to the sprint-wide ledger (live runs only)."""
        if self.sprint_ledger is None or self.actual_usd == 0:
            return
        total = self.sprint_spent() + self.actual_usd
        self.sprint_ledger.parent.mkdir(parents=True, exist_ok=True)
        self.sprint_ledger.write_bytes(json.dumps(
            {"total_usd": total, "updated_utc": datetime.now(UTC).isoformat()}, indent=2).encode("utf-8"))
