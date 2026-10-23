"""Explicitly synthetic-only offline latency fixture; no inference optimization."""
import hashlib
import time
from blackgrid.agent.providers import MockProvider


class LatencyMockProvider(MockProvider):
    def complete(self, role, payload, messages, max_tokens):
        key = hashlib.sha256((role+str(len(str(payload)))).encode()).digest()[0]
        time.sleep((.025, .075, .15)[key % 3])
        return super().complete(role, payload, messages, max_tokens)
