from __future__ import annotations

import asyncio
import uuid
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from resume_agent.utils.logger import setup_logger

setup_logger()



_ws_clients: dict[str, list[WebSocket]] = defaultdict(list)


async def broadcast(run_id: str, event: dict) -> None:
    dead: list[WebSocket] = []

    for ws in _ws_clients[run_id]:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)

    for ws in dead:
        _ws_clients[run_id].remove(ws)

app = FastAPI(
    title="Resume Agent API",
    description="Autonomous job application agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_TAILORED_DIR = Path("output/tailored")
_TAILORED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/tailored", StaticFiles(directory=str(_TAILORED_DIR)), name="tailored")



class RunRequest(BaseModel):
    resume_path: str
    dry_run: bool = False
    max_applications: int = 20
    min_relevance_score: Optional[float] = None
    results_per_platform: Optional[int] = None
    job_location: Optional[str] = None
    job_type: Optional[str] = None
    use_linkedin: Optional[bool] = None
    use_internshala: Optional[bool] = None
    use_naukri: Optional[bool] = None
    use_wellfound: Optional[bool] = None
    linkedin_email: Optional[str] = None
    linkedin_password: Optional[str] = None
    internshala_email: Optional[str] = None
    internshala_password: Optional[str] = None
    naukri_email: Optional[str] = None
    naukri_password: Optional[str] = None
    wellfound_email: Optional[str] = None
    wellfound_password: Optional[str] = None
    headless: Optional[bool] = None
    browser_slow_mo: Optional[int] = None


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ApplicationOut(BaseModel):
    job_title: str
    company: str
    job_url: str
    platform: str
    status: str
    relevance_score: float
    applied_at: Optional[str] = None
    error: Optional[str] = None
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str


def _app_to_out(app_result) -> ApplicationOut:
    return ApplicationOut(
        job_title=app_result.job.title,
        company=app_result.job.company,
        job_url=app_result.job.url,
        platform=app_result.job.platform.value,
        status=app_result.status.value,
        relevance_score=app_result.job.relevance_score,
        applied_at=(
            app_result.applied_at.isoformat() if app_result.applied_at else None
        ),
        error=app_result.error,
        notes=app_result.notes,
    )


_ALLOWED_EXTENSIONS = {".md", ".pdf", ".docx"}

_UPLOAD_DIR = Path("output/resumes")


@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)) -> JSONResponse:
    """Accept a resume file upload and save it to output/resumes/.

    Returns the server-side path the frontend should pass to POST /run.
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {_ALLOWED_EXTENSIONS}",
        )

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / file.filename

    content = await file.read()
    dest.write_bytes(content)

    saved_path = str(dest)
    logger.info(f"[API] Resume uploaded: {saved_path} ({len(content)} bytes)")
    return JSONResponse({"path": saved_path, "filename": file.filename})


@app.post("/run", response_model=RunResponse)
async def start_run(request: RunRequest) -> RunResponse:
    path = Path(request.resume_path)
    if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{path.suffix}'. Allowed: {_ALLOWED_EXTENSIONS}",
        )
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Resume file not found: {request.resume_path}",
        )

    run_id = str(uuid.uuid4())

    from resume_agent.graph.pipeline import run_pipeline
    from resume_agent.core.config import settings as _base_settings
    from resume_agent.core.models import JobType

    overrides: dict = {}
    if request.min_relevance_score  is not None: overrides["MIN_RELEVANCE_SCORE"]  = request.min_relevance_score
    if request.results_per_platform is not None: overrides["RESULTS_PER_PLATFORM"] = request.results_per_platform
    if request.job_location         is not None: overrides["JOB_LOCATION"]          = request.job_location
    if request.job_type             is not None:
        try:
            overrides["JOB_TYPE"] = JobType(request.job_type)
        except ValueError:
            pass  
    if request.use_linkedin    is not None: overrides["USE_LINKEDIN"]    = request.use_linkedin
    if request.use_internshala is not None: overrides["USE_INTERNSHALA"] = request.use_internshala
    if request.use_naukri      is not None: overrides["USE_NAUKRI"]      = request.use_naukri
    if request.use_wellfound   is not None: overrides["USE_WELLFOUND"]   = request.use_wellfound
    if request.linkedin_email      : overrides["LINKEDIN_EMAIL"]      = request.linkedin_email
    if request.linkedin_password   : overrides["LINKEDIN_PASSWORD"]   = request.linkedin_password
    if request.internshala_email   : overrides["INTERNSHALA_EMAIL"]   = request.internshala_email
    if request.internshala_password: overrides["INTERNSHALA_PASSWORD"]= request.internshala_password
    if request.naukri_email        : overrides["NAUKRI_EMAIL"]        = request.naukri_email
    if request.naukri_password     : overrides["NAUKRI_PASSWORD"]     = request.naukri_password
    if request.wellfound_email     : overrides["WELLFOUND_EMAIL"]     = request.wellfound_email
    if request.wellfound_password  : overrides["WELLFOUND_PASSWORD"]  = request.wellfound_password
    if request.headless        is not None: overrides["HEADLESS"]         = request.headless
    if request.browser_slow_mo is not None: overrides["BROWSER_SLOW_MO"]  = request.browser_slow_mo

    # Apply overrides by mutating the singleton settings object for this run.
    # FastAPI runs each request in the same process, so we store originals and
    # restore them after the run to avoid cross-run contamination.
    original_values = {k: getattr(_base_settings, k) for k in overrides}
    for k, v in overrides.items():
        object.__setattr__(_base_settings, k, v)
    logger.info(f"[API] Settings overrides applied: {list(overrides.keys())}")

    async def _run() -> None:
        try:
            await run_pipeline(
                resume_path=request.resume_path,
                dry_run=request.dry_run,
                max_applications=request.max_applications,
                run_id=run_id,
                emit=broadcast,
            )
        except Exception as e:
            logger.error(f"[API] Background pipeline error: {e}")
            await broadcast(run_id, {"type": "error", "message": str(e)})
        finally:
            for k, v in original_values.items():
                object.__setattr__(_base_settings, k, v)
            logger.info(f"[API] Settings restored to defaults after run {run_id}")

    asyncio.create_task(_run())
    logger.info(f"[API] Pipeline started — run_id: {run_id}, resume: {request.resume_path}")
    return RunResponse(run_id=run_id, status="started", message="Agent is running in background")


@app.get("/status", response_model=list[ApplicationOut])
async def get_status() -> list[ApplicationOut]:
    from resume_agent.db.repository import get_all_applications

    applications = await get_all_applications()
    return [_app_to_out(a) for a in applications]


@app.delete("/applications", response_model=dict)
async def clear_applications() -> dict:
    from resume_agent.db.repository import clear_all_applications

    count = await clear_all_applications()
    return {"deleted": count}


@app.get("/status/{platform}", response_model=list[ApplicationOut])
async def get_status_by_platform(platform: str) -> list[ApplicationOut]:
    from resume_agent.db.repository import get_all_applications

    applications = await get_all_applications()
    filtered = [a for a in applications if a.job.platform.value == platform.lower()]
    if not filtered and platform.lower() not in {"linkedin", "internshala", "naukri", "wellfound"}:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")
    return [_app_to_out(a) for a in filtered]


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


# ── Sessions ──────────────────────────────────────────────────────────────────

_interactive_sessions = {}

PLATFORM_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "naukri": "https://www.naukri.com/nlogin/login",
    "internshala": "https://internshala.com/",
    "wellfound": "https://wellfound.com/login",
}

@app.post("/sessions/{platform}/login_start")
async def start_interactive_login(platform: str) -> dict:
    if platform not in PLATFORM_URLS:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
        
    if platform in _interactive_sessions:
        # Close existing if any
        obj = _interactive_sessions[platform]
        try:
            await obj["browser"].close()
            await obj["p"].stop()
        except:
            pass
            
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=False, 
        slow_mo=200, 
        channel="chrome",
        args=["--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"]
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
    )
    
    # Stealth: Hide webdriver flag so platforms don't immediately block us with captchas
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    page = await context.new_page()
    
    _interactive_sessions[platform] = {
        "p": p,
        "browser": browser,
        "context": context
    }
    
    await page.goto(PLATFORM_URLS[platform])
    return {"status": "started"}

@app.post("/sessions/{platform}/login_finish")
async def finish_interactive_login(platform: str) -> dict:
    obj = _interactive_sessions.get(platform)
    if not obj:
        raise HTTPException(status_code=400, detail="No interactive session running for this platform.")
        
    sessions_dir = Path("sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_path = sessions_dir / f"{platform}_session.json"
    
    try:
        await obj["context"].storage_state(path=str(session_path))
    finally:
        await obj["browser"].close()
        await obj["p"].stop()
        del _interactive_sessions[platform]
        
    logger.info(f"[API] Interactive session saved for {platform}")
    return {"status": "saved"}

@app.post("/sessions/{platform}/login_cancel")
async def cancel_interactive_login(platform: str) -> dict:
    obj = _interactive_sessions.get(platform)
    if obj:
        try:
            await obj["browser"].close()
            await obj["p"].stop()
        finally:
            del _interactive_sessions[platform]
    return {"status": "cancelled"}


from fastapi import Body

@app.post("/sessions/{platform}")
async def save_session(platform: str, payload: Any = Body(...)) -> dict:
    valid_platforms = {"linkedin", "naukri", "internshala", "wellfound"}
    if platform not in valid_platforms:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform}")
    
    sessions_dir = Path("sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    session_path = sessions_dir / f"{platform}_session.json"
    with open(session_path, "w") as f:
        json.dump(payload, f, indent=2)
        
    logger.info(f"[API] Manual session saved for {platform}")
    return {"status": "saved", "platform": platform}


@app.get("/sessions/{platform}")
async def get_session_status(platform: str) -> dict:
    session_path = Path("sessions") / f"{platform}_session.json"
    exists = session_path.exists()
    return {"platform": platform, "exists": exists}


@app.delete("/sessions/{platform}")
async def delete_session(platform: str) -> dict:
    session_path = Path("sessions") / f"{platform}_session.json"
    if session_path.exists():
        session_path.unlink()
        logger.info(f"[API] Manual session deleted for {platform}")
    return {"status": "deleted", "platform": platform}


@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str) -> None:

    await websocket.accept()      
    _ws_clients[run_id].append(websocket)
    logger.info(f"[WS] Client connected  — run_id: {run_id}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected — run_id: {run_id}")
    finally:
        if websocket in _ws_clients[run_id]:
            _ws_clients[run_id].remove(websocket)
