from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.models import Job, ParsedResume
from resume_agent.core.state import AgentState


async def _search_platform(platform: Any, query: str) -> list[Job]:
    return await platform.search(
        query=query,
        location=settings.JOB_LOCATION,
        job_type=settings.JOB_TYPE,
    )


async def search_jobs_node(state: AgentState) -> dict:
    queries: list[str] = state["search_queries"]
    query = queries[0] if queries else "software engineer intern"

    from resume_agent.platforms.linkedin import LinkedInPlatform
    from resume_agent.platforms.internshala import IntershalaPlatform
    from resume_agent.platforms.naukri import NaukriPlatform
    from resume_agent.platforms.wellfound import WellfoundPlatform

    platform_map = [
        (settings.USE_LINKEDIN, LinkedInPlatform),
        (settings.USE_INTERNSHALA, IntershalaPlatform),
        (settings.USE_NAUKRI, NaukriPlatform),
        (settings.USE_WELLFOUND, WellfoundPlatform),
    ]

    active_platforms = [cls() for enabled, cls in platform_map if enabled]
    logger.info(
        f"[JobSearcher] Searching {len(active_platforms)} platforms with query: {query!r}"
    )

    async def safe_search(platform: Any) -> list[Job]:
        try:
            results = await _search_platform(platform, query)
            logger.info(f"[JobSearcher] {platform.name}: {len(results)} results")
            return results
        except Exception as e:
            logger.warning(f"[JobSearcher] {platform.name} failed: {e}")
            return []

    results_per_platform = await asyncio.gather(*[safe_search(p) for p in active_platforms])

    seen: set[str] = set()
    jobs: list[Job] = []
    for platform_jobs in results_per_platform:
        for job in platform_jobs:
            key = f"{job.title.lower()}|{job.company.lower()}"
            if key not in seen:
                seen.add(key)
                jobs.append(job)

    logger.info(f"[JobSearcher] Total unique jobs found: {len(jobs)}")
    return {"jobs_found": jobs}
