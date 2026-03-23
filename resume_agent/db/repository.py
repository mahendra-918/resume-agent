from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import aiosqlite
from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.models import (
    ApplicationResult,
    ApplicationStatus,
    Job,
    JobType,
    Platform,
)


# ── Schema ─────────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title       TEXT    NOT NULL,
    company         TEXT    NOT NULL,
    job_url         TEXT    NOT NULL,
    platform        TEXT    NOT NULL,
    job_type        TEXT    NOT NULL,
    location        TEXT,
    relevance_score REAL    DEFAULT 0.0,
    matched_skills  TEXT,
    missing_skills  TEXT,
    status          TEXT    NOT NULL,
    applied_at      TEXT,
    resume_pdf_path TEXT,
    resume_docx_path TEXT,
    error           TEXT,
    notes           TEXT
)
"""


async def init_db() -> None:
    """Create the applications table if it does not exist."""
    import os
    import pathlib

    pathlib.Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(_CREATE_TABLE)
        await db.commit()
    logger.debug(f"[DB] Initialised database at {settings.DB_PATH}")


# ── Write ──────────────────────────────────────────────────────────────────────

async def save_application(result: ApplicationResult) -> None:
    """Persist an ApplicationResult to the database."""
    await init_db()
    job = result.job

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO applications (
                job_title, company, job_url, platform, job_type, location,
                relevance_score, matched_skills, missing_skills,
                status, applied_at, resume_pdf_path, resume_docx_path, error, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.title,
                job.company,
                job.url,
                job.platform.value,
                job.job_type.value,
                job.location,
                job.relevance_score,
                json.dumps(job.matched_skills),
                json.dumps(job.missing_skills),
                result.status.value,
                result.applied_at.isoformat() if result.applied_at else None,
                result.resume_pdf_path,
                result.resume_docx_path,
                result.error,
                result.notes,
            ),
        )
        await db.commit()
    logger.debug(f"[DB] Saved application: {job.title} @ {job.company} — {result.status}")


# ── Read ───────────────────────────────────────────────────────────────────────

def _row_to_result(row: aiosqlite.Row) -> ApplicationResult:
    job = Job(
        title=row["job_title"],
        company=row["company"],
        url=row["job_url"],
        platform=Platform(row["platform"]),
        job_type=JobType(row["job_type"]),
        location=row["location"],
        description="",
        relevance_score=row["relevance_score"] or 0.0,
        matched_skills=json.loads(row["matched_skills"] or "[]"),
        missing_skills=json.loads(row["missing_skills"] or "[]"),
    )
    applied_at: Optional[datetime] = None
    if row["applied_at"]:
        try:
            applied_at = datetime.fromisoformat(row["applied_at"])
        except ValueError:
            pass

    return ApplicationResult(
        job=job,
        status=ApplicationStatus(row["status"]),
        applied_at=applied_at,
        resume_pdf_path=row["resume_pdf_path"],
        resume_docx_path=row["resume_docx_path"],
        error=row["error"],
        notes=row["notes"],
    )


async def get_all_applications() -> list[ApplicationResult]:
    """Return all saved applications ordered by most recent first."""
    await init_db()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM applications ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()
    results = [_row_to_result(r) for r in rows]
    logger.debug(f"[DB] Fetched {len(results)} applications")
    return results


async def get_by_platform(platform: str) -> list[ApplicationResult]:
    """Return applications for a specific platform."""
    await init_db()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM applications WHERE platform = ? ORDER BY id DESC",
            (platform.lower(),),
        ) as cursor:
            rows = await cursor.fetchall()
    results = [_row_to_result(r) for r in rows]
    logger.debug(f"[DB] Fetched {len(results)} applications for platform: {platform}")
    return results
