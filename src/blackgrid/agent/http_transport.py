"""Trusted OpenRouter HTTP child. Private stdin/stdout; no shell or generated code.

The parent enforces a wall-clock subprocess deadline. This is timeout isolation,
not an OS security sandbox. Credentials never appear in arguments or error output.
"""
from __future__ import annotations
import json
import socket
import sys
import urllib.error
import urllib.request

ENDPOINTS = {'https://openrouter.ai/api/v1/models': 'GET',
             'https://openrouter.ai/api/v1/chat/completions': 'POST'}
INPUT_LIMIT = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(payload: dict) -> dict:
    url, method = payload.get('url'), payload.get('method')
    if not isinstance(url, str) or ENDPOINTS.get(url) != method:
        return {'ok': False, 'category': 'permanent', 'error': 'Transport endpoint/method is not allowlisted'}
    headers = payload.get('headers', {})
    if not isinstance(headers, dict) or set(headers) - {'Authorization', 'Content-Type', 'X-Title'}:
        return {'ok': False, 'category': 'permanent', 'error': 'Transport headers are not allowlisted'}
    if not all(isinstance(v, str) for v in headers.values()):
        return {'ok': False, 'category': 'permanent', 'error': 'Transport header values must be strings'}
    timeout = payload.get('timeout_s')
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 300:
        return {'ok': False, 'category': 'permanent', 'error': 'Invalid transport timeout'}
    body = json.dumps(payload['body']).encode('utf-8') if method == 'POST' else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    limit = (8 if method == 'GET' else 1) * 1024 * 1024
    try:
        open_request = (urllib.request.build_opener(NoRedirect()).open if payload.get('deny_redirects') is True
                        else urllib.request.urlopen)
        with open_request(req, timeout=timeout) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit:
            return {'ok': False, 'category': 'uncertain', 'error': 'Provider response exceeded byte limit'}
        return {'ok': True, 'response': json.loads(raw.decode('utf-8'))}
    except urllib.error.HTTPError as exc:
        return {'ok': False, 'category': 'permanent' if exc.code in (400,401,403,404) or
                (payload.get('deny_redirects') is True and 300 <= exc.code < 400) else 'transient',
                'error': f'OpenRouter HTTP {exc.code}', 'http_status': exc.code}
    except (TimeoutError, OSError) as exc:
        reason = getattr(exc, 'reason', exc)
        return {'ok': False, 'category': 'transient' if isinstance(reason, (socket.gaierror, ConnectionRefusedError)) else 'uncertain',
                'error': 'OpenRouter request failed: ' + type(reason).__name__}
    except (ValueError, TypeError, KeyError):
        return {'ok': False, 'category': 'uncertain', 'error': 'Provider returned an invalid response'}


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(INPUT_LIMIT + 1)
        if len(raw) > INPUT_LIMIT:
            result = {'ok': False, 'category': 'permanent', 'error': 'Transport input exceeded byte limit'}
        else:
            payload = json.loads(raw.decode('utf-8'))
            result = request(payload) if isinstance(payload, dict) else {'ok': False, 'category': 'permanent', 'error': 'Invalid transport input'}
    except Exception:
        result = {'ok': False, 'category': 'permanent', 'error': 'Invalid transport input'}
    sys.stdout.buffer.write(json.dumps(result).encode('utf-8'))


if __name__ == '__main__':
    main()
