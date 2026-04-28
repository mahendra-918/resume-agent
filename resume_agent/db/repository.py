from __future__ import annotations
import datetime
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from resume_agent.core.config import settings
from resume_agent.core.models import ApplicationResult, Job, ApplicationStatus, Platform, JobType
from resume_agent.db.models import ApplicationRecord, Base


db_path = Path(settings.DB_PATH)
db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(f"sqlite+aiosqlite:///{settings.DB_PATH}")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_application(result: ApplicationResult):
    async with SessionLocal() as session:
        async with session.begin():
            record = ApplicationRecord(
                job_title=result.job.title,
                company=result.job.company,
                job_url=result.job.url,
                platform=result.job.platform.value,
                job_type=result.job.job_type.value,
                location=result.job.location,
                relevance_score=result.job.relevance_score,
                matched_skills=",".join(result.job.matched_skills),
                missing_skills=",".join(result.job.missing_skills),
                status=result.status.value,
                applied_at=result.applied_at,
                resume_pdf_path=result.tailored_resume_path,
                error=result.error,
                notes=result.notes,
            )
            session.add(record)


async def get_all_applications() -> list[ApplicationResult]:
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(ApplicationRecord).order_by(ApplicationRecord.id.desc()))
            records = result.scalars().all()
            
            apps = []
            for r in records:
                job = Job(
                    title=r.job_title,
                    company=r.company,
                    url=r.job_url,
                    description="",
                    platform=Platform(r.platform),
                    job_type=JobType(r.job_type),
                    location=r.location,
                    relevance_score=r.relevance_score or 0.0,
                    matched_skills=r.matched_skills.split(",") if r.matched_skills else [],
                    missing_skills=r.missing_skills.split(",") if r.missing_skills else [],
                )
                apps.append(
                    ApplicationResult(
                        job=job,
                        status=ApplicationStatus(r.status),
                        applied_at=r.applied_at,
                        error=r.error,
                        notes=r.notes,
                        tailored_resume_path=r.resume_pdf_path,
                    )
                )
            return apps


async def clear_all_applications() -> int:
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(delete(ApplicationRecord))
            return result.rowcount


async def is_already_applied(job_url: str) -> bool:
    """Return True if this job URL was successfully applied to in a previous run."""
    async with SessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(ApplicationRecord).where(
                    ApplicationRecord.job_url == job_url,
                    ApplicationRecord.status == ApplicationStatus.APPLIED.value,
                )
            )
            return result.scalars().first() is not None
