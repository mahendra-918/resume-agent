from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.models import Job
from resume_agent.core.state import AgentState
from resume_agent.platforms.linkedin import LinkedInPlatform
from resume_agent.platforms.internshala import IntershalaPlatform
from resume_agent.platforms.naukri import NaukriPlatform
from resume_agent.platforms.wellfound import WellfoundPlatform


async def search_jobs_node(state: AgentState) -> dict:
    queries: list[str] = state["search_queries"] or ["software engineer intern"]

    logger.info(
        f"[JobSearcher] Platform toggles — LinkedIn:{settings.USE_LINKEDIN} "
        f"Internshala:{settings.USE_INTERNSHALA} Naukri:{settings.USE_NAUKRI} "
        f"Wellfound:{settings.USE_WELLFOUND}"
    )

    platform_map = [
        (settings.USE_LINKEDIN,    "linkedin",    LinkedInPlatform),
        (settings.USE_INTERNSHALA, "internshala", IntershalaPlatform),
        (settings.USE_NAUKRI,      "naukri",      NaukriPlatform),
        (settings.USE_WELLFOUND,   "wellfound",   WellfoundPlatform),
    ]

    platforms = [(name, cls()) for enabled, name, cls in platform_map if enabled]

    logger.info(f"[JobSearcher] Searching {len(platforms)} platforms × {len(queries)} queries")

    platform_status: dict[str, dict] = {}
    all_jobs: list[list[Job]] = []

    async def safe_search(name: str, platform: Any, query: str) -> list[Job]:
        t0 = time.monotonic()
        try:
            results = await platform.search(
                query=query,
                location=settings.JOB_LOCATION,
                job_type=settings.JOB_TYPE,
            )
            duration_ms = (time.monotonic() - t0) * 1000
            if not results:
                logger.warning(
                    f"[JobSearcher] {name} ({query!r}) returned empty — "
                    f"url={name}:{query}, duration={duration_ms:.0f}ms"
                )
            else:
                logger.info(f"[JobSearcher] {name} ({query!r}): {len(results)} results")

            existing = platform_status.get(name, {"count": 0, "error": None, "duration_ms": 0.0})
            platform_status[name] = {
                "count": existing["count"] + len(results),
                "error": "empty_result" if not results else None,
                "duration_ms": existing["duration_ms"] + duration_ms,
            }
            return results
        except Exception as e:
            duration_ms = (time.monotonic() - t0) * 1000
            logger.warning(f"[JobSearcher] {name} ({query!r}) failed: {e}")
            existing = platform_status.get(name, {"count": 0, "error": None, "duration_ms": 0.0})
            platform_status[name] = {
                "count": existing["count"],
                "error": str(e),
                "duration_ms": existing["duration_ms"] + duration_ms,
            }
            return []

    tasks = [
        safe_search(name, platform, q)
        for name, platform in platforms
        for q in queries
    ]
    all_jobs = await asyncio.gather(*tasks)

    # ── De-duplicate ──────────────────────────────────────────────────────────
    seen: set[str] = set()
    jobs: list[Job] = []
    for platform_jobs in all_jobs:
        for job in platform_jobs:
            key = f"{job.title.lower()}|{job.company.lower()}"
            if key not in seen:
                seen.add(key)
                jobs.append(job)

    logger.info(f"[JobSearcher] Total unique jobs found: {len(jobs)}")
    logger.info(f"[JobSearcher] Platform status: {platform_status}")

    return {"jobs_found": jobs, "platform_status": platform_status}
