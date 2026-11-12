import json,tempfile,unittest
from pathlib import Path
import twin
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.t=twin.Twin(Path(self.tmp.name)/'db');self.calls=[]
  self.t.hub_client.send=lambda *a:(self.calls.append(a) or (200,{'seq':1}))
  self.t.hub_client.connect({'consent':True,'token':'fixture-token-'+'x'*30})
  self.p=self.t.act('/api/projects',{'name':'PRIVATE_NAME','goal':'PRIVATE_GOAL'})
  self.d=self.t.act('/api/document',{'project_id':self.p['id'],'name':'PRIVATE_FILENAME','text':'selected sk-or-v1-'+('x'*40)})
  self.t.act('/api/document',{'project_id':self.p['id'],'name':'PRIVATE_SECOND','text':'PRIVATE_UNSELECTED'})
 def tearDown(self):self.t.zoo.close();self.t.db.close();self.tmp.cleanup()
 def test_context_preview_then_outbound_canaries(self):
  preview=self.t.act('/api/zoo/hub/context-preview',{'project_id':self.p['id'],'document_ids':[self.d['id']]})
  self.assertFalse(self.calls);self.assertTrue(preview['requires_exact_preview_approval'])
  text=preview['text'];self.assertNotIn('PRIVATE',text);self.assertNotIn('sk-or-v1-',text);self.assertIn('[REDACTED]',text)
  self.t.act('/api/zoo/hub/request',{'consent':True,'method':'POST','path':'/v1/rooms/fixture/events','payload':{'request_id':'fixture','text':text}})
  self.assertEqual(self.calls[0][2]['text'],text)
  self.assertIn('sk-or-v1-',self.t.project(self.p['id'])['documents'][0]['text'])
 def test_direct_unsanitized_send_blocked(self):
  with self.assertRaises(ValueError):self.t.act('/api/zoo/hub/request',{'consent':True,'method':'POST','path':'/v1/rooms/fixture/events','payload':{'request_id':'fixture','text':'sk-or-v1-'+'x'*40}})
  self.assertFalse(self.calls)
 def test_text_preview_and_no_implicit_history(self):
  result=self.t.act('/api/zoo/hub/text-preview',{'text':'key gsk_'+'x'*30});self.assertIn('[REDACTED]',result['text']);self.assertFalse(self.calls)
  with self.assertRaises(ValueError):self.t.act('/api/zoo/hub/context-preview',{'project_id':self.p['id'],'include_history':True})
 def test_empty_selection_sends_no_project_data(self):
  result=self.t.act('/api/zoo/hub/context-preview',{'project_id':self.p['id']})
  self.assertEqual(json.loads(result['text']),{'documents':[],'decisions':[]});self.assertFalse(self.calls)
if __name__=='__main__':unittest.main()
