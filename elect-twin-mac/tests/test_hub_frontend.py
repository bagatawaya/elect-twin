"""Offline Hub UI contracts and async state-machine tests. No live services."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HubFrontend(unittest.TestCase):
    def test_modules_mirrored_and_hooked_without_changing_zoo(self):
        shell = (ROOT / 'web/shell.html').read_text()
        for suffix, tag in [('js', 'script'), ('css', 'style')]:
            source = (ROOT / ('web/hub.' + suffix)).read_text()
            marker = 'hub-script' if suffix == 'js' else 'hub-styles'
            self.assertIn('<' + tag + ' id="' + marker + '">\n' + source + '\n</' + tag + '>', shell)
        self.assertIn("if(typeof enhanceHubBridge==='function')enhanceHubBridge();", shell)
        source = (ROOT / 'web/hub.js').read_text()
        for forbidden in ['localStorage', 'sessionStorage', 'setInterval', 'setTimeout', 'navigator.clipboard', 'fetch(']:
            self.assertNotIn(forbidden, source)
        self.assertIn('type="password" autocomplete="off"', source)
        self.assertIn("byId('hub-token').value = '';", source)
        self.assertIn('textContent = hubSession.pending ? JSON.stringify', source)

    def test_async_consent_disconnect_and_retry_flows(self):
        source = (ROOT / 'web/hub.js').read_text()
        result = subprocess.run(['node', '-'], input=source + r'''
const assert = require('node:assert/strict');
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return {promise, resolve, reject}; };
const tick = () => new Promise(resolve => setImmediate(resolve));
const clone = value => JSON.parse(JSON.stringify(value));
const TOKEN = 'fixture-token-not-real-123456789';
const calls = [];
let response = {status:'ok',data:[]};
const client = async (route, payload) => {
  calls.push({route,payload:clone(payload)});
  if (route.endsWith('/connect')) return {status:'configured',verified:false};
  if (route.endsWith('/disconnect')) return {status:'disconnected'};
  if (route.endsWith('/text-preview')) return {text:payload.text,requires_exact_preview_approval:true,warning:'Review every character'};
  if (response instanceof Error) throw response;
  return response;
};
(async () => {
  const s = new OpenTwinHubSession(client);
  assert.equal(calls.length,0);
  s.review('rooms'); await s.send(true); await s.connect(TOKEN,false);
  assert.equal(calls.length,0,'Off or missing consent must do nothing');
  await s.connect(TOKEN,true);
  assert.equal(calls.length,1,'Connecting must not read the Hub');
  assert.equal(calls[0].payload.token,TOKEN,'Queued configuration must retain token until dispatch');
  assert.equal(s.connection,'configured'); assert.equal(s.verified,false);
  s.review('rooms'); await s.send(false); assert.equal(calls.length,1);
  s.cancelReview(); await s.send(true); assert.equal(calls.length,1);
  response = {status:'ok',data:[{id:'room_1',title:'Private room',owner:'do-not-cache'}, {id:'../bad',title:'Invalid'}]};
  s.review('rooms'); await s.send(true);
  assert.deepEqual(s.rooms,[{id:'room_1',title:'Private room'}]); assert.equal(s.verified,true);
  s.selectRoom('room_1'); s.events=[{seq:1,text:'PRIVATE'}];
  response={status:'ok',data:[]}; s.review('rooms'); await s.send(true);
  assert.equal(s.room,null); assert.equal(s.events.length,0,'Lost membership on room refresh must clear prior private events');
  response={status:'ok',data:[{id:'room_1',title:'Private room'}]}; s.review('rooms'); await s.send(true);
  s.selectRoom('room_1'); s.updateDraft('Only my selected text');
  await s.review('send'); const original=clone(s.pending);
  response = new Error('RAW_SECRET_MUST_NOT_RENDER');
  const sending=s.send(true); s.updateDraft('Later edit'); await sending;
  assert.equal(calls.at(-1).payload.payload.text,'Only my selected text','Reviewed body must be frozen');
  assert.equal(s.rooms.length,0); assert.equal(s.room,null); assert.equal(s.pending,null);
  assert(!s.message.includes('RAW_SECRET')); assert.equal(s.draft,'Later edit');
  s.review('retry');
  assert.deepEqual(s.pending.payload,original.payload,'Unknown retries must preserve exact text and request ID');
  response={status:'ok',data:{seq:1}}; await s.send(true);
  assert.deepEqual(calls.at(-1).payload.payload,original.payload); assert.equal(s.uncertainSend,null);
  assert.equal(s.draft,'Later edit','Confirmed old send must not erase newer draft');
  for (const status of [403,404,401]) {
    s.rooms=[{id:'room_1',title:'SECRET'}]; s.room=s.rooms[0]; s.events=[{seq:1,text:'SECRET'}];
    response={status:'failed',http_status:status,clear_private_views:true};
    s.review('rooms'); await s.send(true);
    assert.equal(s.rooms.length,0); assert.equal(s.events.length,0); assert.equal(s.room,null); assert.equal(s.busy,false);
  }
  assert.equal(s.connection,'off'); assert.equal(s.verified,false);
  await s.connect(TOKEN,true);
  response={status:'ok',data:[{id:'listing',label:'Shared Twin',category:'coding',profile:'PRIVATE',owner:'PRIVATE'}]};
  s.review('public'); await s.send(true);
  assert.deepEqual(s.publicListings,[{id:'listing',label:'Shared Twin',category:'coding'}]);
  assert.equal(s.verified,false,'Public projection must not verify auth');
  s.dismiss(); assert.equal(s.publicListings.length,0); assert.equal(s.pending,null);
  await s.disconnect(); assert.equal(s.connection,'off'); assert.equal(s.draft,'Later edit');

  // An in-flight private response must not reappear after Close or Disconnect.
  for (const action of ['dismiss','disconnect']) {
    const pending=deferred(); let count=0;
    const c=new OpenTwinHubSession((route) => {
      count++;
      if (route.endsWith('/connect')) return Promise.resolve({status:'configured'});
      if (route.endsWith('/disconnect')) return Promise.resolve({status:'disconnected'});
      return pending.promise;
    });
    await c.connect(TOKEN,true); c.review('rooms'); const request=c.send(true); const double=c.send(true);
    assert.equal(count,2,'Repeated Send must not dispatch twice');
    await c[action](); pending.resolve({status:'ok',data:[{id:'private',title:'LATE SECRET'}]}); await request; await double;
    assert.equal(c.rooms.length,0); assert.equal(c.pending,null);
  }
  // Closing during Connect queues Disconnect after Connect; no secret remains configured.
  const pendingConnect=deferred(); const sequence=[];
  const c=new OpenTwinHubSession(async route => {
    sequence.push(route);
    if (route.endsWith('/connect')) return pendingConnect.promise;
    return {status:'disconnected'};
  });
  const connecting=c.connect(TOKEN,true); await tick();
  const closing=c.dismiss(); assert.equal(c.connection,'disconnecting');
  pendingConnect.resolve({status:'configured'}); await connecting; await closing;
  assert.deepEqual(sequence,['/api/zoo/hub/connect','/api/zoo/hub/disconnect']); assert.equal(c.connection,'off');
  // Closing during an existing disconnect must not suppress its final status.
  const pendingDisconnect=deferred();
  const d=new OpenTwinHubSession(route => route.endsWith('/connect') ? Promise.resolve({status:'configured'}) : pendingDisconnect.promise);
  await d.connect(TOKEN,true); const disconnecting=d.disconnect(); d.dismiss();
  pendingDisconnect.resolve({status:'disconnected'}); await disconnecting; assert.equal(d.connection,'off');
  // A rejected disconnect never claims its server token was removed.
  const e=new OpenTwinHubSession(async () => { throw new Error('offline'); });
  await e.disconnect(); assert.equal(e.connection,'uncertain'); assert(e.message.includes('unconfirmed'));
  assert.equal(hubEscape('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  console.log('Hub async UI contracts passed');
})().catch(error => { console.error(error); process.exit(1); });
''', text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


    def test_sanitized_preview_is_exact_opt_in_and_race_safe(self):
        source = (ROOT / 'web/hub.js').read_text()
        result = subprocess.run(['node', '-'], input=source + r"""
