from contextlib import asynccontextmanager
from dataclasses import dataclass
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles
import json
from tofscope import __version__
from tofscope.storage.saved_files import SavedFile
from tofscope.storage.raw_preparation import PreparationPreview
from urllib.parse import quote
import os
from tofscope.application.saves import SaveService
from tofscope.application.analyses import AnalysisService, CapacityError, Conflict
from tofscope.application.explore import ExploreService
from tofscope.application.resources import ResourceBudget
from tofscope.application.cache import ArrayCache
from tofscope.application.jobs import JobService, JobSnapshot, IntegrationSpec
from tofscope.application.lifecycle import LifecycleService, ViewLease
from tofscope.application.models import AnalysisSnapshot
from tofscope.application.signals import image_signal
from tofscope.application.commands import CommandEnvelope
from tofscope.storage.acquisitions import (
    AcquisitionRepository,
    SourceChanged,
    DatasetBusy,
)
from tofscope.storage.file_browser import list_data_files
from tofscope.api.auth import Auth
from tofscope.api.schemas import (
    Bootstrap,
    SessionInfo,
    OpenAcquisition,
    PrepareAcquisition,
    ReplaceAcquisition,
    SubmitJob,
    SaveCopy,
    FolderLocations,
)
from typing import Literal
from tofscope.presentation.data import ExploreData
from tofscope.presentation.explore import ExplorePresenter
from tofscope.presentation.exports import ExportService


@dataclass
class Services:
    repository: AcquisitionRepository
    analyses: AnalysisService
    explore: ExploreService
    cache: ArrayCache
    jobs: JobService
    lifecycle: LifecycleService
    presenter: object = None
    exports: object = None
    saves: object = None
    preparations: object = None


def build_services(settings):
    budget = ResourceBudget(settings)
    repo = AcquisitionRepository(settings, budget=budget)
    ws = AnalysisService(repo, settings)
    explore = ExploreService(ws, repo)
    cache = ArrayCache(repo, budget)

    def prepare(snapshot):
        with cache.load(
            snapshot.owner, snapshot.id, snapshot.dataset, image_signal(snapshot).recipe, materialization_id=image_signal(snapshot).materialization_id
        ):
            pass

    ws.prepare = prepare
    jobs = JobService(ws, explore, cache, settings)
    life = LifecycleService(ws, jobs, settings)
    presenter = ExplorePresenter(ws, repo, cache, settings)
    services = Services(
        repo, ws, explore, cache, jobs, life, presenter, ExportService(presenter), SaveService(ws, jobs, cache, repo, settings)
    )
    from tofscope.application.preparations import PreparationService
    services.preparations = PreparationService(repo, jobs, services.saves.files)
    return services


class ManagedResponse(Response):
    def __init__(self, *args, reservation, **kwargs):
        self.reservation = reservation
        super().__init__(*args, **kwargs)

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.reservation.release()


