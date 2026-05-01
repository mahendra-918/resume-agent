from __future__ import annotations

import asyncio

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.exceptions import JobSearchError
from resume_agent.core.models import Job, JobType, Platform
from resume_agent.platforms.base import BasePlatform


class WellfoundPlatform(BasePlatform):
    name = "wellfound"

    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[Wellfound] Searching: '{query}' in '{location}'")
        try:
            import pandas as pd
            from jobspy import scrape_jobs
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=["glassdoor"],
                search_term=query,
                location=location,
                results_wanted=settings.RESULTS_PER_PLATFORM,
            )
            jobs = []
            for _, row in df.iterrows():
                posted = row.get("date_posted")
                if pd.isna(posted):
                    posted = None
                jobs.append(Job(
                    title=str(row.get("title", "")),
                    company=str(row.get("company", "")),
                    location=str(row.get("location", "")),
                    description=str(row.get("description", "")),
                    url=str(row.get("job_url", "")),
                    platform=Platform.WELLFOUND,
                    job_type=JobType.INTERNSHIP if job_type == JobType.INTERNSHIP else JobType.FULL_TIME,
                    posted_at=posted,
                ))
            logger.info(f"[Wellfound] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.error(f"[Wellfound] Search failed: {e}")
            raise JobSearchError(f"Wellfound search failed: {e}") from e
