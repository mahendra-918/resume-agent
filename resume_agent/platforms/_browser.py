from __future__ import annotations

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from resume_agent.core.config import settings


class BrowserPool:
    """Shared Chromium browser + context for a single search run."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserPool":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.HEADLESS,
            slow_mo=settings.BROWSER_SLOW_MO,
        )
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self) -> Page:
        assert self._context is not None, "BrowserPool not started"
        return await self._context.new_page()

    @property
    def context(self) -> BrowserContext:
        assert self._context is not None, "BrowserPool not started"
        return self._context
