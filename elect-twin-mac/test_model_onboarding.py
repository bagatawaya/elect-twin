import json
import threading
import unittest
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch
import model_onboarding as m

class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.keys = {}
        self.calls = []
        self.now = 0
        def fetch(url, payload, timeout):
            self.calls.append((url, payload, timeout))
            return {'key': 'sk-or-v1-' + 'testonly' * 8}
        self.flow = m.Onboarding(self.keys, fetch=fetch, clock=lambda: self.now)
    def begin(self):
        return parse_qs(urlparse(self.flow.start(4321)['authorization_url']).query)
    def test_rfc7636_s256(self):
        self.assertEqual(m.challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'), 'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM')
    def test_mock_exchange_and_replay(self):
        q = self.begin()
        self.assertEqual(q['callback_url'], ['http://127.0.0.1:4321/api/oauth/openrouter/callback'])
        self.assertEqual(q['code_challenge_method'], ['S256'])
        self.flow.complete('testcode', q['state'][0])
        self.assertIn('openrouter', self.keys)
        self.assertEqual(m.challenge(self.calls[0][1]['code_verifier']), q['code_challenge'][0])
        self.assertNotIn(self.keys['openrouter'], str(q))
        with self.assertRaises(ValueError):self.flow.complete('testcode', q['state'][0])
        self.assertEqual(len(self.calls), 1)
    def test_mismatch_and_expiry_no_exchange(self):
        q = self.begin()
        with self.assertRaises(ValueError):self.flow.complete('code', 'wrong')
        self.now = 600
        with self.assertRaises(ValueError):self.flow.complete('code', q['state'][0])
        self.assertEqual(self.calls, [])
    def test_repeated_start_and_cancel(self):
        old = self.begin(); new = self.begin()
        self.assertNotEqual(old['state'], new['state'])
        with self.assertRaises(ValueError):self.flow.complete('code', old['state'][0])
        self.flow.cancel()
        with self.assertRaises(ValueError):self.flow.complete('code', new['state'][0])
        self.assertFalse(self.keys)
    def test_cancel_during_exchange_cannot_store(self):
        q = self.begin()
        def fetch(*a, **kw):
            self.flow.cancel()
            return {'key': 'sk-or-v1-' + 'x' * 40}
        self.flow.fetch=fetch
        with self.assertRaises(ValueError):self.flow.complete('code', q['state'][0])
        self.assertFalse(self.keys)
    def test_error_sanitized_and_single_use(self):
        q = self.begin()
        def fetch(*a, **kw):raise RuntimeError('secret-error-body')
        self.flow.fetch=fetch
        with self.assertRaises(ValueError) as caught:self.flow.complete('code', q['state'][0])
        self.assertNotIn('secret-error-body', str(caught.exception))
        self.assertIsNone(self.flow.pending)
    def test_invalid_key_rejected(self):
        q=self.begin(); self.flow.fetch=lambda *a,**k:{'key':'not-a-key'}
        with self.assertRaises(ValueError):self.flow.complete('code',q['state'][0])
        self.assertFalse(self.keys)
    def test_fixed_callback_no_redirect_input(self):
        for port in ('https://evil.test', 0, 65536, True):
            with self.assertRaises(ValueError):self.flow.start(port)
    def test_prefixes_and_order_no_key_echo(self):
        for prefix, provider in m.PREFIXES:
            value=prefix+'a'*40
            result=m.detect_and_register_credential(value,self.keys)
            self.assertEqual(result['provider'],provider)
            self.assertFalse(result['verified'])
            self.assertNotIn(value,json.dumps(result))
    def test_consumer_mistakes_not_saved(self):
        for value in ('hello@gmail.com','https://chatgpt.com/session','password',None, 'sk- key with spaces but long enough'):
            self.assertNotEqual(m.detect_and_register_credential(value,self.keys)['status'],'configured')
        self.assertFalse(self.keys)
    def test_unknown_not_saved(self):
        self.assertEqual(m.detect_and_register_credential('z'*60,self.keys)['status'],'unrecognized_credential')
        self.assertFalse(self.keys)
    def test_family_diversity(self):
        for providers in ({'gemini':'x','groq':'x'}, {'openai':'x','anthropic':'x'}):
            r=m.auto_select_models_for_session(providers)
            self.assertTrue(r['distinct_families'])
            self.assertNotEqual(r['builder']['family'],r['challenger']['family'])
    def test_router_and_single_provider_no_fake_diversity(self):
        for providers in ({'openrouter':'x'}, {'gemini':'x'}, {}):
            self.assertFalse(m.auto_select_models_for_session(providers)['distinct_families'])
    def test_free_preference_does_not_fall_back_to_paid(self):
        self.assertIsNone(m.auto_select_models_for_session({'openai':'x'},'free')['builder'])
        for intent in ('auto','free','reasoning','creative'):
            self.assertTrue(m.auto_select_models_for_session({'gemini':'x'},intent)['requires_preview_and_send'])
        with self.assertRaises(ValueError):m.auto_select_models_for_session({},'bad')
    def test_discovery_fixed_targets_and_filter(self):
        calls=[]
        def fetch(url,timeout):
            calls.append((url,timeout))
            return {'models':[{'name':'llama3:latest'},{'name':'<script>'}], 'data':[{'id':'local-model'}]}
        r=m.discover_local_models(fetch)
        self.assertEqual({x[0] for x in calls},set(m.LOCAL_ENDPOINTS.values()))
        self.assertEqual(r['servers'][0]['models'],['llama3:latest'])
        self.assertTrue(all(t==1 for _,t in calls))
    def test_discovery_failures_safe(self):
        def fetch(*a,**k):raise RuntimeError('secret')
        self.assertTrue(all(x['status']=='unavailable' for x in m.discover_local_models(fetch)['servers']))
    def test_discovery_deadline_and_lingering_worker_cap(self):
        release=threading.Event(); calls=[]
        def fetch(url,timeout):
            calls.append(url); release.wait(4); return {}
        try:
            start=m.time.monotonic(); result=m.discover_local_models(fetch)
            self.assertLess(m.time.monotonic()-start,2)
            self.assertTrue(all(x['status']=='timeout_or_busy' for x in result['servers']))
            m.discover_local_models(fetch)
            self.assertEqual(len(calls),2)
        finally:
            release.set()
            for lock in m._LOCAL_LOCKS.values():
                with lock:pass
    def test_redirect_block(self):
        with self.assertRaises(ValueError):m.NoRedirect().redirect_request(None,None,None,None,None,None)

if __name__=='__main__':unittest.main()
