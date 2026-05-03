from __future__ import annotations

import asyncio
import uuid
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.routing import APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from loguru import logger
from pydantic import BaseModel

from resume_agent.utils.logger import setup_logger

setup_logger()


_ws_clients: dict[str, list[WebSocket]] = defaultdict(list)


class _StripApiPrefix(BaseHTTPMiddleware):
    """Strip /api prefix from all incoming requests so the same FastAPI routes
    work whether called directly (dev proxy strips /api) or from production
    (browser sends /api/...). WebSocket paths are excluded."""
    async def dispatch(self, request: Request, call_next):
        path = request.scope["path"]
        if path.startswith("/api/") and not path.startswith("/api/tailored") and not path.startswith("/api/packages-files"):
            request.scope["path"] = path[4:]  # /api/run → /run
        return await call_next(request)


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
app.add_middleware(_StripApiPrefix)

_TAILORED_DIR = Path("output/tailored")
_TAILORED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/tailored", StaticFiles(directory=str(_TAILORED_DIR)), name="tailored")

_PACKAGES_DIR = Path("output/packages")
_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

_FRONTEND_BUILD = Path("frontend/dist")
app.mount("/packages-files", StaticFiles(directory=str(_PACKAGES_DIR)), name="packages")



class RunRequest(BaseModel):
    resume_path: str
    max_applications: int = 20
    min_relevance_score: Optional[float] = None
    results_per_platform: Optional[int] = None
    job_location: Optional[str] = None
    job_type: Optional[str] = None
    use_linkedin: Optional[bool] = None
    use_internshala: Optional[bool] = None
    use_naukri: Optional[bool] = None
    use_wellfound: Optional[bool] = None
    apply_enabled: bool = False


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
    tailored_resume_path: Optional[str] = None


class PackageOut(BaseModel):
    job_title: str
    company: str
    job_url: str
    platform: str
    relevance_score: float
    output_dir: str
    has_cover_letter: bool
    has_email_draft: bool
    has_interview_prep: bool
    generated_at: Optional[str] = None
    error: Optional[str] = None


class TrackingUpdate(BaseModel):
    status: str  # "ready" | "applied" | "phone_screen" | "interview" | "offer" | "rejected"
    notes: Optional[str] = None


class TrackingOut(BaseModel):
    package_dir: str
    job_title: str
    company: str
    platform: str
    relevance_score: float
    job_url: str
    status: str
    notes: str
    generated_at: Optional[str] = None
    has_cover_letter: bool
    has_email_draft: bool
    has_interview_prep: bool
    tailored_resume_path: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str


class LLMConfig(BaseModel):
    llm_provider: str = "groq"   # "groq" | "gemini"
    groq_api_key: str = ""
    gemini_api_key: str = ""


def _package_to_out(pkg) -> PackageOut:
    from pathlib import Path
    out_dir = Path(pkg.output_dir) if pkg.output_dir else None
    return PackageOut(
        job_title=pkg.job.title,
        company=pkg.job.company,
        job_url=pkg.job.url,
        platform=pkg.job.platform.value,
        relevance_score=pkg.job.relevance_score,
        output_dir=pkg.output_dir or "",
        has_cover_letter=(out_dir / "cover_letter.txt").exists() if out_dir else False,
        has_email_draft=(out_dir / "email_draft.txt").exists() if out_dir else False,
        has_interview_prep=(out_dir / "interview_prep.txt").exists() if out_dir else False,
        generated_at=pkg.generated_at.isoformat() if pkg.generated_at else None,
        error=pkg.error,
    )


def _read_tracking(job_dir: Path) -> dict:
    tracking_file = job_dir / "tracking.json"
    if tracking_file.exists():
        return json.loads(tracking_file.read_text())
    return {"status": "ready", "notes": ""}