const assert = require('node:assert/strict');
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve=yes; reject=no; }); return {promise,resolve,reject}; };
const clone = value => JSON.parse(JSON.stringify(value));
const make = (call) => { const s=new OpenTwinHubSession(call); s.connection='configured'; s.rooms=[{id:'fixture',title:'Chosen room'}]; s.selectRoom('fixture'); return s; };
(async () => {
  const calls=[];
  const secret='sk-or-v1-'+'x'.repeat(40);
  const s=make(async (route,data) => {
    calls.push({route,data:clone(data)});
    if (route.endsWith('text-preview')) return {text:'Keep [REDACTED]',requires_exact_preview_approval:true,warning:'Automatic redaction cannot identify every private fact.'};
    if (route.endsWith('context-preview')) return {text:'{"documents":[{"text":"Only chosen [REDACTED]"}],"decisions":[]}',requires_exact_preview_approval:true,warning:'Check all selected prose.'};
    return {status:'ok',data:{seq:1}};
  });
  s.updateDraft('Keep '+secret); await s.review('send');
  assert.equal(calls.length,1); assert.equal(calls[0].route,'/api/zoo/hub/text-preview');
  assert.equal(calls[0].data.text,'Keep '+secret,'Only local preview receives raw text');
  assert.equal(s.pending.payload.text,'Keep [REDACTED]');
  assert(!JSON.stringify(s.pending).includes(secret),'Raw secret must not survive in request preview metadata');
  assert(s.pending.warning.includes('cannot identify'));
  await s.send(false); assert.equal(calls.length,1,'Sanitization does not grant send consent');
  const exact=clone(s.pending.payload); await s.send(true);
  assert.equal(calls[1].route,'/api/zoo/hub/request'); assert.deepEqual(calls[1].data.payload,exact);
  assert.equal(s.draft,'','Successful sanitized send clears only the unchanged original draft');

  const before=calls.length;
  await s.review('context',{project_id:'p',document_ids:[],decision_ids:[]});
  assert.equal(calls.length,before,'No automatic whole-project selection');
  const selected={project_id:'p',document_ids:['chosen'],decision_ids:[]};
  s.updateDraft('An unrelated unsent draft'); await s.review('context',selected);
  assert.deepEqual(calls.at(-1).data,selected); assert.equal(calls.at(-1).route,'/api/zoo/hub/context-preview');
  assert(s.pending.audience.includes('current and future members'));
  assert(s.pending.audience.includes('explicitly selected'));
  assert.equal(s.pending.source,'context');
  const contextPayload=clone(s.pending.payload); await s.send(true);
  assert.deepEqual(calls.at(-1).data.payload,contextPayload);
  assert.equal(s.draft,'An unrelated unsent draft','Context sends never erase freeform work');

  for (const action of ['cancel','edit','close','disconnect']) {
    const pending=deferred(); const seen=[];
    const c=make((route,data) => { seen.push(route); return route.endsWith('/disconnect') ? Promise.resolve({status:'disconnected'}) : pending.promise; });
    c.updateDraft('Before edit '+secret); const preview=c.review('send');
    assert(c.previewing && c.busy); assert.equal(c.pending,null);
    await c.send(true); assert.equal(seen.length,1,'Cannot send an unfinished local preview');
    if(action==='cancel') c.cancelReview();
    if(action==='edit') c.updateDraft('Newer draft');
    if(action==='close') c.dismiss();
    if(action==='disconnect') await c.disconnect();
    pending.resolve({text:'LATE [REDACTED]',requires_exact_preview_approval:true}); await preview;
    assert.equal(c.pending,null,'Stale sanitized text must not reappear after '+action);
    assert.equal(c.previewing,false); assert.equal(c.busy,false);
    assert(!seen.includes('/api/zoo/hub/request'));
  }
  // Selecting context or editing draft after preview cancels the prior approval.
  await s.review('send'); s.updateDraft('New content'); await s.send(true);
  assert.equal(s.pending,null); assert.equal(calls.at(-1).route,'/api/zoo/hub/text-preview');
  // Failure or invalid shape must never fall back to unsanitized send.
  for(const bad of [null,{text:'safe'}, {text:secret,requires_exact_preview_approval:false}]) {
    const c=make(async()=>bad);c.updateDraft(secret);await c.review('send');assert.equal(c.pending,null);assert.equal(c.busy,false);
    assert(!c.message.includes(secret));
  }
  const c=make(async()=>{throw new Error(secret);}); c.updateDraft(secret); await c.review('send');
  assert.equal(c.pending,null); assert(!c.message.includes(secret));
  console.log('Sanitized preview selection, exact body, consent and race contracts passed');
})().catch(error=>{console.error(error);process.exit(1);});
""", text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
