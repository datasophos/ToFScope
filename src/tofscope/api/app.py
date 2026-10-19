from contextlib import asynccontextmanager
from dataclasses import dataclass
import asyncio
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI,Request,Response,Depends,HTTPException,Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
from tofscope import __version__
from tofscope.application.workspaces import WorkspaceService,CapacityError,Conflict
from tofscope.application.explore import ExploreService
from tofscope.application.resources import ResourceBudget
from tofscope.application.cache import ArrayCache
from tofscope.application.jobs import JobService,JobSnapshot,IntegrationSpec
from tofscope.application.lifecycle import LifecycleService,ViewLease
from tofscope.application.models import WorkspaceSnapshot,AnalysisSnapshot
from tofscope.application.commands import CommandEnvelope
from tofscope.storage.acquisitions import AcquisitionRepository,SourceChanged,DatasetBusy
from tofscope.storage.file_browser import list_data_files
from tofscope.api.auth import Auth
from tofscope.api.schemas import *

@dataclass
class Services:
    repository:AcquisitionRepository
    workspaces:WorkspaceService
    explore:ExploreService
    cache:ArrayCache
    jobs:JobService
    lifecycle:LifecycleService
    presenter:object=None
    exports:object=None

def build_services(settings):
    repo=AcquisitionRepository(settings);ws=WorkspaceService(repo,settings);explore=ExploreService(ws,repo);cache=ArrayCache(repo,ResourceBudget(settings));jobs=JobService(ws,explore,cache,settings);life=LifecycleService(ws,jobs,settings)
    return Services(repo,ws,explore,cache,jobs,life)

