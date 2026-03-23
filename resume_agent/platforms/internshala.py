import asyncio
from datetime import datetime
from loguru import logger
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from resume_agent.core.config import settings
from resume_agent.core.models import Job, ApplicationResult, ApplicationStatus, Platform, JobType
from resume_agent.core.exceptions import JobSearchError, PlatformLoginError, ApplicationError
from resume_agent.platforms.base import BasePlatform


class IntershalaPlatform(BasePlatform):
    name = "internshala"
    BASE_URL = "https://internshala.com"

    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        logger.info(f"[Internshala] Searching: '{query}'")
        try:
            slug = query.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/internships/keywords-{slug}"
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                })
            soup = BeautifulSoup(response.text, "html.parser")
            cards = soup.select(".internship_meta")[:settings.RESULTS_PER_PLATFORM]

            jobs = []
            for card in cards:
                title_el = card.select_one(".profile a")
                company_el = card.select_one(".company_name a")
                link_el = card.select_one(".profile a")
                desc_el = card.select_one(".internship_other_details_container")

                if not title_el:
                    continue

                job_url = self.BASE_URL + (link_el["href"] if link_el else "")
                jobs.append(Job(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else "Unknown",
                    location=location,
                    description=desc_el.get_text(strip=True) if desc_el else "",
                    url=job_url,
                    platform=Platform.INTERNSHALA,
                    job_type=JobType.INTERNSHIP,
                ))

            logger.info(f"[Internshala] Found {len(jobs)} internships")
            return jobs
        except Exception as e:
            logger.error(f"[Internshala] Search failed: {e}")
            raise JobSearchError(f"Internshala search failed: {e}") from e

    async def apply(self, job: Job, resume_pdf_path: str) -> ApplicationResult:
        logger.info(f"[Internshala] Applying to: {job.title} at {job.company}")
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

                apply_btn = page.locator("a:has-text('Apply now'), button:has-text('Apply now')").first
                if not await apply_btn.is_visible():
                    return ApplicationResult(
                        job=job,
                        status=ApplicationStatus.SKIPPED,
                        notes="Apply button not found",
                    )

                await apply_btn.click()
                await asyncio.sleep(2)

                # Fill cover letter if present
                cover_letter = page.locator("textarea").first
                if await cover_letter.is_visible():
                    await cover_letter.fill(
                        f"I am excited to apply for the {job.title} role at {job.company}. "
                        f"My skills in Python, LangChain, and FastAPI align well with this opportunity."
                    )

                submit_btn = page.locator("button:has-text('Submit'), input[value='Submit']").first
                if await submit_btn.is_visible():
                    await submit_btn.click()
                    logger.success(f"[Internshala] Applied: {job.title} at {job.company}")
                    return ApplicationResult(
                        job=job,
                        status=ApplicationStatus.APPLIED,
                        applied_at=datetime.now(),
                        resume_pdf_path=resume_pdf_path,
                    )

                return ApplicationResult(
                    job=job,
                    status=ApplicationStatus.FAILED,
                    notes="Could not submit application",
                )

            except Exception as e:
                logger.error(f"[Internshala] Apply failed: {e}")
                raise ApplicationError(f"Internshala apply failed: {e}") from e
            finally:
                await browser.close()

    async def _login(self, page: Page) -> None:
        if not settings.INTERNSHALA_EMAIL or not settings.INTERNSHALA_PASSWORD:
            raise PlatformLoginError("Internshala credentials not set in .env")
        await page.goto(f"{self.BASE_URL}/login", wait_until="networkidle")
        await page.fill("#email", settings.INTERNSHALA_EMAIL)
        await page.fill("#password", settings.INTERNSHALA_PASSWORD)
        await page.click("#login_submit")
        await asyncio.sleep(3)
        logger.info("[Internshala] Logged in successfully")