def create_app(settings, services=None, bootstrap_secret=None):
    @asynccontextmanager
    async def lifespan(app):
        import anyio.to_thread

        anyio.to_thread.current_default_thread_limiter().total_tokens = 8
        app.state.services = services or build_services(settings)

        async def sweep():
            while True:
                await asyncio.sleep(5)
                await anyio.to_thread.run_sync(app.state.services.lifecycle.sweep)

        task = asyncio.create_task(sweep())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            app.state.services.analyses.close_all()
            app.state.services.jobs.shutdown()
            app.state.services.cache.clear()

    app = FastAPI(
        title="ToFScope Explore",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.state.auth = Auth(settings, bootstrap_secret)

    def svc(request: Request):
        return request.app.state.services

    def owner(request: Request):
        return app.state.auth.owner(request)

    @app.middleware("http")
    async def request_guard(request, call_next):
        if request.method not in ("GET", "HEAD"):
            if int(request.headers.get("content-length", "0")) > 1024 * 1024:
                return JSONResponse(
                    {"code": "request_too_large", "message": "Request exceeds 1 MiB."},
                    413,
                )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 1024 * 1024:
                    return JSONResponse(
                        {
                            "code": "request_too_large",
                            "message": "Request exceeds 1 MiB.",
                        },
                        413,
                    )
            request._body = bytes(body)
        result = await call_next(request)
        result.headers["X-Content-Type-Options"] = "nosniff"
        result.headers["Referrer-Policy"] = "no-referrer"
        result.headers["Cache-Control"] = "no-store"
        result.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
        return result

    async def error(request, exc):
        status = 422
        code = "invalid_input"
        message = "Invalid request; check the values and acquisition layout."
        revision = None
        if isinstance(exc, (KeyError, PermissionError)):
            status = 404
            code = "not_found"
            message = "Resource unavailable."
        elif isinstance(exc, CapacityError):
            status = 429
            code = "capacity"
            message = str(exc)
        elif isinstance(exc, Conflict):
            status = 409
            code = "revision_conflict"
            message = str(exc)
            revision = exc.revision
        elif isinstance(exc, SourceChanged):
            status = 409
            code = "source_changed"
            message = str(exc)
        elif isinstance(exc, DatasetBusy):
            status = 409
            code = "dataset_busy"
            message = str(exc)
        elif isinstance(exc, StarletteHTTPException):
            status = exc.status_code
            code = {401: "unauthorized", 403: "forbidden", 404: "not_found"}.get(
                status, "http_error"
            )
            message = str(exc.detail)
        return JSONResponse(
            {
                "code": code,
                "message": message,
                "request_id": request.headers.get("x-request-id"),
                "current_revision": revision,
            },
            status_code=status,
        )

    for kind in (
        ValueError,
        KeyError,
        PermissionError,
        RequestValidationError,
        StarletteHTTPException,
    ):
        app.add_exception_handler(kind, error)

    @app.get("/healthz")
    async def health():
        return {
            "status": "ok",
            "version": __version__,
            "scope": "Explore-only",
            "writes": False,
            "original_writes": False,
            "save_copies": True,
        }

    @app.get("/readyz")
    async def ready():
        if not (
            Path(__file__).resolve().parents[1] / "static" / "manifest.json"
        ).is_file():
            raise HTTPException(503, "Frontend assets are unavailable.")
        return {"ready": True, "version": __version__}

    @app.post("/api/v1/auth/bootstrap", response_model=SessionInfo)
    def bootstrap(body: Bootstrap, request: Request, response: Response):
        return app.state.auth.exchange(request, body.secret, response)

    @app.get("/api/v1/auth/session", response_model=SessionInfo)
    def session(request: Request, o=Depends(owner)):
        entry = app.state.auth.sessions.get(request.cookies.get("tofscope_session", ""))
        return {"owner": o, "csrf": entry[1] if entry else ""}

    @app.get('/api/v1/locations', response_model=FolderLocations)
    def folder_locations(o=Depends(owner), s=Depends(svc)):
        return FolderLocations(acquisitions=str(settings.data_root),
                               saved_copies=str(settings.output_root),
                               save_destination=str(s.saves.files.owner_path(o)))

    @app.post('/api/v1/acquisitions/inspect', response_model=PreparationPreview)
    def inspect_acquisition(body: OpenAcquisition, o=Depends(owner), s=Depends(svc)):
        return s.preparations.inspect(o, body.relative_path, body.location)

    @app.post('/api/v1/acquisitions/prepare', response_model=JobSnapshot, status_code=202)
    def prepare_acquisition(body: PrepareAcquisition, o=Depends(owner), s=Depends(svc)):
        try:
            return s.preparations.submit(o, body.relative_path, body.location, body.generation, body.filename)
        except FileExistsError:
            raise HTTPException(409, 'Output already exists; choose a new name.') from None

    @app.get('/api/v1/analyses', response_model=list[AnalysisSnapshot])
    def open_files(o=Depends(owner), s=Depends(svc)):
        return s.analyses.list(o)

    @app.post('/api/v1/analyses', response_model=AnalysisSnapshot)
    def open_analysis(body: OpenAcquisition, o=Depends(owner), s=Depends(svc)):
        return s.analyses.create_analysis(o, s.repository.open(o, body.relative_path, body.location))

    @app.get("/api/v1/analyses/{aid}", response_model=AnalysisSnapshot)
    def analysis(aid: str, o=Depends(owner), s=Depends(svc)):
        return s.analyses.get(o, aid)

    @app.delete("/api/v1/analyses/{aid}", status_code=204)
    def close(aid: str, expected_revision: int = Query(ge=0), o=Depends(owner), s=Depends(svc)):
        s.analyses.close(o, aid, expected_revision)

    @app.post("/api/v1/analyses/{aid}/replace", response_model=AnalysisSnapshot)
    def replace_analysis(
        aid: str, body: ReplaceAcquisition, o=Depends(owner), s=Depends(svc)
    ):
        s.analyses.get(o, aid)
        e = s.analyses.entry(o, aid)
        fingerprint = body.model_dump_json()
        with e.lock:
            previous = s.explore.validate_envelope(
                e, body, fingerprint, check_source=False
            )
            if previous is not None:
                return previous
            result = s.analyses.replace(
                o, aid, s.repository.open(o, body.relative_path, body.location), body.expected_revision
            )
            s.explore.receipt(e, body.request_id, fingerprint, result)
            return result

    @app.post("/api/v1/analyses/{aid}/commands", response_model=AnalysisSnapshot)
    def command(aid: str, body: CommandEnvelope, o=Depends(owner), s=Depends(svc)):
        return s.explore.apply(o, aid, body)

    @app.post(
        "/api/v1/analyses/{aid}/jobs", response_model=JobSnapshot, status_code=202
    )
    def job(aid: str, body: SubmitJob, o=Depends(owner), s=Depends(svc)):
        return s.jobs.submit(
            o,
            aid,
            body,
            IntegrationSpec(
                tuple(body.spec.intervals), tuple(body.spec.frames), body.spec.name,
                body.spec.signal_id, body.spec.expected_recipe_version
            ),
        )

    @app.post('/api/v1/analyses/{aid}/saves', response_model=JobSnapshot, status_code=202)
    def save_copy(aid: str, body: SaveCopy, o=Depends(owner), s=Depends(svc)):
        return s.saves.submit(o, aid, body, body.filename)

    @app.get('/api/v1/saved-files', response_model=list[SavedFile])
    def saved_files(o=Depends(owner), s=Depends(svc)):
        return s.saves.files.list(o)

    @app.get('/api/v1/saved-files/{fid}/download')
    def download_saved(fid: str, o=Depends(owner), s=Depends(svc)):
        try:
            path = s.saves.files.path(o, fid)
        except FileNotFoundError:
            raise KeyError('Saved file unavailable.') from None
        expected = path.stat()
        reservation = s.cache.budget.reserve(o, 'download:' + fid, 128 * 1024)
        stream = None
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            stream = os.fdopen(descriptor, 'rb')
            actual = os.fstat(descriptor)
            if (expected.st_dev, expected.st_ino, expected.st_size, expected.st_mtime_ns) != (actual.st_dev, actual.st_ino, actual.st_size, actual.st_mtime_ns):
                raise SourceChanged('Saved file changed before download.')
            def chunks():
                while chunk := stream.read(64 * 1024):
                    yield chunk
            class DownloadResponse(StreamingResponse):
                async def __call__(self, scope, receive, send):
                    try:
                        await super().__call__(scope, receive, send)
                    finally:
                        stream.close()
                        reservation.release()
            return DownloadResponse(chunks(), media_type='application/x-hdf5', headers={
                'Content-Length': str(actual.st_size),
                'Content-Disposition': "attachment; filename*=UTF-8''" + quote(path.name),
            })
        except BaseException:
            if stream:
                stream.close()
            reservation.release()
            raise

    @app.get("/api/v1/jobs/{jid}", response_model=JobSnapshot)
    def job_status(jid: str, o=Depends(owner), s=Depends(svc)):
        return s.jobs.get(o, jid)

    @app.post("/api/v1/jobs/{jid}/cancel", response_model=JobSnapshot)
    def cancel(jid: str, o=Depends(owner), s=Depends(svc)):
        return s.jobs.cancel(o, jid)

    @app.post("/api/v1/analyses/{aid}/views", response_model=ViewLease)
    def attach(aid: str, o=Depends(owner), s=Depends(svc)):
        return s.lifecycle.attach(o, aid)

    @app.post("/api/v1/views/{vid}/heartbeat", response_model=ViewLease)
    def heartbeat(vid: str, o=Depends(owner), s=Depends(svc)):
        return s.lifecycle.heartbeat(o, vid)

    @app.delete("/api/v1/views/{vid}", status_code=204)
    def detach(vid: str, o=Depends(owner), s=Depends(svc)):
        s.lifecycle.detach(o, vid)

    @app.get("/api/v1/files")
    def files(
        directory: str = "",
        location: Literal["acquisition", "saved"] = "acquisition",
        query: str = "",
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        o=Depends(owner),
        s=Depends(svc),
    ):
        if location == 'saved':
            if directory:
                raise ValueError('Saved files have no subdirectories.')
            values = [f for f in s.saves.files.list(o) if query.lower() in f.name.lower()]
            entries = [dict(name=f.name, path=f.id, kind='file', size=f.size) for f in values[offset:offset + limit]]
            return dict(path='', entries=entries, total=len(values), next_offset=offset + limit if offset + limit < len(values) else None)
        return list_data_files(
            settings, directory, query=query, offset=offset, limit=limit
        )

    @app.get("/api/v1/analyses/{aid}/data", response_model=ExploreData)
    def data(
        aid: str,
        panels: str = "ion,front,spectrum,profile",
        o=Depends(owner),
        s=Depends(svc),
    ):
        s.analyses.get(o, aid)
        reservation = s.cache.budget.reserve(o, aid, settings.response_bytes)
        try:
            snapshot = s.presenter.snapshot(o, aid, set(panels.split(",")))
            content = json.dumps(
                snapshot.to_dict(), allow_nan=False, separators=(",", ":")
            ).encode()
            return ManagedResponse(
                content,
                media_type="application/json",
                reservation=reservation,
            )
        except BaseException:
            reservation.release()
            raise

    @app.get("/api/v1/analyses/{aid}/exports/{format}")
    def export(
        aid: str, format: Literal["csv", "json"], o=Depends(owner), s=Depends(svc)
    ):
        s.analyses.get(o, aid)
        reservation = s.cache.budget.reserve(o, aid, settings.response_bytes)
        try:
            d = s.exports.render(o, aid, format)
            return ManagedResponse(
                d.content,
                media_type=d.media_type,
                headers={"Content-Disposition": f'attachment; filename="{d.filename}"'},
                reservation=reservation,
            )
        except BaseException:
            reservation.release()
            raise

    @app.get("/api/v1/{unknown:path}", include_in_schema=False)
    def unknown_api(unknown: str):
        raise HTTPException(404, "API route unavailable.")

    static = Path(__file__).resolve().parents[1] / "static"
    if (static / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        if not (static / "index.html").exists():
            raise HTTPException(503, "Build frontend assets first.")
        return FileResponse(static / "index.html")

    return app