def create_app(settings,services=None,bootstrap_secret=None):
    @asynccontextmanager
    async def lifespan(app):
        import anyio.to_thread
        anyio.to_thread.current_default_thread_limiter().total_tokens=8
        app.state.services=services or build_services(settings)
        async def sweep():
            while True:
                await asyncio.sleep(5)
                await anyio.to_thread.run_sync(app.state.services.lifecycle.sweep)
        task=asyncio.create_task(sweep())
        try:yield
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
            app.state.services.workspaces.close_all();app.state.services.jobs.shutdown();app.state.services.cache.clear()
    app=FastAPI(title='ToFScope Explore',version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url='/api/v1/openapi.json')
    app.state.auth=Auth(settings,bootstrap_secret)
    def svc(request:Request):return request.app.state.services
    def owner(request:Request):return app.state.auth.owner(request)
    @app.middleware('http')
    async def request_guard(request,call_next):
        if request.method not in ('GET','HEAD'):
            if int(request.headers.get('content-length','0'))>1024*1024:return JSONResponse({'code':'request_too_large','message':'Request exceeds 1 MiB.'},413)
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>1024*1024:return JSONResponse({'code':'request_too_large','message':'Request exceeds 1 MiB.'},413)
            request._body=bytes(body)
        result=await call_next(request)
        result.headers['X-Content-Type-Options']='nosniff';result.headers['Referrer-Policy']='no-referrer';result.headers['Cache-Control']='no-store'
        result.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        return result
    async def error(request,exc):
        status=422;code='invalid_input';message='Invalid request; check the values and acquisition layout.';revision=None
        if isinstance(exc,(KeyError,PermissionError)):status=404;code='not_found';message='Resource unavailable.'
        elif isinstance(exc,CapacityError):status=429;code='capacity';message=str(exc)
        elif isinstance(exc,Conflict):status=409;code='revision_conflict';message=str(exc);revision=exc.revision
        elif isinstance(exc,SourceChanged):status=409;code='source_changed';message=str(exc)
        elif isinstance(exc,DatasetBusy):status=409;code='dataset_busy';message=str(exc)
        elif isinstance(exc,StarletteHTTPException):status=exc.status_code;code={401:'unauthorized',403:'forbidden',404:'not_found'}.get(status,'http_error');message=str(exc.detail)
        return JSONResponse({'code':code,'message':message,'request_id':request.headers.get('x-request-id'),'current_revision':revision},status_code=status)
    for kind in (ValueError,KeyError,PermissionError,RequestValidationError,StarletteHTTPException):app.add_exception_handler(kind,error)
    @app.get('/healthz')
    async def health():return {'status':'ok','version':__version__,'scope':'Explore-only','writes':False}
    @app.get('/readyz')
    async def ready():return {'ready':True,'version':__version__}
    @app.post('/api/v1/auth/bootstrap',response_model=SessionInfo)
    def bootstrap(body:Bootstrap,request:Request,response:Response):return app.state.auth.exchange(request,body.secret,response)
    @app.get('/api/v1/auth/session',response_model=SessionInfo)
    def session(request:Request,o=Depends(owner)):
        entry=app.state.auth.sessions.get(request.cookies.get('tofscope_session',''))
        return {'owner':o,'csrf':entry[1] if entry else ''}
    @app.post('/api/v1/workspaces',response_model=WorkspaceSnapshot)
    def new_workspace(o=Depends(owner),s=Depends(svc)):return s.workspaces.create(o)
    @app.get('/api/v1/workspaces',response_model=list[WorkspaceSnapshot])
    def workspaces(o=Depends(owner),s=Depends(svc)):return s.workspaces.list(o)
    @app.get('/api/v1/workspaces/{wid}',response_model=WorkspaceSnapshot)
    def workspace(wid:str,o=Depends(owner),s=Depends(svc)):return s.workspaces.workspace(o,wid)
    @app.delete('/api/v1/workspaces/{wid}',status_code=204)
    def delete_workspace(wid:str,o=Depends(owner),s=Depends(svc)):s.workspaces.delete_workspace(o,wid)
    @app.post('/api/v1/workspaces/{wid}/analyses',response_model=AnalysisSnapshot)
    def open_analysis(wid:str,body:OpenAcquisition,o=Depends(owner),s=Depends(svc)):
        s.workspaces.workspace(o,wid);dataset=s.repository.open(o,body.relative_path);return s.workspaces.create_analysis(o,wid,dataset)
    @app.get('/api/v1/analyses/{aid}',response_model=AnalysisSnapshot)
    def analysis(aid:str,o=Depends(owner),s=Depends(svc)):return s.workspaces.get(o,aid)
    @app.delete('/api/v1/analyses/{aid}',status_code=204)
    def close(aid:str,o=Depends(owner),s=Depends(svc)):s.workspaces.close(o,aid)
    @app.post('/api/v1/analyses/{aid}/replace',response_model=AnalysisSnapshot)
    def replace_analysis(aid:str,body:ReplaceAcquisition,o=Depends(owner),s=Depends(svc)):
        e=s.workspaces.entry(o,aid);fingerprint=body.model_dump_json()
        with e.lock:
            previous=s.explore.validate_envelope(e,body,fingerprint)
            if previous is not None:return previous
            result=s.workspaces.replace(o,aid,s.repository.open(o,body.relative_path),body.expected_revision);s.explore.receipt(e,body.request_id,fingerprint,result);return result
    @app.post('/api/v1/analyses/{aid}/commands',response_model=AnalysisSnapshot)
    def command(aid:str,body:CommandEnvelope,o=Depends(owner),s=Depends(svc)):return s.explore.apply(o,aid,body)
    @app.post('/api/v1/analyses/{aid}/jobs',response_model=JobSnapshot,status_code=202)
    def job(aid:str,body:SubmitJob,o=Depends(owner),s=Depends(svc)):return s.jobs.submit(o,aid,body,IntegrationSpec(tuple(body.spec.intervals),tuple(body.spec.frames),body.spec.target))
    @app.get('/api/v1/jobs/{jid}',response_model=JobSnapshot)
    def job_status(jid:str,o=Depends(owner),s=Depends(svc)):return s.jobs.get(o,jid)
    @app.post('/api/v1/jobs/{jid}/cancel',response_model=JobSnapshot)
    def cancel(jid:str,o=Depends(owner),s=Depends(svc)):return s.jobs.cancel(o,jid)
    @app.post('/api/v1/analyses/{aid}/views',response_model=ViewLease)
    def attach(aid:str,o=Depends(owner),s=Depends(svc)):return s.lifecycle.attach(o,aid)
    @app.post('/api/v1/views/{vid}/heartbeat',response_model=ViewLease)
    def heartbeat(vid:str,o=Depends(owner),s=Depends(svc)):return s.lifecycle.heartbeat(o,vid)
    @app.delete('/api/v1/views/{vid}',status_code=204)
    def detach(vid:str,o=Depends(owner),s=Depends(svc)):s.lifecycle.detach(o,vid)
    @app.get('/api/v1/files')
    def files(directory:str='',query:str='',offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),o=Depends(owner),s=Depends(svc)):
        return list_data_files(settings,directory,query=query,offset=offset,limit=limit)
    @app.get('/api/v1/{unknown:path}',include_in_schema=False)
    def unknown_api(unknown:str):raise HTTPException(404,'API route unavailable.')
    static=Path(__file__).resolve().parents[1]/'static'
    if (static/'assets').is_dir():app.mount('/assets',StaticFiles(directory=static/'assets'),name='assets')
    @app.get('/',include_in_schema=False)
    def index():
        if not (static/'index.html').exists():raise HTTPException(503,'Build frontend assets first.')
        return FileResponse(static/'index.html')
    return app
