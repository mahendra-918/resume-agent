from __future__ import annotations

from datetime import datetime

from loguru import logger

from resume_agent.core.models import (
    ApplicationResult,
    ApplicationStatus,
    Job,
    Platform,
    TailoredResume,
)
from resume_agent.core.state import AgentState


async def apply_job_node(state: AgentState) -> dict:
    job: Job = state["current_job"]
    tailored: TailoredResume = state["tailored_resume"]
    dry_run: bool = state.get("dry_run", False)
    applications: list[ApplicationResult] = list(state.get("applications") or [])

    if dry_run:
        logger.info(
            f"[JobApplier] DRY RUN — skipping submission for {job.title} @ {job.company}"
        )
        applications.append(
            ApplicationResult(
                job=job,
                status=ApplicationStatus.SKIPPED,
                resume_pdf_path=tailored.pdf_path,
                resume_docx_path=tailored.docx_path,
                notes="Dry run — not submitted",
            )
        )
        return {"applications": applications}

    logger.info(f"[JobApplier] Applying to {job.title} @ {job.company} via {job.platform}")

    try:
        from resume_agent.platforms.linkedin import LinkedInPlatform
        from resume_agent.platforms.internshala import IntershalaPlatform
        from resume_agent.platforms.naukri import NaukriPlatform
        from resume_agent.platforms.wellfound import WellfoundPlatform

        platform_map = {
            Platform.LINKEDIN: LinkedInPlatform,
            Platform.INTERNSHALA: IntershalaPlatform,
            Platform.NAUKRI: NaukriPlatform,
            Platform.WELLFOUND: WellfoundPlatform,
        }

        platform_cls = platform_map.get(job.platform)
        if platform_cls is None:
            raise ValueError(f"Unknown platform: {job.platform}")

        platform = platform_cls()
        result = await platform.apply(job=job, resume_pdf_path=tailored.pdf_path or "")

        result.resume_pdf_path = tailored.pdf_path
        result.resume_docx_path = tailored.docx_path
        applications.append(result)
        logger.info(f"[JobApplier] Applied successfully: {result.status}")

    except Exception as e:
        logger.error(f"[JobApplier] Application failed for {job.title} @ {job.company}: {e}")
        errors = list(state.get("errors") or [])
        errors.append(f"JobApplier: {e}")
        applications.append(
            ApplicationResult(
                job=job,
                status=ApplicationStatus.FAILED,
                applied_at=datetime.utcnow(),
                resume_pdf_path=tailored.pdf_path,
                resume_docx_path=tailored.docx_path,
                error=str(e),
            )
        )
        return {"applications": applications, "errors": errors}

    return {"applications": applications}
