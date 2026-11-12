"""Real HTTP, two fixture users, temporary Hub DB. No external calls."""
import sys,tempfile,threading,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'OpenTwinHub-prep'))
from hub import Hub,Server
import hub_client
class BridgeIntegration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.h=Hub(str(Path(self.tmp.name)/'hub.sqlite'))
  self.ta=self.h.issue('alice');self.tb=self.h.issue('bob')
  self.s=Server(('127.0.0.1',0),self.h);self.thread=threading.Thread(target=self.s.serve_forever,daemon=True);self.thread.start()
  self.base=patch.object(hub_client,'BASE','http://127.0.0.1:'+str(self.s.server_address[1]));self.base.start()
  self.a=hub_client.HubClient();self.b=hub_client.HubClient()
  self.a.connect(dict(consent=True,token=self.ta));self.b.connect(dict(consent=True,token=self.tb))
  self.room=self.call(self.a,'POST','/v1/rooms',{'title':'fixture'})['data']['id'];self.route='/v1/rooms/'+self.room
 def tearDown(self):
  self.a.disconnect();self.b.disconnect();self.s.shutdown();self.s.server_close();self.thread.join();self.base.stop();self.h.db.close();self.tmp.cleanup()
 def call(self,c,method,path,payload=None):return c.request(dict(consent=True,method=method,path=path,payload=payload))
 def test_two_users_private_then_explicit_membership(self):
  self.assertEqual(self.call(self.b,'GET','/v1/rooms')['data'],[])
  self.assertEqual(self.call(self.b,'GET',self.route+'/events')['http_status'],404)
  self.call(self.a,'POST',self.route+'/members',{'user':'bob'})
  self.call(self.a,'POST',self.route+'/events',{'text':'only selected text','request_id':'fixture'})
  self.assertEqual(self.call(self.b,'GET',self.route+'/events')['data'][0]['text'],'only selected text')
  self.call(self.a,'DELETE',self.route+'/members',{'user':'bob'})
  self.assertTrue(self.call(self.b,'GET',self.route+'/events')['clear_private_views'])
 def test_public_redaction_and_separate_optins(self):
  listing=self.call(self.a,'POST',self.route+'/zoo',{'category':'coding','public':True,'profile':{'owner_name':'PRIVATE_OWNER'},'blueprint':'PRIVATE_BLUEPRINT'})['data']['id']
  public=self.call(self.b,'GET','/v1/zoo')['data'];self.assertEqual(set(public[0]),{'id','label','category'})
  self.assertNotIn('PRIVATE',json.dumps(public))
  self.call(self.a,'POST',self.route+'/members',{'user':'bob'})
  for field in ('profile','blueprint'):self.assertEqual(self.call(self.b,'GET','/v1/zoo/'+listing+'/'+field)['http_status'],404)
  self.call(self.a,'POST',self.route+'/zoo',{'category':'coding','public':True,'profile':{'owner_name':'PRIVATE_OWNER'},'share_profile':True})
  self.assertEqual(self.call(self.b,'GET','/v1/zoo/'+listing+'/profile')['data']['profile']['owner_name'],'PRIVATE_OWNER')
  self.assertEqual(self.call(self.b,'GET','/v1/zoo/'+listing+'/blueprint')['http_status'],404)
 def test_revocation_reconnect_does_not_grant_membership(self):
  self.h.revoke('bob');r=self.call(self.b,'GET','/v1/rooms');self.assertEqual(r['http_status'],401);self.assertIsNone(self.b.token)
  with self.assertRaises(ValueError):self.call(self.b,'GET','/v1/rooms')
  self.b.connect(dict(consent=True,token=self.h.issue('bob')))
  self.assertEqual(self.call(self.b,'GET','/v1/rooms')['data'],[])
  self.assertEqual(self.call(self.b,'GET',self.route+'/events')['http_status'],404)
 def test_reconnect_same_request_id_is_deduplicated(self):
  payload={'text':'chosen text','request_id':'stable-retry'}
  first=self.call(self.a,'POST',self.route+'/events',payload)
  self.a.disconnect();self.a.connect(dict(consent=True,token=self.ta))
  self.assertEqual(self.call(self.a,'POST',self.route+'/events',payload)['data'],first['data'])
  self.assertEqual(len(self.call(self.a,'GET',self.route+'/events')['data']),1)
  self.assertEqual(self.call(self.a,'POST',self.route+'/events',dict(payload,text='changed'))['http_status'],409)
if __name__=='__main__':unittest.main()
