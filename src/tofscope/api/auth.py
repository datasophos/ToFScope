import hmac
import secrets
import time
from urllib.parse import urlsplit
from fastapi import HTTPException,Request

class Auth:
    def __init__(self,settings,bootstrap_secret=None):self.settings=settings;self.bootstrap_secret=bootstrap_secret or secrets.token_urlsafe(32);self.sessions={}
    def origin(self,request):
        if self.settings.public_origin:return self.settings.public_origin.rstrip('/')
        host='localhost' if self.settings.host=='localhost' else self.settings.host
        return f'http://{host}:{self.settings.port}'
    def validate_origin(self,request,mutation):
        expected=self.origin(request)
        if request.headers.get('host')!=urlsplit(expected).netloc:raise HTTPException(403,'Unexpected host.')
        origin=request.headers.get('origin')
        if origin is not None and origin!=expected:raise HTTPException(403,'Cross-origin request denied.')
        if mutation and origin!=expected:raise HTTPException(403,'Same-origin requests require an Origin header.')
    def owner(self,request:Request):
        mutation=request.method not in ('GET','HEAD','OPTIONS');self.validate_origin(request,mutation)
        if self.settings.mode=='proxy':
            peer=request.client.host if request.client else ''
            if peer not in self.settings.trusted_proxies:raise HTTPException(401,'Untrusted proxy.')
            owner=request.headers.get(self.settings.identity_header,'').strip()
            if not owner or len(owner)>256 or any(ord(c)<32 for c in owner):raise HTTPException(401,'Authenticated identity required.')
            return owner
        if request.headers.get(self.settings.identity_header):raise HTTPException(401,'Proxy identity unavailable in local mode.')
        token=request.cookies.get('tofscope_session','');entry=self.sessions.get(token)
        if entry is None or entry[2]<time.monotonic():raise HTTPException(401,'Open this service with the local launcher.')
        owner,csrf,_=entry
        if mutation and not hmac.compare_digest(request.headers.get('x-csrf-token',''),csrf):raise HTTPException(403,'CSRF token required.')
        return owner
    def exchange(self,request,secret,response):
        self.validate_origin(request,True)
        if self.settings.mode!='local' or self.bootstrap_secret is None or not hmac.compare_digest(secret,self.bootstrap_secret):raise HTTPException(401,'Invalid or consumed bootstrap.')
        self.bootstrap_secret=None;token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);self.sessions[token]=('local',csrf,time.monotonic()+86400)
        response.set_cookie('tofscope_session',token,httponly=True,samesite='strict',secure=self.origin(request).startswith('https:'),max_age=86400)
        return {'owner':'local','csrf':csrf}