def _write_tracking(job_dir: Path, status: str, notes: str) -> None:
    tracking_file = job_dir / "tracking.json"
    tracking_file.write_text(json.dumps({"status": status, "notes": notes}, indent=2))


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
                max_applications=request.max_applications,
                apply_enabled=request.apply_enabled,
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
    """Return generated packages as application results for dashboard compatibility."""
    packages_dir = Path("output/packages")
    if not packages_dir.exists():
        return []

    results = []
    for job_dir in sorted(packages_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        readme = job_dir / "README.md"

        job_title, company, platform_str, job_url, score_str, generated_at = (
            "", "", "linkedin", "", "0", None
        )
        missing_skills = []
        in_missing = False
        if readme.exists():
            for line in readme.read_text().splitlines():
                if line.startswith("**Job:**"):       job_title    = line.split("**Job:**")[-1].strip()
                if line.startswith("**Company:**"):   company      = line.split("**Company:**")[-1].strip()
                if line.startswith("**Platform:**"):  platform_str = line.split("**Platform:**")[-1].strip()
                if line.startswith("**Job URL:**"):   job_url      = line.split("**Job URL:**")[-1].strip()
                if line.startswith("**Match Score:**"):
                    score_str = line.split("**Match Score:**")[-1].strip().replace("%", "")
                if line.startswith("**Generated:**"):
                    generated_at = line.split("**Generated:**")[-1].strip()
                if line.strip() == "## Missing Skills to Address":
                    in_missing = True
                    continue
                if in_missing and line.startswith("- "):
                    missing_skills.append(line[2:].strip())
                elif in_missing and line.startswith("##"):
                    in_missing = False

        try:
            score = float(score_str) / 100
        except (ValueError, ZeroDivisionError):
            score = 0.0

        resume_pdf = None
        resume_ref_file = job_dir / "resume_path.txt"
        if resume_ref_file.exists():
            resume_pdf = resume_ref_file.read_text().strip()

        missing_str = ", ".join(missing_skills[:5]) if missing_skills else ""
        notes_value = f"Package ready → {job_dir.name}"
        if missing_str:
            notes_value += f" | Missing: {missing_str}"

        results.append(ApplicationOut(
            job_title=job_title or job_dir.name,
            company=company,
            job_url=job_url,
            platform=platform_str,
            status="generated",
            relevance_score=score,
            applied_at=generated_at,
            notes=notes_value,
            tailored_resume_path=resume_pdf,
        ))

    return results


@app.delete("/applications", response_model=dict)
async def clear_applications() -> dict:
    import shutil
    packages_dir = Path("output/packages")
    count = 0
    if packages_dir.exists():
        for d in packages_dir.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
                count += 1
    logger.info(f"[API] Cleared {count} packages from disk")
    return {"deleted": count}


@app.get("/status/{platform}", response_model=list[ApplicationOut])
async def get_status_by_platform(platform: str) -> list[ApplicationOut]:
    all_results = await get_status()
    filtered = [r for r in all_results if r.platform.lower() == platform.lower()]
    if not filtered and platform.lower() not in {"linkedin", "internshala", "naukri", "wellfound"}:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")
    return filtered


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@app.get("/packages", response_model=list[PackageOut])
async def list_packages() -> list[PackageOut]:
    """List all generated application packages from disk."""
    packages_dir = Path("output/packages")
    if not packages_dir.exists():
        return []

    results = []
    for job_dir in sorted(packages_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        readme = job_dir / "README.md"
        cover = job_dir / "cover_letter.txt"
        email = job_dir / "email_draft.txt"
        prep = job_dir / "interview_prep.txt"

        job_title, company, platform_str, job_url, score_str = "", "", "linkedin", "", "0"
        if readme.exists():
            for line in readme.read_text().splitlines():
                if line.startswith("**Job:**"):       job_title    = line.split("**Job:**")[-1].strip()
                if line.startswith("**Company:**"):   company      = line.split("**Company:**")[-1].strip()
                if line.startswith("**Platform:**"):  platform_str = line.split("**Platform:**")[-1].strip()
                if line.startswith("**Job URL:**"):   job_url      = line.split("**Job URL:**")[-1].strip()
                if line.startswith("**Match Score:**"):
                    score_str = line.split("**Match Score:**")[-1].strip().replace("%", "")

        results.append(PackageOut(
            job_title=job_title or job_dir.name,
            company=company,
            job_url=job_url,
            platform=platform_str,
            relevance_score=float(score_str) / 100 if score_str else 0.0,
            output_dir=str(job_dir),
            has_cover_letter=cover.exists(),
            has_email_draft=email.exists(),
            has_interview_prep=prep.exists(),
        ))
    return results


@app.get("/packages/{package_dir}/{file_name}")
async def get_package_file(package_dir: str, file_name: str) -> JSONResponse:
    """Return the text content of a specific package file."""
    allowed_files = {"cover_letter.txt", "email_draft.txt", "interview_prep.txt", "README.md"}
    if file_name not in allowed_files:
        raise HTTPException(status_code=400, detail=f"File not allowed: {file_name}")

    file_path = Path("output/packages") / package_dir / file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return JSONResponse({"content": file_path.read_text(encoding="utf-8")})


@app.delete("/packages", response_model=dict)
async def clear_packages() -> dict:
    """Delete all generated packages from disk."""
    import shutil
    packages_dir = Path("output/packages")
    count = 0
    if packages_dir.exists():
        for d in packages_dir.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
                count += 1
    return {"deleted": count}


@app.get("/tracking", response_model=list[TrackingOut])
async def get_tracking() -> list[TrackingOut]:
    """Return all packages with their tracking status."""
    packages_dir = Path("output/packages")
    if not packages_dir.exists():
        return []

    results = []
    for job_dir in sorted(packages_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        readme = job_dir / "README.md"
        tracking = _read_tracking(job_dir)

        job_title, company, platform_str, job_url, score_str, generated_at = (
            "", "", "linkedin", "", "0", None
        )
        if readme.exists():
            for line in readme.read_text().splitlines():
                if line.startswith("**Job:**"):        job_title    = line.split("**Job:**")[-1].strip()
                if line.startswith("**Company:**"):    company      = line.split("**Company:**")[-1].strip()
                if line.startswith("**Platform:**"):   platform_str = line.split("**Platform:**")[-1].strip()
                if line.startswith("**Job URL:**"):    job_url      = line.split("**Job URL:**")[-1].strip()
                if line.startswith("**Match Score:**"): score_str   = line.split("**Match Score:**")[-1].strip().replace("%", "")
                if line.startswith("**Generated:**"):  generated_at = line.split("**Generated:**")[-1].strip()

        try:
            score = float(score_str) / 100
        except (ValueError, ZeroDivisionError):
            score = 0.0

        resume_pdf = None
        resume_ref = job_dir / "resume_path.txt"
        if resume_ref.exists():
            resume_pdf = resume_ref.read_text().strip()

        results.append(TrackingOut(
            package_dir=job_dir.name,
            job_title=job_title or job_dir.name,
            company=company,
            platform=platform_str,
            relevance_score=score,
            job_url=job_url,
            status=tracking.get("status", "ready"),
            notes=tracking.get("notes", ""),
            generated_at=generated_at,
            has_cover_letter=(job_dir / "cover_letter.txt").exists(),
            has_email_draft=(job_dir / "email_draft.txt").exists(),
            has_interview_prep=(job_dir / "interview_prep.txt").exists(),
            tailored_resume_path=resume_pdf,
        ))
    return results


@app.patch("/tracking/{package_dir}", response_model=dict)
async def update_tracking(package_dir: str, update: TrackingUpdate) -> dict:
    """Update the tracking status and notes for a package."""
    job_dir = Path("output/packages") / package_dir
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Package not found")
    _write_tracking(job_dir, update.status, update.notes or "")
    return {"status": "updated"}


@app.get("/tracking/{package_dir}", response_model=dict)
async def get_package_tracking(package_dir: str) -> dict:
    """Get tracking status for a single package."""
    job_dir = Path("output/packages") / package_dir
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Package not found")
    return _read_tracking(job_dir)


_ENV_FILE = Path(".env")


def _read_env() -> dict[str, str]:
    """Parse .env file into a dict."""
    env: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(updates: dict[str, str]) -> None:
    """Write key=value pairs into .env, adding or replacing existing values."""
    lines = _ENV_FILE.read_text().splitlines() if _ENV_FILE.exists() else []
    written: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                written.add(k)
                continue
        new_lines.append(line)

    # Append any new keys not already in file
    for k, v in updates.items():
        if k not in written:
            new_lines.append(f"{k}={v}")

    _ENV_FILE.write_text("\n".join(new_lines) + "\n")


@app.get("/config/llm", response_model=LLMConfig)
async def get_llm_config() -> LLMConfig:
    """Return current LLM provider config (keys masked)."""
    from resume_agent.core.config import settings as _s
    groq_key = _s.GROQ_API_KEY or ""
    gemini_key = _s.GEMINI_API_KEY or ""
    return LLMConfig(
        llm_provider=_s.LLM_PROVIDER or "groq",
        # Show only last 6 chars so the UI can display "configured" state
        groq_api_key="••••••" + groq_key[-6:] if len(groq_key) > 6 else ("set" if groq_key else ""),
        gemini_api_key="••••••" + gemini_key[-6:] if len(gemini_key) > 6 else ("set" if gemini_key else ""),
    )


@app.post("/config/llm", response_model=dict)
async def save_llm_config(config: LLMConfig) -> dict:
    """Persist LLM provider and API keys to .env and reload settings."""
    from resume_agent.core.config import settings as _s

    updates: dict[str, str] = {"LLM_PROVIDER": config.llm_provider}

    # Only write the key if the user sent a real value (not our masked placeholder)
    if config.groq_api_key and not config.groq_api_key.startswith("••••••"):
        updates["GROQ_API_KEY"] = config.groq_api_key
    if config.gemini_api_key and not config.gemini_api_key.startswith("••••••"):
        updates["GEMINI_API_KEY"] = config.gemini_api_key

    # Set model to a sensible default for each provider
    if config.llm_provider == "gemini":
        updates["LLM_MODEL"] = "gemini-2.0-flash"
    elif config.llm_provider == "groq":
        updates["LLM_MODEL"] = "llama-3.3-70b-versatile"
    elif config.llm_provider == "ollama":
        updates["LLM_MODEL"] = "llama3.2:3b"

    _write_env(updates)

    # Hot-reload settings singleton so next run picks up new values immediately
    env = _read_env()
    object.__setattr__(_s, "LLM_PROVIDER",    env.get("LLM_PROVIDER",    "groq"))
    object.__setattr__(_s, "LLM_MODEL",        env.get("LLM_MODEL",        _s.LLM_MODEL))
    if "GROQ_API_KEY" in env:
        object.__setattr__(_s, "GROQ_API_KEY",   env.get("GROQ_API_KEY", ""))
    if "GEMINI_API_KEY" in env:
        object.__setattr__(_s, "GEMINI_API_KEY", env.get("GEMINI_API_KEY", ""))

    logger.info(f"[API] LLM config updated → provider={config.llm_provider}")
    return {"status": "saved", "provider": config.llm_provider}


class LinkedInConfig(BaseModel):
    linkedin_email: str = ""
    linkedin_password: str = ""


@app.get("/config/linkedin", response_model=dict)
async def get_linkedin_config() -> dict:
    from resume_agent.core.config import settings as _s
    email = _s.LINKEDIN_EMAIL or ""
    return {
        "linkedin_email": ("set" if email else ""),
        "linkedin_password": ("set" if _s.LINKEDIN_PASSWORD else ""),
    }


@app.post("/config/linkedin", response_model=dict)
async def save_linkedin_config(config: LinkedInConfig) -> dict:
    from resume_agent.core.config import settings as _s
    updates: dict[str, str] = {}
    if config.linkedin_email:
        updates["LINKEDIN_EMAIL"] = config.linkedin_email
    if config.linkedin_password:
        updates["LINKEDIN_PASSWORD"] = config.linkedin_password
    if updates:
        _write_env(updates)
        if config.linkedin_email:
            object.__setattr__(_s, "LINKEDIN_EMAIL", config.linkedin_email)
        if config.linkedin_password:
            object.__setattr__(_s, "LINKEDIN_PASSWORD", config.linkedin_password)
    logger.info("[API] LinkedIn credentials updated")
    return {"status": "saved"}


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


# ── Serve built React frontend (production) ───────────────────────────────────
_ASSETS_DIR = _FRONTEND_BUILD / "assets"
if _ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")


def _serve_index() -> HTMLResponse:
    index = _FRONTEND_BUILD / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text())
    return HTMLResponse("<h1>Resume Agent API is running</h1>")


@app.get("/", include_in_schema=False)
async def serve_root() -> HTMLResponse:
    return _serve_index()


@app.exception_handler(404)
async def spa_fallback(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse:
    """Return the SPA shell for all unmatched paths so client-side routing works.
    API-like paths get a proper JSON 404 instead."""
    _api_prefixes = (
        "/api/", "/ws/", "/health", "/run", "/status",
        "/packages", "/upload", "/config", "/tracking",
        "/tailored", "/packages-files",
    )
    if any(request.url.path.startswith(p) for p in _api_prefixes):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return _serve_index()
