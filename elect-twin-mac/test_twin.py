"""Offline regression suite. No network or paid model requests are made."""
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
from pathlib import Path
from twin import Twin, Handler, provider_call, BASE, load_catalog, SESSION_KEYS

class TwinTests(unittest.TestCase):
    def setUp(self):
        SESSION_KEYS.clear()
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'projects.db';self.calls=[]
        def fake(provider,model,context):
            self.calls.append((provider,model,json.loads(context)))
            return 'Reviewed by '+provider,{'output_tokens':12}
        self.t=Twin(self.path,transport=fake)
        self.p=self.t.act('/api/projects',{'name':'Project A','goal':'Choose a plan'})
    def tearDown(self):self.t.zoo.close();self.t.db.close();self.tmp.cleanup();SESSION_KEYS.clear()
    def preview(self,**overrides):
        d={'project_id':self.p['id'],'provider':'openai','model':'test-model','prompt':'Draft a plan'};d.update(overrides)
        return self.t.act('/api/preview',d)
    def send(self,p):return self.t.act('/api/send',{'preview_id':p['preview_id'],'consent':True})
    def test_connect_is_memory_only_and_unverified(self):
        result=self.t.act('/api/connect',{'provider':'openai','key':'test-session-secret'})
        self.assertTrue(result['configured']);self.assertFalse(result['verified'])
        self.assertNotIn('test-session-secret',json.dumps(self.t.state()))
        self.assertNotIn(b'test-session-secret',self.path.read_bytes())
        with self.assertRaises(ValueError):self.t.act('/api/connect',{'provider':'openai','key':'contains spaces'})
    def test_create_and_reopen(self):
        self.t.act('/api/decision',{'project_id':self.p['id'],'text':'Keep private'})
        self.t.db.close();self.t=Twin(self.path)
        self.assertEqual(self.t.project(self.p['id'])['decisions'][0]['text'],'Keep private')
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
    def test_consent_required(self):
        p=self.preview()
        for consent in (False,None,'true',1):
            with self.assertRaises(ValueError):self.t.act('/api/send',{'preview_id':p['preview_id'],'consent':consent})
        self.assertEqual(self.calls,[])
    def test_preview_does_not_send(self):
        p=self.preview();self.assertIn(BASE,p['context']);self.assertEqual(self.calls,[])
    def test_replay_prevented(self):
        p=self.preview();self.send(p)
        with self.assertRaises(ValueError):self.send(p)
        self.assertEqual(len(self.calls),1)
    def test_expired_preview(self):
        p=self.preview();self.t.previews[p['preview_id']]['expires']=0
        with self.assertRaises(ValueError):self.send(p)
        self.assertEqual(self.calls,[])
    def test_preview_is_immutable_after_project_edit(self):
        p=self.preview();self.t.act('/api/project',{'id':self.p['id'],'goal':'A new goal'})
        self.send(p);self.assertEqual(self.calls[0][2]['project']['goal'],'Choose a plan')
    def test_selections_are_explicit(self):
        doc=self.t.act('/api/document',{'project_id':self.p['id'],'name':'brief.md','text':'Private reference'})
        dec=self.t.act('/api/decision',{'project_id':self.p['id'],'text':'No deployment'})
        self.send(self.preview())
        self.assertEqual(self.calls[0][2]['documents'],[])
        self.send(self.preview(document_ids=[doc['id']],decision_ids=[dec['id']],skill_ids=['project-plan']))
        ctx=self.calls[1][2];self.assertEqual(ctx['documents'][0]['text'],'Private reference');self.assertEqual(len(ctx['skills']),1)
    def test_project_isolation(self):
        b=self.t.act('/api/projects',{'name':'B','goal':'Secret B'})
        d=self.t.act('/api/document',{'project_id':b['id'],'name':'b.txt','text':'Private B'})
        with self.assertRaises(ValueError):self.preview(document_ids=[d['id']])
        p=self.preview();self.assertNotIn('Private B',p['context']);self.assertNotIn('Secret B',p['context'])
    def test_two_providers_share_only_approved_history(self):
        self.send(self.preview(provider='openai'))
        self.send(self.preview(provider='anthropic',include_history=True))
        self.assertEqual([c[0] for c in self.calls],['openai','anthropic'])
        self.assertEqual(self.calls[1][2]['history'][1]['content'],'Reviewed by openai')
        self.assertEqual(self.calls[1][2]['history'][1]['provider'],'openai')
    def test_no_history_by_default(self):
        self.send(self.preview());self.send(self.preview(provider='anthropic'))
        self.assertEqual(self.calls[1][2]['history'],[])
    def test_bad_selection_and_provider(self):
        for kwargs in ({'skill_ids':['missing']},{'document_ids':'bad'},{'provider':'unknown'},{'prompt':''}):
            with self.assertRaises(ValueError):self.preview(**kwargs)
    def test_failure_not_retried(self):
        attempts=[]
        def fail(*args):attempts.append(1);raise RuntimeError('Connection lost; outcome unknown')
        self.t.transport=fail;p=self.preview()
        with self.assertRaises(RuntimeError):self.send(p)
        with self.assertRaises(ValueError):self.send(p)
        self.assertEqual(len(attempts),1)
        project=self.t.project(self.p['id']);self.assertEqual(project['runs'][0]['status'],'failed_or_unknown');self.assertEqual(project['messages'],[])
    def test_restart_marks_interrupted_unknown(self):
        p=self.t.project(self.p['id']);p['runs']=[{'id':'interrupted','status':'running'}];self.t.save(p)
        self.t.db.close();self.t=Twin(self.path)
        self.assertEqual(self.t.project(self.p['id'])['runs'][0]['status'],'interrupted_unknown')
    def test_keyword_suggestions_explain_matching(self):
        found=self.t.act('/api/skills/search',{'query':'review document'})['skills']
        self.assertTrue(found);self.assertIn('document',found[0]['reason'])
    def test_context_size_guard(self):
        ids=[self.t.act('/api/document',{'project_id':self.p['id'],'name':str(i),'text':'x'*80000})['id'] for i in range(2)]
        with self.assertRaises(ValueError):self.preview(document_ids=ids)

