import json, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse, parse_qs, urlencode
from unittest.mock import patch
import twin

class RouteTests(unittest.TestCase):
    def setUp(self):
        twin.SESSION_KEYS.clear()
        self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),twin.Handler)
        self.server.origin='http://127.0.0.1:'+str(self.server.server_address[1])
        self.server.hosts={urlparse(self.server.origin).netloc}
        self.server.token='fixture-token'
        self.server.twin=twin.Twin(Path(self.temp.name)/'test.db')
        self.calls=[]
        def fetch(*args,**kwargs):
            self.calls.append((args,kwargs))
            return {'key':'sk-or-v1-'+'x'*40}
        self.server.twin.onboarding.fetch=fetch
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server.twin.zoo.close();self.server.twin.db.close();self.temp.cleanup();twin.SESSION_KEYS.clear()
    def request(self,path,data=None,auth=True,extra=None):
        headers={'X-Twin-Token':self.server.token} if auth else {}
        headers.update(extra or {})
        request=Request(self.server.origin+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            with urlopen(request,timeout=3) as r:return r.status,r.headers,r.read().decode()
        except HTTPError as r:
            try:return r.code,r.headers,r.read().decode()
            finally:r.close()
    def test_new_routes_require_auth(self):
        for path,data in [('/api/oauth/openrouter/start',None),('/api/models/compatibility-guide',None),('/api/models/smart-connect',{'credential':'sk-or-v1-'+'x'*40}),('/api/models/auto-select',{}),('/api/models/discover-local',{'consent':True}),('/api/oauth/openrouter/cancel',{})]:
            self.assertEqual(self.request(path,data,False)[0],403)
        self.assertFalse(self.calls);self.assertFalse(twin.SESSION_KEYS)
    def test_callback_without_token_validates_state_and_hides_secrets(self):
        status,_,body=self.request('/api/oauth/openrouter/start')
        q=parse_qs(urlparse(json.loads(body)['authorization_url']).query)
        status,headers,body=self.request('/api/oauth/openrouter/callback?'+urlencode({'state':q['state'][0],'code':'fixture'}),auth=False)
        self.assertEqual(status,200);self.assertEqual(headers['Referrer-Policy'],'no-referrer')
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertNotIn(q['state'][0],body);self.assertNotIn(twin.SESSION_KEYS['openrouter'],body)
        self.assertIn('replaceState',body);self.assertEqual(len(self.calls),1)
    def test_bad_callback_and_host_no_exchange(self):
        for path in ('?code=x&state=nope','?code=x&code=y&state=z','?error=denied'):
            self.assertEqual(self.request('/api/oauth/openrouter/callback'+path,auth=False)[0],400)
        self.assertEqual(self.request('/api/oauth/openrouter/callback?code=x&state=y',auth=False,extra={'Host':'evil.test'})[0],403)
        self.assertFalse(self.calls)
    def test_cross_origin_connect_and_start_rejected(self):
        self.assertEqual(self.request('/api/oauth/openrouter/start',extra={'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request('/api/models/smart-connect',{'credential':'AIza'+'x'*40},extra={'Origin':'https://evil.test'})[0],403)
        self.assertFalse(twin.SESSION_KEYS)
    def test_smart_connect_no_persistence_no_inference(self):
        self.assertEqual(self.request('/api/models/smart-connect',{'credential':'AIza'+'x'*40})[0],200)
        self.assertEqual(self.request('/api/models/smart-connect',{'credential':'gsk_'+'x'*40})[0],200)
        data=json.loads(self.request('/api/models/auto-select',{})[2]);self.assertTrue(data['distinct_families'])
        self.assertNotIn('AIza'+'x'*40, json.dumps(self.server.twin.state()))
        self.assertFalse(self.calls)
    def test_discovery_requires_consent_and_is_mocked(self):
        with patch('twin.discover_local_models',return_value={'servers':[]}) as discover:
            self.assertEqual(self.request('/api/models/discover-local',{})[0],400);discover.assert_not_called()
            self.assertEqual(self.request('/api/models/discover-local',{'consent':True})[0],200);discover.assert_called_once()
    def test_manual_replacement_cancels_oauth(self):
        for path,data in [('/api/connect',{'provider':'openrouter','key':'sk-or-v1-'+'x'*40}),('/api/models/smart-connect',{'credential':'sk-or-v1-'+'x'*40})]:
            self.request('/api/oauth/openrouter/start')
            self.assertEqual(self.request(path,data)[0],200)
            self.assertIsNone(self.server.twin.onboarding.pending)
    def test_disconnect_cancels_pending_oauth(self):
        self.request('/api/oauth/openrouter/start')
        self.request('/api/disconnect',{'provider':'openrouter'})
        self.assertIsNone(self.server.twin.onboarding.pending)
if __name__=='__main__':unittest.main()
