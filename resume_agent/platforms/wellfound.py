import asyncio
from datetime import datetime
from loguru import logger
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from resume_agent.core.config import settings
from resume_agent.core.models import Job, ApplicationResult, ApplicationStatus, Platform, JobType
from resume_agent.core.exceptions import JobSearchError, ApplicationError
from resume_agent.platforms.base import BasePlatform


class WellfoundPlatform(BasePlatform):
    name = "wellfound"
    BASE_URL = "https://wellfound.com"

    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[Wellfound] Searching: '{query}'")
        try:
            slug = query.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/role/{slug}"
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                })
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select("[class*='JobListing']")[:settings.RESULTS_PER_PLATFORM]

            jobs = []
            for card in cards:
                title_el = card.select_one("a[class*='title'], h2")
                company_el = card.select_one("[class*='company'], h3")
                link_el = card.select_one("a[href*='/jobs/']")

                if not title_el:
                    continue

                job_url = self.BASE_URL + link_el["href"] if link_el else url
                jobs.append(Job(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "Unknown",
                    location=location,
                    description=card.get_text(strip=True),
                    url=job_url,
                    platform=Platform.WELLFOUND,
                    job_type=JobType.FULL_TIME,
                ))

            logger.info(f"[Wellfound] Found {len(jobs)} jobs")
            return jobs
        except Exception as e:
            logger.error(f"[Wellfound] Search failed: {e}")
            raise JobSearchError(f"Wellfound search failed: {e}") from e

    async def apply(self, job: Job, resume_path: str | None = None) -> ApplicationResult:
        logger.info(f"[Wellfound] Applying to: {job.title} at {job.company}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                slow_mo=settings.BROWSER_SLOW_MO,
            )
            page = await browser.new_page()
            try:
                await page.goto(job.url, wait_until="networkidle")
                await asyncio.sleep(2)

                apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply')").first
                if not await apply_btn.is_visible():
                    return ApplicationResult(
                        job=job,
                        status=ApplicationStatus.SKIPPED,
                        notes="Apply button not found — may require account",
                    )

                await apply_btn.click()
                await asyncio.sleep(2)

                return ApplicationResult(
                    job=job,
                        status=ApplicationStatus.APPLIED,
                        applied_at=datetime.now(),
                    )

            except Exception as e:
                logger.error(f"[Wellfound] Apply failed: {e}")
                raise ApplicationError(f"Wellfound apply failed: {e}") from e
            finally:
                await browser.close()
