import unittest
from hub_client import HubClient,NoRedirect,BASE
class Tests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def send(*args):self.calls.append(args);return 200,[]
        self.client=HubClient(send)
    def connect(self):self.client.connect({'consent':True,'token':'fixture-token-'+'x'*30})
    def request(self,path='/v1/zoo',**kw):return self.client.request(dict(consent=True,method='GET',path=path,**kw))
    def test_off_by_default_and_no_connect_network(self):
        with self.assertRaises(ValueError):self.request()
        self.connect();self.assertFalse(self.calls)
    def test_only_fixed_origin_and_routes(self):
        self.connect()
        for path in ['https://evil.test','//evil.test','/v1/zoo/../secrets','/v1/zoo?token=x','/v1/rooms/a/events?after=1&url=x','/v1/zoo/%2e%2e','/api/state']:
            with self.assertRaises(ValueError):self.request(path)
        self.assertFalse(self.calls);self.assertEqual(BASE,'http://127.0.0.1:18765')
    def test_consent_required(self):
        with self.assertRaises(ValueError):self.client.connect({'token':'x'*30})
        self.connect()
        with self.assertRaises(ValueError):self.client.request({'path':'/v1/zoo','method':'GET'})
    def test_read_and_explicit_write(self):
        self.connect();self.assertEqual(self.request()['status'],'ok')
        d={'consent':True,'method':'POST','path':'/v1/rooms/a/events','payload':{'text':'selected','request_id':'stable'}}
        self.client.request(d);self.client.request(d)
        self.assertEqual(self.calls[-1],self.calls[-2]);self.assertEqual(len(self.calls),3)
    def test_unknown_payload_and_delete_rejected(self):
        self.connect()
        for d in [dict(method='POST',path='/v1/rooms',payload={'title':'x','api_key':'secret'}),dict(method='DELETE',path='/v1/rooms/a/zoo',payload={})]:
            with self.assertRaises(ValueError):self.client.request(dict(consent=True,**d))
    def test_401_disconnects(self):
        self.connect();self.client.send=lambda *a:(401,{'secret':'never reflected'})
        r=self.request();self.assertTrue(r['clear_private_views']);self.assertIsNone(self.client.token)
        with self.assertRaises(ValueError):self.request()
    def test_disconnect_during_request_discards(self):
        self.connect()
        def send(*a):self.client.disconnect();return 200,{'private':'data'}
        self.client.send=send
        with self.assertRaises(ValueError):self.request()
    def test_errors_sanitized_and_redirects_blocked(self):
        self.connect()
        def send(*a):raise RuntimeError('secret')
        self.client.send=send
        with self.assertRaises(ValueError) as c:self.request()
        self.assertNotIn('secret',str(c.exception))
        with self.assertRaises(ValueError):NoRedirect().redirect_request(None,None,None,None,None,None)
if __name__=='__main__':unittest.main()
