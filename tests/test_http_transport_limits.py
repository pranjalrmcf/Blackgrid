"""Actual transport-process limits and pure permission checks; no simulated LLM."""
import json
import time
import pytest
from blackgrid.agent.http_transport import request
from blackgrid.agent.providers import _http_json, ProviderError
from blackgrid.agent.tools import network_denied, network_is_denied, NetworkDenied


@pytest.mark.parametrize('url', ['file:///private', 'https://example.org/api', 'https://openrouter.ai.evil.test/api/v1/models'])
def test_transport_rejects_unregistered_endpoints_without_echoing_credentials(url):
    reply=request({'url':url,'method':'GET','headers':{'Authorization':'Bearer TEST-SECRET'},'timeout_s':1})
    assert not reply['ok'] and reply['category']=='permanent'
    assert 'TEST-SECRET' not in json.dumps(reply)


def test_transport_process_is_killed_at_wall_deadline():
    started=time.monotonic()
    with pytest.raises(ProviderError,match='wall-clock deadline') as exc:
        _http_json('https://openrouter.ai/api/v1/models',timeout_s=.001)
    assert exc.value.category=='uncertain'
    assert time.monotonic()-started<5


def test_provider_transport_cannot_bypass_the_tool_network_guard():
    assert not network_is_denied()
    with network_denied():
        with network_denied():
            with pytest.raises(NetworkDenied):
                _http_json('https://openrouter.ai/api/v1/models',timeout_s=1)
        assert network_is_denied()
    assert not network_is_denied()
