from __future__ import annotations

from loguru import logger

from resume_agent.core.models import Job, ParsedResume, ResumeProject, ResumeExperience, TailoredResume
from resume_agent.core.state import AgentState
from resume_agent.llm.chains import run_resume_tailor_chain
from resume_agent.utils.pdf_generator import generate_tailored_pdf


async def tailor_resume_node(state: AgentState) -> dict:
    job: Job = state["current_job"]

    # Duplicate skip: process_next_job set current_job to None for already-applied jobs
    if job is None:
        return {}

    parsed: ParsedResume = state["parsed_resume"]
    logger.info(f"[ResumeTailor] Tailoring for {job.title} @ {job.company}")

    try:
        result = await run_resume_tailor_chain(
            job_title=job.title,
            company=job.company,
            job_description=job.description,
            resume_json=parsed.model_dump_json(),
        )

        reordered_projects = [
            ResumeProject(**p) if isinstance(p, dict) else p
            for p in result.get("reordered_projects", parsed.projects)
        ]
        reordered_experience = [
            ResumeExperience(**e) if isinstance(e, dict) else e
            for e in result.get("reordered_experience", parsed.experience)
        ]

        tailored = TailoredResume(
            base=parsed,
            job_title=job.title,
            company=job.company,
            tailored_summary=result.get("tailored_summary", parsed.summary),
            highlighted_skills=result.get("highlighted_skills", []),
            reordered_projects=reordered_projects,
            reordered_experience=reordered_experience,
            added_keywords=result.get("added_keywords", []),
        )

        # Generate physical PDF
        pdf_path = await generate_tailored_pdf(tailored)
        tailored.file_path = pdf_path

        logger.info(f"[ResumeTailor] Done — PDF generated at {pdf_path}")
        return {"tailored_resume": tailored}

    except Exception as e:
        logger.error(f"[ResumeTailor] Failed: {e}")
        errors = list(state.get("errors") or [])
        errors.append(f"ResumeTailor: {e}")
        fallback = TailoredResume(
            base=parsed,
            job_title=job.title,
            company=job.company,
            tailored_summary=parsed.summary,
            reordered_projects=parsed.projects,
            reordered_experience=parsed.experience,
        )
        return {"tailored_resume": fallback, "errors": errors}
