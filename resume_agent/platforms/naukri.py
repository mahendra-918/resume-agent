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

    # ── Apply ──────────────────────────────────────────────────────────────────

    async def apply(self, job: Job, resume_path: str | None = None) -> ApplicationResult:
        logger.info(f"[Naukri] Applying to: {job.title} at {job.company}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=settings.HEADLESS,
                slow_mo=settings.BROWSER_SLOW_MO,
            )
            context = await browser.new_context()

            try:
                # ── Session check ──────────────────────────────────────────────
                if self._session_exists():
                    await self._load_session(context)
                    logger.info("[Naukri] Using saved session — skipping login")
                else:
                    page = await context.new_page()
                    await self._login(page)
                    await self._save_session(context)
                    await page.close()

                # ── Navigate to job ────────────────────────────────────────────
                page = await context.new_page()
                try:
                    await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning(f"[Naukri] Initial page load timeout, proceeding anyway: {e}")
                await asyncio.sleep(2)

                # ── Check session still valid ──────────────────────────────────
                if "login" in page.url or "nlogin" in page.url or "signin" in page.url:
                    logger.warning("[Naukri] Session expired — re-logging in")
                    self._delete_session()
                    await self._login(page)
                    await self._save_session(context)
                    try:
                        await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                    except Exception as e:
                        logger.warning(f"[Naukri] Second page load timeout, proceeding: {e}")
                    await asyncio.sleep(2)

                # ── Upload Tailored Resume (if provided) ──────────────────────────
                if resume_path:
                    # Naukri's application modal usually has an input[type='file'] for resume upload
                    file_input = page.locator("input[type='file']").first
                    if await file_input.is_visible():
                        logger.info(f"[Naukri] Uploading tailored resume: {resume_path}")
                        await file_input.set_input_files(resume_path)
                        await asyncio.sleep(2)  # Wait for upload to complete

                # ── Click Apply ────────────────────────────────────────────────
                apply_btn = page.locator(
                    "button:has-text('Apply'), a:has-text('Apply')"
                ).first
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

    # ── Login (used only when no session exists) ───────────────────────────────

    async def _login(self, page: Page) -> None:
        if not settings.NAUKRI_EMAIL or not settings.NAUKRI_PASSWORD:
            raise PlatformLoginError("Naukri credentials not set in .env")

        await page.goto("https://www.naukri.com/nlogin/login", wait_until="networkidle")
        await asyncio.sleep(2)

        # Try multiple possible selectors for the email field (Naukri changes their UI)
        email_selector = (
            "input[placeholder*='Email'], "
            "input[placeholder*='email'], "
            "input[type='email'], "
            "input[name='username'], "
            "#usernameField"
        )
        password_selector = (
            "input[placeholder*='password'], "
            "input[placeholder*='Password'], "
            "input[type='password']"
        )

        try:
            await page.wait_for_selector(email_selector, timeout=10000)
            await page.fill(email_selector, settings.NAUKRI_EMAIL)
            await page.fill(password_selector, settings.NAUKRI_PASSWORD)
            await page.click("button[type='submit']")
            await asyncio.sleep(4)
            logger.info("[Naukri] Logged in successfully")
        except Exception as e:
            raise PlatformLoginError(
                f"Naukri login form not found — UI may have changed. "
                f"Run: uv run python -m resume_agent.platforms.save_session --platform naukri\n"
                f"Original error: {e}"
            ) from e
