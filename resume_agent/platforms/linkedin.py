from __future__ import annotations

import asyncio

from jobspy import scrape_jobs
from jobspy.model import Country
from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.exceptions import JobSearchError
from resume_agent.core.models import Job, JobType, Platform
from resume_agent.platforms.base import BasePlatform


def _country_indeed(location: str) -> str:
    """Map a free-form location string to a jobspy country_indeed value.

    Falls back to 'worldwide' for unrecognised or remote locations so that
    LinkedIn searches never raise 'Invalid country string'.
    """
    loc = location.lower().strip()

    # Explicit remote / worldwide shortcut — must come before alias loop
    # to prevent short country aliases (e.g. "lb" for Lebanon) matching
    # inside words like "remote" or "anywhere".
    if not loc or loc in ("remote", "worldwide", "anywhere", "work from home", "wfh"):
        return "worldwide"

    for country in Country:
        for alias in country.value[0].split(","):
            alias = alias.strip()
            # Only match aliases that are at least 4 chars long AND appear as
            # a whole word in the location string to avoid false positives.
            if len(alias) >= 4 and alias in loc:
                return alias
    return "worldwide"


class LinkedInPlatform(BasePlatform):
    name = "linkedin"
    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[LinkedIn] Searching: '{query}' in '{location}'")
        country = _country_indeed(location)
        logger.debug(f"[LinkedIn] Resolved country_indeed='{country}' from location='{location}'")
        try:
            # Try with easy_apply=True first (gets only Easy Apply jobs).
            # If that returns nothing, fall back to all jobs so the pipeline
            # still has something to rank and package.
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=["linkedin"],
                search_term=query,
                location=location,
                country_indeed=country,
                results_wanted=settings.RESULTS_PER_PLATFORM,
                job_type="internship" if job_type == JobType.INTERNSHIP else "fulltime",
                easy_apply=True,
            )

            if df is None or df.empty:
                logger.warning(f"[LinkedIn] easy_apply=True returned 0 — retrying without filter")
                df = await asyncio.to_thread(
                    scrape_jobs,
                    site_name=["linkedin"],
                    search_term=query,
                    location=location,
                    country_indeed=country,
                    results_wanted=settings.RESULTS_PER_PLATFORM,
                    job_type="internship" if job_type == JobType.INTERNSHIP else "fulltime",
                )
            import pandas as pd
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
                    platform=Platform.LINKEDIN,
                    job_type=JobType.INTERNSHIP if job_type == JobType.INTERNSHIP else JobType.FULL_TIME,
                    posted_at=posted,
                ))
            logger.info(f"[LinkedIn] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.error(f"[LinkedIn] Search failed: {e}")
            raise JobSearchError(f"LinkedIn search failed: {e}") from e

