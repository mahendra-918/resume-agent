from __future__ import annotations

import asyncio

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.exceptions import JobSearchError
from resume_agent.core.models import Job, JobType, Platform
from resume_agent.platforms.base import BasePlatform


class IntershalaPlatform(BasePlatform):
    name = "internshala"

    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[Internshala] Searching: '{query}' in '{location}'")
        try:
            import pandas as pd
            from jobspy import scrape_jobs
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=["indeed"],
                search_term=query + " internship" if job_type == JobType.INTERNSHIP else query,
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
                    platform=Platform.INTERNSHALA,
                    job_type=JobType.INTERNSHIP if job_type == JobType.INTERNSHIP else JobType.FULL_TIME,
                    posted_at=posted,
                ))
            logger.info(f"[Internshala] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.error(f"[Internshala] Search failed: {e}")
            raise JobSearchError(f"Internshala search failed: {e}") from e
