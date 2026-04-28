from __future__ import annotations

import asyncio
from datetime import datetime

from jobspy import scrape_jobs
from loguru import logger
from playwright.async_api import Page, async_playwright

from resume_agent.core.config import settings
from resume_agent.core.exceptions import ApplicationError, JobSearchError, PlatformLoginError
from resume_agent.core.models import (
    ApplicationResult, ApplicationStatus, Job, JobType, Platform,
)
from resume_agent.platforms.base import BasePlatform


class LinkedInPlatform(BasePlatform):
    name = "linkedin"
    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[LinkedIn] Searching: '{query}' in '{location}'")
        try:
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=["linkedin"],
                search_term=query,
                location=location,
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


    async def apply(self, job: Job, resume_path: str | None = None) -> ApplicationResult:
        logger.info(f"[LinkedIn] Applying to: {job.title} at {job.company}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                slow_mo=settings.BROWSER_SLOW_MO,
            )
            context = await browser.new_context()

            try:
                if self._session_exists():
                    await self._load_session(context)
                    logger.info("[LinkedIn] Using saved session — skipping login")
                else:
                    page = await context.new_page()
                    await self._login(page)
                    await self._save_session(context)
                    await page.close()

                page = await context.new_page()
                await page.goto(job.url, wait_until="networkidle")
                await asyncio.sleep(2)

                
                if "login" in page.url or "authwall" in page.url:
                    logger.warning("[LinkedIn] Session expired — re-logging in")
                    self._delete_session()
                    await self._login(page)
                    await self._save_session(context)
                    await page.goto(job.url, wait_until="networkidle")
                    await asyncio.sleep(2)

                # ── Click Easy Apply ───────────────────────────────────────────
                easy_apply = page.locator("button:has-text('Easy Apply')").first
                if not await easy_apply.is_visible():
                    return ApplicationResult(
                        job=job,
                        status=ApplicationStatus.SKIPPED,
                        notes="No Easy Apply button found",
                    )

                await easy_apply.click()
                await asyncio.sleep(1)

                # ── Step through multi-page form ───────────────────────────────
                for _ in range(5):
                    # Upload resume if we see a file input on the current modal page
                    if resume_path:
                        file_input = page.locator("input[type='file']").first
                        if await file_input.is_visible():
                            logger.info(f"[LinkedIn] Uploading tailored resume: {resume_path}")
                            await file_input.set_input_files(resume_path)
                            await asyncio.sleep(2)  # Wait for upload to complete

                    submit_btn = page.locator("button:has-text('Submit application')").first
                    review_btn = page.locator("button:has-text('Review')").first
                    next_btn   = page.locator("button:has-text('Next')").first

                    if await submit_btn.is_visible():
                        await submit_btn.click()
                        logger.success(f"[LinkedIn] Applied: {job.title} at {job.company}")
                        return ApplicationResult(
                            job=job,
                            status=ApplicationStatus.APPLIED,
                            applied_at=datetime.now(),
                        )
                    elif await review_btn.is_visible():
                        await review_btn.click()
                    elif await next_btn.is_visible():
                        await next_btn.click()
                    else:
                        break
                    await asyncio.sleep(1)

                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.FAILED,
                    notes="Could not complete application form",
                )

            except Exception as e:
                logger.error(f"[LinkedIn] Apply failed: {e}")
                raise ApplicationError(f"LinkedIn apply failed: {e}") from e
            finally:
                await browser.close()

    # ── Login (used only when no session exists) ───────────────────────────────

    async def _login(self, page: Page) -> None:
        if not settings.LINKEDIN_EMAIL or not settings.LINKEDIN_PASSWORD:
            raise PlatformLoginError("LinkedIn credentials not set in .env")

        await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
        await page.fill("#username", settings.LINKEDIN_EMAIL)
        await page.fill("#password", settings.LINKEDIN_PASSWORD)
        await page.click("button[type='submit']")
        await asyncio.sleep(3)

        if "checkpoint" in page.url or "login" in page.url:
            raise PlatformLoginError(
                "LinkedIn login failed — possible CAPTCHA or OTP. "
                "Run: uv run python -m resume_agent.platforms.save_session --platform linkedin"
            )
        logger.info("[LinkedIn] Logged in successfully")