class ProviderAdapterTests(unittest.TestCase):
    class Response:
        def __init__(self,value):self.value=value
        def read(self,limit=-1):return json.dumps(self.value).encode()
        def __enter__(self):return self
        def __exit__(self,*args):pass
    @patch.dict(os.environ,{'OPENAI_API_KEY':'test-openai-key','ANTHROPIC_API_KEY':'test-anthropic-key'})
    def test_payloads_and_output_parsing(self):
        cases=[('openai',{'choices':[{'message':{'content':'A'}}],'usage':{'total_tokens':20}},'https://api.openai.com/v1/chat/completions'),('anthropic',{'content':[{'type':'text','text':'B'}],'usage':{'input_tokens':12}},'https://api.anthropic.com/v1/messages')]
        for provider,response,endpoint in cases:
            with patch('twin.urlopen',return_value=self.Response(response)) as call:
                answer,usage=provider_call(provider,'chosen-model','approved context')
                req=call.call_args.args[0];payload=json.loads(req.data)
                self.assertEqual(req.full_url,endpoint);self.assertEqual(payload['model'],'chosen-model');self.assertTrue(answer);self.assertTrue(usage)
                self.assertIn('approved context',req.data.decode())
    @patch.dict(os.environ,{},clear=True)
    def test_missing_credentials_never_calls_network(self):
        with patch('twin.urlopen') as call:
            with self.assertRaises(ValueError):provider_call('openai','model','context')
            call.assert_not_called()
    @patch.dict(os.environ,{'OPENAI_API_KEY':'not-a-real-key'})
    def test_error_does_not_leak_response(self):
        e=HTTPError('https://api.openai.com',401,'secret error content',{},None)
        with patch('twin.urlopen',side_effect=e):
            with self.assertRaises(RuntimeError) as cm:provider_call('openai','model','private prompt')
            self.assertNotIn('secret error',str(cm.exception));self.assertIn('401',str(cm.exception))

class HttpBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        port=self.s.server_address[1];self.s.origin='http://127.0.0.1:'+str(port);self.s.hosts={'127.0.0.1:'+str(port)};self.s.token='private-test-session';self.s.twin=Twin(Path(self.tmp.name)/'db')
        self.thread=threading.Thread(target=self.s.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.s.shutdown();self.s.server_close();self.thread.join();self.s.twin.zoo.close();self.s.twin.db.close();self.tmp.cleanup()
    def get(self,headers):return urlopen(Request(self.s.origin+'/api/state',headers=headers),timeout=3)
    def test_private_api_requires_token(self):
        with self.assertRaises(HTTPError) as cm:self.get({})
        self.assertEqual(cm.exception.code,403)
        with self.get({'X-Twin-Token':self.s.token}) as r:self.assertEqual(json.load(r)['projects'],[])
    def test_cross_origin_and_host_blocked(self):
        for extra in ({'Origin':'https://evil.example'},{'Host':'evil.example'}):
            with self.assertRaises(HTTPError) as cm:self.get({'X-Twin-Token':self.s.token,**extra})
            self.assertEqual(cm.exception.code,403)
    def test_state_omits_credentials(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'secret-value'}):
            with self.get({'X-Twin-Token':self.s.token}) as r:text=r.read().decode()
        self.assertNotIn('secret-value',text);self.assertIn('configured',text)

class CatalogTests(unittest.TestCase):
    def test_only_portable_licensed_prompts_import(self):
        base={'id':'example','name':'document-review','title':'document review','capabilityType':'prompt-template','promptText':'Review evidence carefully.','license':{'confidence':'file-verified','name':'CC0-1.0'},'canonicalUrl':'https://example.org/source','revision':'pinned'}
        rows=[base,{**base,'id':'unknown-license','license':{'confidence':'unverified','name':'MIT'}},{**base,'id':'noncommercial','license':{'confidence':'file-verified','name':'CC-BY-NC-4.0'}},{**base,'id':'executable','capabilityType':'integration'},{**base,'id':'deprecated','deprecated':True}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'skills.json';path.write_text(json.dumps(rows));before=path.read_bytes()
            imported=load_catalog(path)
            self.assertEqual([x['id'] for x in imported],['catalog:example'])
            self.assertEqual(imported[0]['source'],'https://example.org/source');self.assertEqual(imported[0]['revision'],'pinned')
            self.assertEqual(path.read_bytes(),before)
    def test_reject_non_array(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'skills.json';path.write_text('{}')
            with self.assertRaises(ValueError):load_catalog(path)

if __name__=='__main__':unittest.main()
