import base64,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import twin
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQ0AAAAASUVORK5CYII=')
class Images(unittest.TestCase):
 def test_image_consent_library_persistence(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[]
   def generate(*args):calls.append(args);return PNG,{'output_tokens':1}
   t=twin.Twin(Path(d)/'db',image_transport=generate)
   p=t.act('/api/projects',{'name':'Art','goal':'Brand poster'})
   v=t.act('/api/preview',{'project_id':p['id'],'provider':'openai','model':'gpt-image-1.5','kind':'image','prompt':'Flat orange poster'})
   self.assertEqual(calls,[]);self.assertNotIn(twin.BASE,v['context'])
   with self.assertRaises(ValueError):t.send({'preview_id':v['preview_id']})
   r=t.send({'preview_id':v['preview_id'],'consent':True})
   self.assertEqual(len(calls),1);self.assertEqual(t.project(p['id'])['assets'][0]['id'],r['asset_id'])
   self.assertEqual(t.db.execute('SELECT data FROM assets').fetchone()[0],PNG)
   t.db.close();t=twin.Twin(Path(d)/'db');self.assertEqual(len(t.project(p['id'])['assets']),1);t.db.close()
 def test_image_adapter_contract(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):return json.dumps({'data':[{'b64_json':base64.b64encode(PNG).decode()}]}).encode()
  with patch.dict(twin.SESSION_KEYS,{'openai':'test-key'}),patch.object(twin,'urlopen',return_value=Response()) as call:
   raw,usage=twin.image_call('openai','gpt-image-1.5','Test image')
   self.assertEqual(raw,PNG);req=call.call_args.args[0];data=json.loads(req.data)
   self.assertEqual(req.full_url,'https://api.openai.com/v1/images/generations');self.assertEqual(data['n'],1);self.assertEqual(data['output_format'],'png')
 def test_reject_retired_or_wrong_provider(self):
  for p,m in [('anthropic','gpt-image-1.5'),('openai','gpt-image-1')]:
   with self.assertRaises(ValueError):twin.image_call(p,m,'test')
if __name__=='__main__':unittest.main()
