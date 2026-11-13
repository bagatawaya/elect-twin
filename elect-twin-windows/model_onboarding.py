"""Explicit, session-only onboarding. Importing this module performs no I/O.

OpenRouter contract verified 2026-11-11:
https://openrouter.ai/docs/guides/overview/auth/oauth
Model suggestions are editable defaults, not an account/price/quality guarantee.
"""
import base64
import hashlib
import json
import re
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirects are not permitted')

# Ignore environment proxy settings, especially for loopback discovery.
def request_json(url, payload=None, timeout=8):
    request = Request(url, data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'},
                      method='GET' if payload is None else 'POST')
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(262145)
    if len(body) > 262144:
        raise ValueError('Response too large')
    return json.loads(body)

def challenge(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')

PREFIXES = [('sk-or-v1-', 'openrouter'), ('sk-ant-', 'anthropic'),
            ('sk-proj-', 'openai'), ('gsk_', 'groq'), ('AIza', 'gemini'), ('sk-', 'openai')]

def detect_and_register_credential(raw_input, session_keys):
    """Only call after explicit paste/submit. Never echo input, read clipboard or verify remotely."""
    if not isinstance(raw_input, str) or len(raw_input) > 1024:
        return {'status': 'invalid_input', 'message': 'Enter one API key, not a password.'}
    value = raw_input.strip()
    if not value or '@' in value or '://' in value or len(value) < 20:
        return {'status': 'consumer_login_detected', 'message': 'Web logins and passwords are not API keys. Use OpenRouter sign-in or create a developer key. Do not paste passwords here.', 'guide': '/api/models/compatibility-guide'}
    for prefix, provider in PREFIXES:
        if value.startswith(prefix):
            if not re.fullmatch(r'[A-Za-z0-9_-]{20,500}', value):
                break
            session_keys[provider] = value
            return {'status': 'configured', 'provider': provider, 'verified': False,
                    'message': 'Prefix recognized, not remotely verified. Stored only for this app session.', 'storage': 'session_memory'}
    return {'status': 'unrecognized_credential', 'message': 'Could not identify this API key. Use Advanced provider selection; never enter a web password.', 'guide': '/api/models/compatibility-guide'}

def compatibility_guide():
    return {
        'web_accounts': 'ChatGPT and Claude web logins are not API credentials. Developer APIs require separate setup and usage terms; check current account eligibility for any credits or free quotas.',
        'options': [
            {'provider': 'openrouter', 'label': 'Sign in with OpenRouter', 'start': '/api/oauth/openrouter/start', 'note': 'Authorize a session-only API key in your browser. Account limits, model access and billing still apply.'},
            {'provider': 'gemini', 'label': 'Google AI Studio', 'url': 'https://aistudio.google.com/apikey', 'note': 'A free tier may be available, subject to region, account eligibility and quota. Check current terms.'},
            {'provider': 'groq', 'label': 'Groq developer console', 'url': 'https://console.groq.com/keys', 'note': 'A free developer tier may be available. Account eligibility, models and limits vary.'}],
        'no_key': {'available': ['Explore local demo rooms', 'Preview crew blueprints', 'Create local project notes'], 'note': 'Demo residents and voice previews are not live AI activity. Live model responses need an enabled provider or a running local model server.'},
        'intents': [{'id': 'auto', 'label': 'Auto (Recommended)'}, {'id': 'free', 'label': 'Prefer free options'}, {'id': 'reasoning', 'label': 'Deep Reasoning'}, {'id': 'creative', 'label': 'Creative Studio'}],
        'advanced': 'Custom model IDs remain available. Preview the destination before sending; suggestions never send a prompt or silently fail over.',
        'privacy': 'No automatic clipboard access. Keys stay in server RAM until disconnect or restart.'}

# Versioned suggestions; no claim that a model is available to the connected account.
DEFAULTS = [
    {'provider': 'gemini', 'model': 'gemini-3.1-flash-lite', 'family': 'gemini', 'label': 'Gemini Flash-Lite', 'free_candidate': True},
    {'provider': 'groq', 'model': 'openai/gpt-oss-20b', 'family': 'gpt', 'label': 'GPT OSS on Groq', 'free_candidate': True},
    {'provider': 'openai', 'model': 'gpt-5.4-nano', 'family': 'gpt', 'label': 'GPT Nano', 'free_candidate': False},
    {'provider': 'anthropic', 'model': 'claude-sonnet-4-5', 'family': 'claude', 'label': 'Claude Sonnet', 'free_candidate': False},
    {'provider': 'openrouter', 'model': 'openrouter/free', 'family': None, 'label': 'OpenRouter free router', 'free_candidate': True},
]

def auto_select_models_for_session(session_keys, intent='auto', catalog=None):
    if intent not in {'auto', 'free', 'reasoning', 'creative'}:
        raise ValueError('Unknown model intent')
    available = [dict(x) for x in (DEFAULTS if catalog is None else catalog) if session_keys.get(x['provider'])]
    if intent == 'free':
        available = [x for x in available if x.get('free_candidate')]
    if intent == 'reasoning':
        available.sort(key=lambda x: (x['provider'] != 'anthropic', x['provider'] != 'openai'))
    if intent == 'creative':
        available.sort(key=lambda x: (x['provider'] != 'anthropic', x['provider'] != 'gemini'))
    first = available[0] if available else None
    second = next((x for x in available[1:] if first.get('family') and x.get('family') and x['family'] != first['family']), None) if first else None
    return {'intent': intent, 'builder': first, 'challenger': second,
            'distinct_families': bool(second), 'status': 'suggested' if first else 'needs_connection',
            'verified': False, 'requires_preview_and_send': True,
            'explanation': 'Deterministic defaults from connected providers, not a quality ranking. Availability and free-tier eligibility are unverified. A second distinct family is offered only when known; a router cannot guarantee diversity.'}

LOCAL_ENDPOINTS = {'ollama': 'http://127.0.0.1:11434/api/tags', 'lmstudio': 'http://127.0.0.1:1234/v1/models'}
_LOCAL_LOCKS = {provider: threading.Lock() for provider in LOCAL_ENDPOINTS}

def discover_local_models(fetch=None):
    """Explicit action only: two fixed loopback endpoints, bounded parallel reads, no scanning."""
    fetch = fetch or request_json
    def probe(item):
        provider, url = item
        try:
            data = fetch(url, timeout=1)
            entries = data.get('models' if provider == 'ollama' else 'data', [])
            models = [x.get('name' if provider == 'ollama' else 'id') for x in entries[:50] if isinstance(x, dict)]
            models = [x for x in models if isinstance(x, str) and re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,160}', x)]
            return {'provider': provider, 'status': 'detected', 'models': models, 'verified_inference': False}
        except Exception:
            return {'provider': provider, 'status': 'unavailable', 'models': []}
    # A socket timeout alone cannot bound a slow-drip response. Daemon probes
    # have a shared deadline; per-provider locks cap lingering workers at two.
    results = {}
    def worker(item):
        provider = item[0]
        try:results[provider] = probe(item)
        finally:_LOCAL_LOCKS[provider].release()
    threads = []
    deadline = time.monotonic() + 1.2
    for item in LOCAL_ENDPOINTS.items():
        if _LOCAL_LOCKS[item[0]].acquire(blocking=False):
            thread = threading.Thread(target=worker, args=(item,), daemon=True)
            threads.append(thread);thread.start()
    for thread in threads:thread.join(max(0, deadline - time.monotonic()))
    servers = [results.get(provider, {'provider': provider, 'status': 'timeout_or_busy', 'models': []}) for provider in LOCAL_ENDPOINTS]
    return {'servers': servers, 'note': 'Discovery only; no prompt was sent. Local inference wiring requires explicit model selection.'}

class Onboarding:
    def __init__(self, session_keys, fetch=None, clock=None):
        self.keys = session_keys
        self.fetch = fetch or request_json
        self.clock = clock or time.monotonic
        self.pending = None
        self.lock = threading.Lock()
        self.generation = 0

    def start(self, port):
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('Invalid callback port')
        verifier, state = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        with self.lock:
            self.generation += 1
            self.pending = (state, verifier, self.clock() + 600, self.generation)
        # Fixed host/path; never derive a redirect destination from request headers/input.
        callback = 'http://127.0.0.1:%d/api/oauth/openrouter/callback' % port
        return {'authorization_url': 'https://openrouter.ai/auth?' + urlencode({'callback_url': callback, 'code_challenge': challenge(verifier), 'code_challenge_method': 'S256', 'state': state}), 'expires_in': 600}

    def cancel(self):
        with self.lock:
            self.pending = None
            self.generation += 1
        return {'status': 'cancelled'}

    def complete(self, code, state):
        if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,1024}', code) or not isinstance(state, str) or len(state) > 128:
            raise ValueError('Invalid sign-in response. Restart sign-in.')
        with self.lock:
            pending = self.pending
            if not pending or not secrets.compare_digest(pending[0], state):
                raise ValueError('Sign-in state mismatch. Restart sign-in.')
            self.pending = None  # Consume before I/O: no replay or automatic retries.
            if self.clock() >= pending[2]:
                raise ValueError('Sign-in expired. Restart sign-in.')
        try:
            result = self.fetch('https://openrouter.ai/api/v1/auth/keys', {'code': code, 'code_verifier': pending[1], 'code_challenge_method': 'S256'}, timeout=8)
            key = result.get('key')
            if not isinstance(key, str) or not re.fullmatch(r'sk-or-v1-[A-Za-z0-9_-]{12,490}', key):
                raise ValueError('Invalid key')
        except Exception:
            raise ValueError('Sign-in exchange failed. No retry performed; restart sign-in. You may review issued keys in OpenRouter.') from None
        with self.lock:
            if self.generation != pending[3]:
                raise ValueError('Sign-in was cancelled or replaced. Key was not stored; review issued keys in OpenRouter.')
            self.keys['openrouter'] = key
        return {'status': 'connected', 'storage': 'session_memory', 'verified_inference': False}
