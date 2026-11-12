import copy,json,unittest
from shared_context import sanitize_shared_context as sanitize
class Tests(unittest.TestCase):
 def setUp(self):
  self.p={'id':'PRIVATE_PROJECT','name':'PRIVATE_NAME','goal':'PRIVATE_GOAL','documents':[{'id':'a','text':'chosen','name':'PRIVATE_FILENAME','owner':'PRIVATE_OWNER','nested':{'key':'PRIVATE_NESTED'}},{'id':'b','text':'PRIVATE_OTHER'}],'decisions':[{'id':'c','text':'decision','path':'PRIVATE_PATH'}],'messages':[{'content':'PRIVATE_HISTORY'}],'runs':[{'context':'PRIVATE_RUN'}],'pods':{'text':'PRIVATE_POD'}}
 def test_empty_defaults(self):self.assertEqual(sanitize(self.p,{})['context'],{'documents':[],'decisions':[]})
 def test_allowlist_canaries(self):
  r=sanitize(self.p,{'document_ids':['a'],'decision_ids':['c']});self.assertNotIn('PRIVATE',json.dumps(r));self.assertEqual(r['context'],{'documents':[{'text':'chosen'}],'decisions':[{'text':'decision'}]})
 def test_non_destructive(self):
  before=copy.deepcopy(self.p);sanitize(self.p,{'document_ids':['a']});self.assertEqual(self.p,before)
 def test_unknown_selection_rejected(self):
  for key in ['include_history','pod_ids','include_project','all']:
   with self.assertRaises(ValueError):sanitize(self.p,{key:True})
 def test_missing_duplicate_ambiguous(self):
  for ids in [['missing'],['a','a'],'a']:
   with self.assertRaises(ValueError):sanitize(self.p,{'document_ids':ids})
  self.p['documents'].append(dict(self.p['documents'][0]))
  with self.assertRaises(ValueError):sanitize(self.p,{'document_ids':['a']})
 def test_explicit_private_canary_and_credentials(self):
  self.p['documents'][0]['text']='PRIVATE_CANARY sk-or-v1-'+('x'*40)+' AIza'+('x'*30)+' gsk_'+('x'*30)
  text=json.dumps(sanitize(self.p,{'document_ids':['a']},private_values=['PRIVATE_CANARY']))
  for value in ['PRIVATE_CANARY','sk-or-v1-','AIza','gsk_']:self.assertNotIn(value,text)
  self.assertIn('[REDACTED]',text)
 def test_limits(self):
  self.p['documents'][0]['text']='x'*8000
  with self.assertRaises(ValueError):sanitize(self.p,{'document_ids':['a']})
 def test_selected_private_prose_requires_review(self):
  self.p['documents'][0]['text']='Ordinary name and confidential strategy'
  result=sanitize(self.p,{'document_ids':['a']});self.assertTrue(result['requires_exact_preview_approval']);self.assertIn('confidential',result['context']['documents'][0]['text'])
if __name__=='__main__':unittest.main()
