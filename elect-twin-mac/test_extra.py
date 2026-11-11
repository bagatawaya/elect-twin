"""Contract tests for additional provider adapters; never perform live requests."""
import json
import os
import unittest
from unittest.mock import patch
import twin
from providers_extra import build_extra_providers, ENDPOINTS

class Response:
    def __init__(self,body):self.body=body
    def read(self,limit=-1):return json.dumps(self.body).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass

class ExtraProviderTests(unittest.TestCase):
    def setUp(self):
        self.specs=build_extra_providers(twin.BASE)
        self.saved_keys=dict(twin.SESSION_KEYS);twin.SESSION_KEYS.clear()
    def tearDown(self):
        twin.SESSION_KEYS.clear();twin.SESSION_KEYS.update(self.saved_keys)
    def test_three_distinct_fixed_https_destinations(self):
        self.assertEqual(set(self.specs),{'gemini','mistral','groq'})
        self.assertEqual(len({s['url'] for s in self.specs.values()}),3)
        for s in self.specs.values():self.assertTrue(s['url'].startswith('https://'));self.assertNotIn('?',s['url'])
    def test_payload_and_headers(self):
        for provider,spec in self.specs.items():
            with self.subTest(provider=provider):
                body=spec['payload']('user-selected-model','approved project context')
                self.assertEqual(body['model'],'user-selected-model')
                self.assertEqual(body['messages'],[{'role':'system','content':twin.BASE},{'role':'user','content':'approved project context'}])
                self.assertEqual(body[ENDPOINTS[provider][2]],2048)
                self.assertEqual(spec['headers']('user-key'),{'Authorization':'Bearer user-key'})
                self.assertNotIn('tools',body)
    def test_real_transport_boundary_for_each_provider(self):
        for provider,spec in self.specs.items():
            with self.subTest(provider=provider), patch.dict(twin.PROVIDERS,self.specs), patch.dict(os.environ,{spec['env']:'fixture-key'}):
                fixture={'choices':[{'message':{'content':'Fixture response'}}],'usage':{'prompt_tokens':17,'completion_tokens':5}}
                with patch('twin.urlopen',return_value=Response(fixture)) as network:
                    answer,usage=twin.provider_call(provider,'selected-model','approved context')
                request=network.call_args.args[0]
                self.assertEqual(request.full_url,spec['url'])
                self.assertEqual(request.get_header('Authorization'),'Bearer fixture-key')
                self.assertEqual(answer,'Fixture response');self.assertEqual(usage['completion_tokens'],5)
                self.assertEqual(json.loads(request.data)['messages'][1]['content'],'approved context')
    def test_missing_keys_never_call_network(self):
        with patch.dict(twin.PROVIDERS,self.specs), patch.dict(os.environ,{},clear=True), patch('twin.urlopen') as network:
            for provider in self.specs:
                with self.assertRaises(ValueError):twin.provider_call(provider,'chosen-model','context')
            network.assert_not_called()
    def test_text_chunks_exclude_reasoning_and_tools(self):
        data={'choices':[{'message':{'content':[{'type':'thinking','thinking':'private reasoning'},{'type':'text','text':'Visible answer'},{'type':'tool_call','name':'external-write'}]}}]}
        for spec in self.specs.values():self.assertEqual(spec['answer'](data),'Visible answer')
    def test_empty_output_rejected_by_transport(self):
        for provider,spec in self.specs.items():
            with self.subTest(provider=provider), patch.dict(twin.PROVIDERS,self.specs), patch.dict(os.environ,{spec['env']:'fixture-key'}), patch('twin.urlopen',return_value=Response({'choices':[{'message':{'content':None}}]})):
                with self.assertRaises(RuntimeError):twin.provider_call(provider,'chosen-model','context')

if __name__=='__main__':unittest.main()
