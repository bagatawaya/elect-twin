"""Three real fixture processes: Hub plus two desktop backends. Loopback only."""
import json,os,selectors,subprocess,sys,tempfile,unittest
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parent
HUB=ROOT.parents[1]/'OpenTwinHub-prep'
sys.path.insert(0,str(HUB))
from hub import Hub
class Processes(unittest.TestCase):
 def start(self,code,cwd,args):
  p=subprocess.Popen([sys.executable,'-u','-c',code,*map(str,args)],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env={'PATH':os.environ['PATH'],'PYTHONDONTWRITEBYTECODE':'1'})
  self.processes.append(p)
  with selectors.DefaultSelector() as sel:
   sel.register(p.stdout,selectors.EVENT_READ)
   if not sel.select(8):raise RuntimeError('Fixture startup timeout')
   line=p.stdout.readline()
  if not line:raise RuntimeError('Fixture startup failed: '+p.stderr.read()[:1000])
  return p,int(line)
 def setUp(self):
  self.processes=[];self.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.addCleanup(self.cleanup)
  self.db=Path(self.tmp.name)/'hub.sqlite';h=Hub(str(self.db));self.ta=h.issue('alice');self.tb=h.issue('bob');h.db.close()
  self.hcode="from hub import Hub,Server; import sys; s=Server(('127.0.0.1',int(sys.argv[2])),Hub(sys.argv[1])); print(s.server_address[1],flush=True); s.serve_forever()"
  self.hp,self.port=self.start(self.hcode,HUB,[self.db,0])
  code="import sys,twin,hub_client; hub_client.BASE='http://127.0.0.1:'+sys.argv[2]; s=twin.ThreadingHTTPServer(('127.0.0.1',0),twin.Handler); s.twin=twin.Twin(sys.argv[1]); s.token='fixture-local-token'; s.origin='http://127.0.0.1:'+str(s.server_address[1]); s.hosts={s.origin.split('//')[1]}; print(s.server_address[1],flush=True); s.serve_forever()"
  self.ap,self.a=self.start(code,ROOT,[Path(self.tmp.name)/'alice'/'local.sqlite',self.port])
  self.bp,self.b=self.start(code,ROOT,[Path(self.tmp.name)/'bob'/'local.sqlite',self.port])
  for port,token in [(self.a,self.ta),(self.b,self.tb)]:self.local(port,'connect',{'consent':True,'token':token})
 def cleanup(self):
  for p in reversed(self.processes):
   if p.poll() is None:p.terminate()
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.kill();p.wait()
   p.stdout.close();p.stderr.close()
  self.tmp.cleanup()
 def local(self,port,route,data):
  req=Request('http://127.0.0.1:'+str(port)+'/api/zoo/hub/'+route,data=json.dumps(data).encode(),headers={'X-Twin-Token':'fixture-local-token','Content-Type':'application/json'})
  with urlopen(req,timeout=5) as r:return json.load(r)
 def call(self,port,method,path,payload=None):return self.local(port,'request',dict(consent=True,method=method,path=path,payload=payload))
 def test_privacy_revocation_restart_and_retry(self):
  room=self.call(self.a,'POST','/v1/rooms',{'title':'fixture'})['data']['id'];base='/v1/rooms/'+room
  self.assertEqual(self.call(self.b,'GET',base+'/events')['http_status'],404)
  listing=self.call(self.a,'POST',base+'/zoo',{'public':True,'category':'coding','profile':{'owner_name':'SECRET_OWNER'},'blueprint':'SECRET_BLUEPRINT'})['data']['id']
  public=self.call(self.b,'GET','/v1/zoo')['data'];self.assertEqual(set(public[0]),{'id','label','category'});self.assertNotIn('SECRET',json.dumps(public))
  self.call(self.a,'POST',base+'/members',{'user':'bob'})
  self.assertEqual(self.call(self.b,'GET','/v1/zoo/'+listing+'/profile')['http_status'],404)
  payload={'text':'explicitly selected','request_id':'stable'};first=self.call(self.b,'POST',base+'/events',payload)['data']
  self.hp.terminate();self.hp.wait(timeout=5)
  self.hp,_=self.start(self.hcode,HUB,[self.db,self.port])
  self.local(self.b,'disconnect',{});self.local(self.b,'connect',{'consent':True,'token':self.tb})
  self.assertEqual(self.call(self.b,'POST',base+'/events',payload)['data'],first)
  self.assertEqual(len(self.call(self.a,'GET',base+'/events')['data']),1)
  self.call(self.a,'DELETE',base+'/members',{'user':'bob'})
  self.assertTrue(self.call(self.b,'GET',base+'/events')['clear_private_views'])
  h=Hub(str(self.db));h.revoke('bob');h.db.close()
  self.assertEqual(self.call(self.b,'GET','/v1/rooms')['http_status'],401)
if __name__=='__main__':unittest.main()
