from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

from resume_agent.utils.logger import setup_logger

setup_logger()

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


# ── Request / Response schemas ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    resume_path: str
    dry_run: bool = False
    max_applications: int = 20


class RunResponse(BaseModel):
    status: str
    message: str


class ApplicationOut(BaseModel):
    job_title: str
    company: str
    platform: str
    status: str
    relevance_score: float
    applied_at: Optional[str] = None
    error: Optional[str] = None
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Helper ─────────────────────────────────────────────────────────────────────

def _app_to_out(app_result) -> ApplicationOut:  # type: ignore[no-untyped-def]
    return ApplicationOut(
        job_title=app_result.job.title,
        company=app_result.job.company,
        platform=app_result.job.platform.value,
        status=app_result.status.value,
        relevance_score=app_result.job.relevance_score,
        applied_at=(
            app_result.applied_at.isoformat() if app_result.applied_at else None
        ),
        error=app_result.error,
        notes=app_result.notes,
    )


# ── Routes ─────────────────────────────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {".md", ".pdf", ".docx"}


@app.post("/run", response_model=RunResponse)
async def start_run(request: RunRequest) -> RunResponse:
    """Launch the full agent pipeline in the background."""
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

    from resume_agent.graph.pipeline import run_pipeline

    async def _run() -> None:
        try:
            await run_pipeline(
                resume_path=request.resume_path,
                dry_run=request.dry_run,
                max_applications=request.max_applications,
            )
        except Exception as e:
            logger.error(f"[API] Background pipeline error: {e}")

    asyncio.create_task(_run())
    logger.info(f"[API] Pipeline started for resume: {request.resume_path}")
    return RunResponse(status="started", message="Agent is running in background")


@app.get("/status", response_model=list[ApplicationOut])
async def get_status() -> list[ApplicationOut]:
    """Return all recorded job applications."""
    from resume_agent.db.repository import get_all_applications

    applications = await get_all_applications()
    return [_app_to_out(a) for a in applications]


@app.get("/status/{platform}", response_model=list[ApplicationOut])
async def get_status_by_platform(platform: str) -> list[ApplicationOut]:
    """Return applications filtered by platform."""
    from resume_agent.db.repository import get_all_applications

    applications = await get_all_applications()
    filtered = [a for a in applications if a.job.platform.value == platform.lower()]
    if not filtered and platform.lower() not in {"linkedin", "internshala", "naukri", "wellfound"}:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")
    return [_app_to_out(a) for a in filtered]


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version="0.1.0")
