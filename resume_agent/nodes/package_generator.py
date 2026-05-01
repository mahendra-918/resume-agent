from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path

from loguru import logger

from resume_agent.core.models import ApplicationPackage, Job, ParsedResume, TailoredResume
from resume_agent.core.state import AgentState
from resume_agent.llm.chains import (
    run_cover_letter_chain,
    run_email_draft_chain,
    run_interview_prep_chain,
)


def _safe_dirname(text: str) -> str:
    """Convert job title + company into a safe folder name."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().replace(" ", "_")
    return slug[:50]  # cap length


def _save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def generate_package_node(state: AgentState) -> dict:
    job: Job = state["current_job"]

    if job is None:
        return {}

    tailored: TailoredResume = state["tailored_resume"]
    parsed: ParsedResume = state["parsed_resume"]
    packages: list[ApplicationPackage] = list(state.get("packages") or [])

    logger.info(f"[PackageGenerator] Generating package for {job.title} @ {job.company}")

    # ── Build output directory ────────────────────────────────────────────────
    dir_name = f"{_safe_dirname(job.company)}_{_safe_dirname(job.title)}"
    output_dir = Path("output") / "packages" / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Prepare shared inputs ─────────────────────────────────────────────────
    skills_str = ", ".join(parsed.skills.all_skills()[:20])
    projects_str = "; ".join(
        f"{p.name} ({', '.join(p.tech_stack[:3])})" for p in parsed.projects[:4]
    )

    package = ApplicationPackage(
        job=job,
        tailored_resume_path=tailored.file_path if tailored else None,
        output_dir=str(output_dir),
        generated_at=datetime.now(),
    )

    errors = list(state.get("errors") or [])

    # ── 1-3: Cover Letter + Email + Interview Prep — run in parallel ─────────
    logger.info(f"[PackageGenerator] Generating cover letter, email & interview prep in parallel…")
    jd = job.description[:1200]  # trim context to reduce token count

    async def _cover():
        return await run_cover_letter_chain(
            name=parsed.name, job_title=job.title, company=job.company,
            job_description=jd, resume_summary=parsed.summary,
            skills=skills_str, projects=projects_str,
        )

    async def _email():
        return await run_email_draft_chain(
            name=parsed.name, job_title=job.title,
            company=job.company, skills=skills_str,
        )

    async def _prep():
        return await run_interview_prep_chain(
            job_title=job.title, company=job.company, job_description=jd,
            resume_summary=parsed.summary, skills=skills_str, projects=projects_str,
        )

    cover_result, email_result, prep_result = await asyncio.gather(
        _cover(), _email(), _prep(), return_exceptions=True
    )

    if isinstance(cover_result, Exception):
        logger.error(f"[PackageGenerator] Cover letter failed: {cover_result}")
        errors.append(f"PackageGenerator cover letter: {cover_result}")
    else:
        package.cover_letter = cover_result
        cover_path = output_dir / "cover_letter.txt"
        _save_text(cover_path, cover_result)
        package.cover_letter_path = str(cover_path)
        logger.info(f"[PackageGenerator] Cover letter saved → {cover_path}")

    if isinstance(email_result, Exception):
        logger.error(f"[PackageGenerator] Email draft failed: {email_result}")
        errors.append(f"PackageGenerator email draft: {email_result}")
    else:
        package.email_draft = email_result
        email_path = output_dir / "email_draft.txt"
        _save_text(email_path, email_result)
        logger.info(f"[PackageGenerator] Email draft saved → {email_path}")

    if isinstance(prep_result, Exception):
        logger.error(f"[PackageGenerator] Interview prep failed: {prep_result}")
        errors.append(f"PackageGenerator interview prep: {prep_result}")
    else:
        package.interview_prep = prep_result
        prep_path = output_dir / "interview_prep.txt"
        _save_text(prep_path, prep_result)
        logger.info(f"[PackageGenerator] Interview prep saved → {prep_path}")

    # ── 4. Write a README index for the package folder ────────────────────────
    try:
        readme_lines = [
            f"# Application Package",
            f"**Job:** {job.title}",
            f"**Company:** {job.company}",
            f"**Platform:** {job.platform.value}",
            f"**Job URL:** {job.url}",
            f"**Generated:** {package.generated_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Match Score:** {job.relevance_score:.0%}",
            f"",
            f"## Files",
            f"- `resume_tailored.pdf` — tailored resume",
            f"- `cover_letter.txt` — personalized cover letter",
            f"- `email_draft.txt` — cold email ready to send",
            f"- `interview_prep.txt` — likely questions + talking points",
            f"",
            f"## Missing Skills to Address",
        ]
        for skill in job.missing_skills[:5]:
            readme_lines.append(f"- {skill}")
        _save_text(output_dir / "README.md", "\n".join(readme_lines))
    except Exception as e:
        logger.warning(f"[PackageGenerator] README write failed (non-fatal): {e}")

    # Save resume path reference
    if tailored and tailored.file_path:
        resume_ref = Path(tailored.file_path)
        _save_text(output_dir / "resume_path.txt", resume_ref.name)

    packages.append(package)
    logger.success(
        f"[PackageGenerator] Package complete for {job.title} @ {job.company} → {output_dir}"
    )
    return {"packages": packages, "errors": errors}
