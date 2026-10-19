"""Offline provider request capture at the trusted transport boundary."""
import json
from types import SimpleNamespace
import pytest

@pytest.fixture
def capture_openrouter_http(monkeypatch):
    from blackgrid.agent import providers
    def install(handler):
        def transport(url,*,timeout_s,body=None,headers=None):
            if body is None:
                assert url.endswith('/models')
                return {'data':[{'id':'m','pricing':{'prompt':'0.0000001','completion':'0.0000003'}}]}
            assert url.endswith('/chat/completions')
            return json.loads(handler(SimpleNamespace(data=json.dumps(body).encode()),timeout_s).read())
        monkeypatch.setattr(providers,'_http_json',transport)
    return install
