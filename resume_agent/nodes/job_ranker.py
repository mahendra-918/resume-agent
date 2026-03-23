from __future__ import annotations

import asyncio

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.models import Job, ParsedResume
from resume_agent.core.state import AgentState
from resume_agent.llm.chains import run_job_rank_chain


async def _rank_job(job: Job, candidate_skills: list[str], candidate_experience: str) -> Job:
    try:
        result = await run_job_rank_chain(
            candidate_skills=candidate_skills,
            candidate_experience=candidate_experience,
            job_title=job.title,
            job_description=job.description,
        )
        job.relevance_score = float(result.get("relevance_score", 0.0))
        job.matched_skills = result.get("matched_skills", [])
        job.missing_skills = result.get("missing_skills", [])
    except Exception as e:
        logger.warning(f"[JobRanker] Ranking failed for {job.title} @ {job.company}: {e}")
        job.relevance_score = 0.0
    return job


async def rank_jobs_node(state: AgentState) -> dict:
    jobs: list[Job] = state["jobs_found"]
    parsed: ParsedResume = state["parsed_resume"]

    candidate_skills = parsed.skills.all_skills()
    candidate_experience = ""
    if parsed.experience:
        first = parsed.experience[0]
        candidate_experience = f"{first.title} at {first.org}: " + "; ".join(first.highlights[:3])

    logger.info(f"[JobRanker] Ranking {len(jobs)} jobs...")
    ranked = await asyncio.gather(*[
        _rank_job(job, candidate_skills, candidate_experience) for job in jobs
    ])

    filtered = [
        j for j in ranked if j.relevance_score >= settings.MIN_RELEVANCE_SCORE
    ]
    filtered.sort(key=lambda j: j.relevance_score, reverse=True)
    filtered = filtered[: settings.MAX_APPLICATIONS]

    logger.info(
        f"[JobRanker] {len(filtered)} jobs passed threshold "
        f"(>= {settings.MIN_RELEVANCE_SCORE}), capped at {settings.MAX_APPLICATIONS}"
    )
    return {"jobs_filtered": filtered}
