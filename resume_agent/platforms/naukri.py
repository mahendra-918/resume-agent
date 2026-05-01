from __future__ import annotations

import asyncio

from jobspy import scrape_jobs
from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.exceptions import JobSearchError
from resume_agent.core.models import Job, JobType, Platform
from resume_agent.platforms.base import BasePlatform


class NaukriPlatform(BasePlatform):
    name = "naukri"

    # ── Search ─────────────────────────────────────────────────────────────────

    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[Naukri] Searching: '{query}' in '{location}'")
        try:
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=["indeed"],   # jobspy uses Indeed for India
                search_term=query,
                location=location,
                results_wanted=settings.RESULTS_PER_PLATFORM,
            )
            jobs = []
            for _, row in df.iterrows():
                jobs.append(Job(
                    title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=str(row.get("location", "")),
                    description=str(row.get("description", "")),
                    url=str(row.get("job_url", "")),
                    platform=Platform.NAUKRI,
                    job_type=JobType.INTERNSHIP if job_type == JobType.INTERNSHIP else JobType.FULL_TIME,
                ))
            logger.info(f"[Naukri] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.error(f"[Naukri] Search failed: {e}")
            raise JobSearchError(f"Naukri search failed: {e}") from e

