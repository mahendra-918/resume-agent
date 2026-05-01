"""
One-Time Session Saver
══════════════════════
Run this script ONCE per platform to save your browser session.
After this, the main pipeline will never need to log in again — it
loads the saved session and goes straight to applying.

Usage:
    uv run python -m resume_agent.platforms.save_session --platform linkedin
    uv run python -m resume_agent.platforms.save_session --platform internshala
    uv run python -m resume_agent.platforms.save_session --platform naukri
    uv run python -m resume_agent.platforms.save_session --platform wellfound
    uv run python -m resume_agent.platforms.save_session --platform all

What happens:
    1. A real browser window opens (NOT headless — you can see it)
    2. The script navigates to the platform's login page
    3. YOU manually type your email + password and complete any CAPTCHA / OTP
    4. Once you're logged in, press Enter in the terminal
    5. The session (cookies) is saved to output/sessions/{platform}_session.json
    6. Future pipeline runs load this file — no login needed
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from loguru import logger
from playwright.async_api import async_playwright

from resume_agent.core.config import settings

app = typer.Typer(help="Save browser sessions for job platforms.")

# ── Platform login URLs ────────────────────────────────────────────────────────

PLATFORM_URLS = {
    "linkedin":    "https://www.linkedin.com/login",
    "internshala": "https://internshala.com/login",
    "naukri":      "https://www.naukri.com/nlogin/login",
    "wellfound":   "https://wellfound.com/login",
}


async def _save_session_for(platform: str) -> None:

    if platform not in PLATFORM_URLS:
        logger.error(f"Unknown platform: {platform}. Choose from: {list(PLATFORM_URLS)}")
        raise typer.Exit(1)

    login_url = PLATFORM_URLS[platform]
    sessions_dir = Path(settings.SESSIONS_DIR)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_path = sessions_dir / f"{platform}_session.json"

    logger.info(f"\n{'='*60}")
    logger.info(f"  Saving session for: {platform.upper()}")
    logger.info(f"{'='*60}")
    logger.info("  A browser window will open.")
    logger.info("  → Log in manually (email + password + any CAPTCHA/OTP)")
    logger.info("  → Once you are fully logged in, come back here and press Enter")
    logger.info(f"{'='*60}\n")

    async with async_playwright() as p:
        # IMPORTANT: headless=False so you can see and interact with the browser
        # Use channel="chrome" to use the real installed Chrome instead of Playwright's bundled Chromium
        # This fixes SIGBUS crashes on macOS ARM
        browser = await p.chromium.launch(headless=False, slow_mo=200, channel="chrome")
        context = await browser.new_context(
            # Pretend to be a real Chrome browser
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # Navigate to login page
        await page.goto(login_url, wait_until="domcontentloaded")
        logger.info(f"Browser opened: {login_url}")

        # Wait for user to manually log in
        input("\n  ✋ Log in manually in the browser, then press Enter here... ")

        # Verify login succeeded by checking current URL
        current_url = page.url
        success_indicators = ("/feed", "/mynetwork", "/jobs", "/home")
        if not any(ind in current_url for ind in success_indicators):
            logger.warning(
                f"  ⚠  It looks like you may not be fully logged in yet ({current_url})."
            )
            proceed = input("  Are you sure you're logged in? (y/n): ").strip().lower()
            if proceed != "y":
                logger.error("  Session NOT saved. Please try again after logging in.")
                await browser.close()
                return

        # Save the session
        storage_state = await context.storage_state()
        import json
        with open(session_path, "w") as f:
            json.dump(storage_state, f, indent=2)

        cookie_count = len(storage_state.get("cookies", []))
        logger.success(f"\n  ✅ Session saved! ({cookie_count} cookies)")
        logger.success(f"  📁 File: {session_path}")
        logger.info(f"  The pipeline will now skip {platform} login on every future run.\n")

        await browser.close()


# ── CLI commands ───────────────────────────────────────────────────────────────

@app.command()
def save(
    platform: str = typer.Option(
        ...,
        "--platform", "-p",
        help="Platform to save session for: linkedin | internshala | naukri | wellfound | all",
    )
) -> None:
    """Open browser, let you log in manually, and save the session."""

    if platform == "all":
        for p in PLATFORM_URLS:
            asyncio.run(_save_session_for(p))
            print()
    else:
        asyncio.run(_save_session_for(platform))


@app.command()
def status() -> None:
    """Show which platforms have saved sessions."""
    sessions_dir = Path(settings.SESSIONS_DIR)
    print("\n  Platform Session Status")
    print("  " + "─" * 40)
    for platform in PLATFORM_URLS:
        session_file = sessions_dir / f"{platform}_session.json"
        if session_file.exists():
            size = session_file.stat().st_size
            print(f"  ✅ {platform:<15} session saved  ({size:,} bytes)")
        else:
            print(f"  ❌ {platform:<15} no session — run save_session --platform {platform}")
    print()


@app.command()
def clear(
    platform: str = typer.Option(
        ...,
        "--platform", "-p",
        help="Platform to clear session for: linkedin | internshala | naukri | wellfound | all",
    )
) -> None:
    """Delete a saved session — forces fresh login on next pipeline run."""
    sessions_dir = Path(settings.SESSIONS_DIR)

    targets = list(PLATFORM_URLS.keys()) if platform == "all" else [platform]
    for p in targets:
        session_file = sessions_dir / f"{p}_session.json"
        if session_file.exists():
            session_file.unlink()
            logger.info(f"  🗑  Deleted session for {p}")
        else:
            logger.info(f"  ℹ  No session found for {p}")


if __name__ == "__main__":
    app()
