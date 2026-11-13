"""Opt-in local Hub adapter. No network, discovery or credentials at import."""
import json,re,threading
from shared_context import sanitize_shared_text
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError
BASE='http://127.0.0.1:18765'
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**k):raise ValueError('Hub redirects blocked')
def transport(method,path,body,token):
    headers={'Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    if body is not None:headers['Content-Type']='application/json'
    req=Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=3) as r:
            raw=r.read(262145)
        if len(raw)>262144:raise ValueError('Hub response too large')
        return 200,json.loads(raw)
    except HTTPError as e:
        status=e.code;e.close();return status,None

ID=r'[A-Za-z0-9_-]{1,128}'
READ=re.compile(r'/v1/(?:rooms|zoo(?:/'+ID+r'(?:/(?:blueprint|profile|telemetry))?)?|rooms/'+ID+r'/(?:members|zoo|events(?:\?after=[0-9]{1,18})?))\Z')
WRITE=re.compile(r'/v1/rooms(?:/'+ID+r'/(?:events|members|zoo))?\Z')
FIELDS={'rooms':{'title'},'members':{'user'},'events':{'text','request_id','telemetry'},'zoo':{'category','blueprint','profile','public','share_blueprint','share_profile','telemetry','share_telemetry'}}
class HubClient:
    def __init__(self,send=None):
        self.send=send or transport;self.token=None;self.enabled=False;self.generation=0;self.lock=threading.Lock()
    def disconnect(self):
        with self.lock:self.token=None;self.enabled=False;self.generation+=1
        return {'status':'disconnected','mode':'local_only'}
    def connect(self,d):
        # Fixed destination only; reject hidden URL overrides and unintended fields.
        if set(d)!={'consent','token'} or d.get('consent') is not True:raise ValueError('Explicit local Hub connection consent required')
        token=d.get('token')
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_.~-]{20,512}',token):raise ValueError('Invalid Hub token format')
        with self.lock:self.token=token;self.enabled=True;self.generation+=1
        return {'status':'configured','verified':False,'destination':BASE,'storage':'session_memory'}
    def request(self,d):
        if set(d)-{'consent','method','path','payload'} or d.get('consent') is not True:raise ValueError('Explicit request consent required')
        method=d.get('method');path=d.get('path');payload=d.get('payload')
        if not isinstance(path,str):raise ValueError('Invalid Hub route')
        if method=='GET':
            if not READ.fullmatch(path) or payload is not None:raise ValueError('Invalid Hub read')
        elif method in ('POST','DELETE'):
            if not WRITE.fullmatch(path) or not isinstance(payload,dict):raise ValueError('Invalid Hub write')
            kind=path.rsplit('/',1)[-1]
            if method=='DELETE' and kind!='members':raise ValueError('Invalid Hub delete')
            if set(payload)-FIELDS[kind]:raise ValueError('Unexpected shared fields')
            for field,allowed in [('profile',{'owner_name','owner_handle','owner_bio','owner_avatar','display_name'}),('telemetry',{'cloud_region','edge_pop_iata','country_code','inference_latency_ms'})]:
                if field in payload and (not isinstance(payload[field],dict) or set(payload[field])-allowed):raise ValueError('Unexpected nested shared fields')
            if len(json.dumps(payload).encode())>16384:raise ValueError('Shared payload too large')
            if kind=='events':
                if not isinstance(payload.get('request_id'),str):raise ValueError('Stable request_id required')
                if sanitize_shared_text(payload.get('text'))!=payload['text']:raise ValueError('Sensitive token detected. Create and approve a sanitized text preview before sharing.')
        else:raise ValueError('Invalid Hub method')
        with self.lock:
            if not self.enabled:raise ValueError('Hub is disconnected')
            token=self.token;generation=self.generation
        # Do not forward provider keys, local session token, Origin, or arbitrary headers.
        try:status,result=self.send(method,path,payload,token)
        except Exception:raise ValueError('Hub request failed. Outcome may be unknown; no automatic retry.') from None
        with self.lock:
            if generation!=self.generation:raise ValueError('Hub connection changed. Response discarded; write outcome may be unknown.')
            if status==401:self.token=None;self.enabled=False;self.generation+=1
        if status!=200:return {'status':'failed','http_status':status,'clear_private_views':status in (401,403,404),'retry_automatically':False}
        return {'status':'ok','data':result,'destination':BASE}
