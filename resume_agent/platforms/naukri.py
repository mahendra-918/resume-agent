import asyncio
from datetime import datetime
from loguru import logger
from jobspy import scrape_jobs
from playwright.async_api import async_playwright, Page

from resume_agent.core.config import settings
from resume_agent.core.models import Job, ApplicationResult, ApplicationStatus, Platform, JobType
from resume_agent.core.exceptions import JobSearchError, PlatformLoginError, ApplicationError
from resume_agent.platforms.base import BasePlatform


class NaukriPlatform(BasePlatform):
    name = "naukri"

    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[Naukri] Searching: '{query}' in '{location}'")
        try:
            df = await asyncio.to_thread(
                scrape_jobs,
                site_name=["indeed"],  # jobspy uses Indeed for India
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

    async def apply(self, job: Job) -> ApplicationResult:
        logger.info(f"[Naukri] Applying to: {job.title} at {job.company}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                slow_mo=settings.BROWSER_SLOW_MO,
            )
            page = await browser.new_page()
            try:
                await self._login(page)
                await page.goto(job.url, wait_until="networkidle")
                await asyncio.sleep(2)

                apply_btn = page.locator("button:has-text('Apply'), a:has-text('Apply')").first
                if not await apply_btn.is_visible():
                    return ApplicationResult(
                        job=job,
                        status=ApplicationStatus.SKIPPED,
                        notes="Apply button not found",
                    )

                await apply_btn.click()
                await asyncio.sleep(2)

                logger.success(f"[Naukri] Applied: {job.title} at {job.company}")
                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.APPLIED,
                    applied_at=datetime.now(),
                )

            except Exception as e:
                logger.error(f"[Naukri] Apply failed: {e}")
                raise ApplicationError(f"Naukri apply failed: {e}") from e
            finally:
                await browser.close()

    async def _login(self, page: Page) -> None:
        if not settings.NAUKRI_EMAIL or not settings.NAUKRI_PASSWORD:
            raise PlatformLoginError("Naukri credentials not set in .env")
        await page.goto("https://www.naukri.com/nlogin/login", wait_until="networkidle")
        await page.fill("input[placeholder='Enter your active Email ID / Username']", settings.NAUKRI_EMAIL)
        await page.fill("input[placeholder='Enter your password']", settings.NAUKRI_PASSWORD)
        await page.click("button[type='submit']")
        await asyncio.sleep(3)
        logger.info("[Naukri] Logged in successfully")