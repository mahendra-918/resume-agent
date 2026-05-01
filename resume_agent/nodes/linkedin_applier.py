from __future__ import annotations

import json
import random
from pathlib import Path

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.state import AgentState


_SESSIONS_DIR = Path("output/sessions")
_COOKIES_FILE = _SESSIONS_DIR / "linkedin_cookies.json"

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_EASY_APPLY_SELECTORS = [
    'button[aria-label*="Easy Apply"]',
    'button[aria-label*="easy apply"]',
    "button.jobs-apply-button",
    ".jobs-s-apply button",
    # Broad fallback — any visible button whose text contains "Easy Apply"
    "button",   # handled separately via text scan
]

_LOGIN_WALL_PATTERNS = ("/login", "/authwall", "/checkpoint", "/uas/login")

# ── browser singleton ─────────────────────────────────────────────────────────
# We keep one browser + page alive across all apply attempts in a single run
# so the user only sees one window and we don't pay per-job launch overhead.
_browser_ctx: dict = {}   # keys: "pw", "browser", "page", "logged_in"


async def _human_click(page, element) -> None:
    box = await element.bounding_box()
    if box:
        x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
        y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)
        await page.mouse.move(x + random.uniform(-20, 20), y + random.uniform(-20, 20))
        await page.mouse.move(x, y)
    await element.click()


async def _save_cookies(page) -> None:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    cookies = await page.context.cookies()
    _COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    logger.info("[LinkedIn] Cookies saved → {}", _COOKIES_FILE)


async def _load_cookies(context) -> bool:
    if not _COOKIES_FILE.exists():
        return False
    try:
        cookies = json.loads(_COOKIES_FILE.read_text())
        await context.add_cookies(cookies)
        logger.info("[LinkedIn] Loaded {} saved cookies", len(cookies))
        return True
    except Exception as e:
        logger.warning("[LinkedIn] Failed to load cookies: {}", e)
        return False


async def _ensure_browser(resume_pdf: str | None) -> tuple | None:
    """Return (browser, page) — launching + logging in if needed.

    Returns None if setup fails.
    """
    global _browser_ctx

    if _browser_ctx.get("page"):
        return _browser_ctx["browser"], _browser_ctx["page"]

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("[LinkedIn] playwright not installed — run: pip install playwright && playwright install chromium")
        return None

    try:
        from playwright_stealth import stealth_async as _stealth
    except ImportError:
        _stealth = None
        logger.warning("[LinkedIn] playwright-stealth not installed — bot detection may trigger")

    pw = await async_playwright().start()

    # Playwright's bundled Chromium crashes with SIGBUS on Apple Silicon (M1/M2/M3).
    # Use the system-installed Google Chrome instead via channel="chrome".
    # Falls back to bundled Chromium if Chrome is not installed.
    try:
        browser = await pw.chromium.launch(headless=False, slow_mo=300, channel="chrome")
        logger.info("[LinkedIn] Using system Google Chrome")
    except Exception as chrome_err:
        logger.warning("[LinkedIn] System Chrome not found ({}), falling back to bundled Chromium", chrome_err)
        browser = await pw.chromium.launch(headless=False, slow_mo=300)

    context = await browser.new_context(
        user_agent=_USER_AGENT,
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = await context.new_page()

    if _stealth:
        await _stealth(page)

    cookies_loaded = await _load_cookies(context)

    if not cookies_loaded:
        if not settings.LINKEDIN_EMAIL or not settings.LINKEDIN_PASSWORD:
            logger.warning("[LinkedIn] No credentials configured — set LINKEDIN_EMAIL / LINKEDIN_PASSWORD in Settings")
            await browser.close()
            await pw.stop()
            return None
        await _do_login(page)

    _browser_ctx = {"pw": pw, "browser": browser, "page": page}
    return browser, page


async def _do_login(page) -> None:
    logger.info("[LinkedIn] Logging in…")
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)
    await page.fill('input[name="session_key"]', settings.LINKEDIN_EMAIL)
    await page.fill('input[name="session_password"]', settings.LINKEDIN_PASSWORD)

    sign_in = await page.query_selector('button[type="submit"]')
    if sign_in:
        await _human_click(page, sign_in)

    try:
        await page.wait_for_url("**/feed/**", timeout=20_000)
        logger.info("[LinkedIn] Login successful")
    except Exception:
        logger.warning("[LinkedIn] Login timeout — you may need to complete CAPTCHA. Waiting 40s…")
        await page.wait_for_timeout(40_000)

    await _save_cookies(page)


def _is_login_wall(url: str) -> bool:
    return any(p in url for p in _LOGIN_WALL_PATTERNS)


async def _ensure_logged_in(page) -> bool:
    """Navigate to LinkedIn feed to verify session. Returns True if logged in."""
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15_000)
    except Exception:
        pass  # partial load is fine — just check the URL
    await page.wait_for_timeout(1500)
    current = page.url
    if _is_login_wall(current):
        logger.info("[LinkedIn] Not logged in — performing login")
        if not settings.LINKEDIN_EMAIL or not settings.LINKEDIN_PASSWORD:
            return False
        await _do_login(page)
        # Verify login succeeded
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15_000)
        await page.wait_for_timeout(1500)
        return not _is_login_wall(page.url)
    logger.info("[LinkedIn] Session active — logged in")
    return True


async def _find_easy_apply_button(page):
    """Find the Easy Apply button using multiple strategies."""

    # Extra wait for JS to render the apply section
    await page.wait_for_timeout(3000)

    # Scroll to trigger any lazy-loaded content
    try:
        await page.evaluate("window.scrollBy(0, 400)")
        await page.wait_for_timeout(1000)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)
    except Exception:
        pass

    # ── Strategy 1: Playwright locator with text match (most reliable) ─────────
    try:
        loc = page.get_by_role("button", name="Easy Apply", exact=False)
        if await loc.count() > 0:
            btn = loc.first
            if await btn.is_visible():
                logger.info("[LinkedIn] Found Easy Apply via get_by_role locator")
                return await btn.element_handle()
    except Exception as e:
        logger.debug("[LinkedIn] locator strategy failed: {}", e)

    # ── Strategy 2: aria-label CSS selector ───────────────────────────────────
    for sel in [
        'button[aria-label*="Easy Apply"]',
        'button[aria-label*="easy apply"]',
        'button[aria-label*="Easy apply"]',
    ]:
        try:
            btn = await page.wait_for_selector(sel, timeout=5_000)
            if btn and await btn.is_visible():
                logger.info("[LinkedIn] Found Easy Apply via aria-label: {}", sel)
                return btn
        except Exception:
            pass

    # ── Strategy 3: Full JS scan of every clickable element ───────────────────
    try:
        handle = await page.evaluate_handle("""() => {
            const selectors = 'button, [role="button"], a[href*="apply"]';
            const els = [...document.querySelectorAll(selectors)];
            for (const el of els) {
                const text = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
                if (text.includes('easy apply')) {
                    el.style.outline = '3px solid lime';
                    return el;
                }
            }
            return null;
        }""")
        btn = handle.as_element()
        if btn:
            visible = await btn.is_visible()
            logger.info("[LinkedIn] JS scan found Easy Apply element — visible={}", visible)
            if visible:
                return btn
    except Exception as e:
        logger.warning("[LinkedIn] JS scan failed: {}", e)

    # ── Debug: screenshot + page source snippet ────────────────────────────────
    try:
        title = await page.title()
        url   = page.url
        logger.warning("[LinkedIn] No Easy Apply found on '{}' @ {}", title, url)

        # Save a screenshot so the user can see what the browser sees
        ss_path = Path("output/sessions/debug_screenshot.png")
        ss_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(ss_path), full_page=False)
        logger.info("[LinkedIn] Debug screenshot saved → {}", ss_path)
    except Exception:
        pass

    return None


async def _fill_form_fields(page, state: dict) -> None:
    """Auto-fill any visible form fields in the Easy Apply modal."""

    # ── Text / number inputs ──────────────────────────────────────────────────
    inputs = await page.query_selector_all("input:not([type='file']):not([type='hidden']):not([type='checkbox']):not([type='radio'])")
    for inp in inputs:
        try:
            if not await inp.is_visible():
                continue
            label_text = ""
            # Try to find associated label
            inp_id = await inp.get_attribute("id")
            if inp_id:
                lbl = await page.query_selector(f'label[for="{inp_id}"]')
                if lbl:
                    label_text = (await lbl.inner_text()).strip().lower()
            # Fallback: aria-label on the input itself
            if not label_text:
                label_text = (await inp.get_attribute("aria-label") or "").lower()
            if not label_text:
                placeholder = (await inp.get_attribute("placeholder") or "").lower()
                label_text = placeholder

            current_val = await inp.input_value()
            if current_val.strip():
                continue  # already filled

            # Fill based on detected field type
            if any(k in label_text for k in ("phone", "mobile", "contact number")):
                value = state.get("phone", "9000000000")
            elif any(k in label_text for k in ("year", "experience", "how many")):
                value = state.get("experience_years", "1")
            elif any(k in label_text for k in ("salary", "compensation", "ctc", "expected")):
                value = state.get("expected_salary", "50000")
            elif any(k in label_text for k in ("city", "location", "where")):
                value = state.get("location", "Remote")
            elif any(k in label_text for k in ("linkedin", "profile url")):
                value = state.get("linkedin_url", "")
            elif any(k in label_text for k in ("github", "portfolio", "website")):
                value = state.get("portfolio", state.get("github", ""))
            elif any(k in label_text for k in ("gpa", "grade", "cgpa")):
                value = state.get("gpa", "8.5")
            elif any(k in label_text for k in ("first name", "firstname")):
                value = state.get("first_name", "")
            elif any(k in label_text for k in ("last name", "lastname", "surname")):
                value = state.get("last_name", "")
            elif "name" in label_text:
                value = state.get("full_name", "")
            elif any(k in label_text for k in ("email", "e-mail")):
                value = state.get("email", "")
            else:
                value = None

            if value:
                await inp.triple_click()
                await inp.type(str(value), delay=40)
                logger.debug("[LinkedIn] Filled '{}' with '{}'", label_text, value)
        except Exception:
            pass

    # ── Textareas ─────────────────────────────────────────────────────────────
    textareas = await page.query_selector_all("textarea")
    for ta in textareas:
        try:
            if not await ta.is_visible():
                continue
            if (await ta.input_value()).strip():
                continue
            label_text = (await ta.get_attribute("aria-label") or "").lower()
            if any(k in label_text for k in ("cover", "summary", "why", "about")):
                await ta.fill(state.get("summary", "I am excited to apply for this role."))
        except Exception:
            pass

    # ── Dropdowns (select) ─────────────────────────────────────────────────────
    selects = await page.query_selector_all("select")
    for sel_el in selects:
        try:
            if not await sel_el.is_visible():
                continue
            # Get all options and pick a non-empty, non-placeholder one
            options = await sel_el.query_selector_all("option")
            chosen = None
            for opt in options:
                val  = await opt.get_attribute("value") or ""
                text = (await opt.inner_text()).strip().lower()
                if val and val not in ("", "select", "please select", "none"):
                    # Prefer "yes", "bachelor", "full-time" type answers
                    if any(k in text for k in ("yes", "bachelor", "full time", "full-time", "1", "currently")):
                        chosen = val
                        break
                    if chosen is None:
                        chosen = val
            if chosen:
                await sel_el.select_option(chosen)
                logger.debug("[LinkedIn] Selected dropdown option: {}", chosen)
        except Exception:
            pass

    # ── Radio buttons — pick "Yes" where possible ─────────────────────────────
    try:
        radios = await page.query_selector_all('input[type="radio"]')
        # Group by name and select the "yes"-like option in each group
        groups: dict[str, list] = {}
        for r in radios:
            name = await r.get_attribute("name") or "unnamed"
            groups.setdefault(name, []).append(r)

        for name, group in groups.items():
            already_checked = any([await r.is_checked() for r in group])
            if already_checked:
                continue
            for r in group:
                lbl_text = ""
                r_id = await r.get_attribute("id")
                if r_id:
                    lbl = await page.query_selector(f'label[for="{r_id}"]')
                    if lbl:
                        lbl_text = (await lbl.inner_text()).strip().lower()
                if any(k in lbl_text for k in ("yes", "i am", "i have", "currently", "agree")):
                    await r.check()
                    logger.debug("[LinkedIn] Checked radio '{}'", lbl_text)
                    break
            else:
                # No "yes" found — just check the first option
                if group:
                    try:
                        await group[0].check()
                    except Exception:
                        pass
    except Exception:
        pass


async def _handle_modal(page, resume_pdf: str | None, state: dict | None = None) -> bool:
    state = state or {}

    for step in range(15):
        await page.wait_for_timeout(1500)

        # Upload resume if file input visible
        file_input = await page.query_selector('input[type="file"]')
        if file_input and resume_pdf and Path(resume_pdf).exists():
            try:
                await file_input.set_input_files(resume_pdf)
                logger.info("[LinkedIn] Uploaded resume: {}", resume_pdf)
                await page.wait_for_timeout(1000)
            except Exception as e:
                logger.warning("[LinkedIn] Resume upload failed: {}", e)

        # Auto-fill any form fields on this step
        await _fill_form_fields(page, state)
        await page.wait_for_timeout(500)

        # Submit
        for sel in [
            'button[aria-label="Submit application"]',
            'button[aria-label*="Submit"]',
        ]:
            submit = await page.query_selector(sel)
            if submit and await submit.is_visible():
                await _human_click(page, submit)
                logger.info("[LinkedIn] Application submitted at step {}", step + 1)
                await page.wait_for_timeout(2000)
                return True
        # Fallback: button whose text is exactly "Submit application"
        try:
            sub_loc = page.get_by_role("button", name="Submit application", exact=False)
            if await sub_loc.count() > 0 and await sub_loc.first.is_visible():
                await sub_loc.first.click()
                logger.info("[LinkedIn] Submitted via locator at step {}", step + 1)
                await page.wait_for_timeout(2000)
                return True
        except Exception:
            pass

        # Review
        clicked = False
        for sel in ['button[aria-label="Review your application"]', 'button[aria-label*="Review"]']:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await _human_click(page, btn)
                clicked = True
                break
        if clicked:
            continue

        # Next
        for sel in ['button[aria-label="Continue to next step"]', 'button[aria-label*="Next"]']:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await _human_click(page, btn)
                clicked = True
                break
        if not clicked:
            try:
                next_loc = page.get_by_role("button", name="Next", exact=False)
                if await next_loc.count() > 0 and await next_loc.first.is_visible():
                    await next_loc.first.click()
                    clicked = True
            except Exception:
                pass
        if clicked:
            continue

        # Dismiss / error dialog — close it and report failure
        dismiss = await page.query_selector('button[aria-label="Dismiss"]')
        if dismiss and await dismiss.is_visible():
            logger.warning("[LinkedIn] Dismiss dialog appeared at step {} — closing", step + 1)
            await _human_click(page, dismiss)
            return False

        logger.warning("[LinkedIn] No recognizable button at step {}", step + 1)
        break

    return False


async def _close_browser() -> None:
    global _browser_ctx
    if _browser_ctx.get("browser"):
        try:
            page = _browser_ctx.get("page")
            if page:
                await _save_cookies(page)
            await _browser_ctx["browser"].close()
        except Exception:
            pass
        try:
            await _browser_ctx["pw"].stop()
        except Exception:
            pass
    _browser_ctx = {}


# ── Maximum per-run apply attempts (prevents 20 browser navigations) ──────────
_MAX_APPLY_ATTEMPTS = 5


async def apply_linkedin_node(state: AgentState) -> dict:
    apply_results = list(state.get("apply_results") or [])
    job = state.get("current_job")
    if not job:
        return {"apply_results": apply_results}

    # Skip if apply is disabled
    if not state.get("apply_enabled", False):
        return {"apply_results": apply_results}

    # Only LinkedIn
    if job.platform.value != "linkedin":
        return {"apply_results": apply_results}

    # Limit total apply attempts per run
    attempted = sum(1 for r in apply_results if r.get("status") in ("applied", "failed"))
    if attempted >= _MAX_APPLY_ATTEMPTS:
        logger.info("[LinkedIn] Apply limit ({}) reached — skipping {}", _MAX_APPLY_ATTEMPTS, job.title)
        apply_results.append({"job_title": job.title, "company": job.company, "status": "skipped", "error": f"apply limit ({_MAX_APPLY_ATTEMPTS}) reached"})
        return {"apply_results": apply_results}

    # Find PDF
    resume_pdf: str | None = None
    tailored = state.get("tailored_resume")
    if tailored and getattr(tailored, "file_path", None):
        resume_pdf = tailored.file_path
    else:
        packages = state.get("packages") or []
        if packages:
            resume_pdf = packages[-1].tailored_resume_path

    result_entry = {"job_title": job.title, "company": job.company, "status": "skipped", "error": None}

    try:
        pair = await _ensure_browser(resume_pdf)
        if pair is None:
            result_entry["error"] = "No LinkedIn credentials configured"
            apply_results.append(result_entry)
            return {"apply_results": apply_results}

        _, page = pair

        # Verify/restore session before navigating to job (handles cookie expiry)
        logged_in = await _ensure_logged_in(page)
        if not logged_in:
            result_entry["error"] = "LinkedIn login failed — check credentials in Settings"
            logger.error("[LinkedIn] Login failed — skipping apply")
            apply_results.append(result_entry)
            return {"apply_results": apply_results}

        logger.info("[LinkedIn] Navigating to job: {}", job.url)
        try:
            await page.goto(job.url, wait_until="domcontentloaded", timeout=20_000)
        except Exception as nav_err:
            # domcontentloaded can still timeout on slow connections — try bare load
            logger.warning("[LinkedIn] domcontentloaded timeout, retrying with load: {}", nav_err)
            try:
                await page.goto(job.url, wait_until="load", timeout=20_000)
            except Exception:
                # Page already partially loaded — proceed anyway
                pass
        await page.wait_for_timeout(4000)  # let JS render the apply button

        # If LinkedIn redirected us to a login wall after job navigation, re-login
        if _is_login_wall(page.url):
            logger.warning("[LinkedIn] Redirected to login wall on job page — re-logging in")
            await _do_login(page)
            try:
                await page.goto(job.url, wait_until="domcontentloaded", timeout=20_000)
            except Exception:
                pass
            await page.wait_for_timeout(4000)

        # Check if already applied to this job
        already_applied = await page.evaluate("""() => {
            const body = document.body.innerText || '';
            return body.includes('Application submitted') ||
                   body.includes('تم إرسال طلب التقديم') ||
                   body.includes('Applied') ||
                   !!document.querySelector('.jobs-applied-badge, .artdeco-inline-feedback--success');
        }""")
        if already_applied:
            logger.info("[LinkedIn] Already applied to {} @ {}", job.title, job.company)
            result_entry["status"] = "applied"
            result_entry["error"] = "Already applied (previous run)"
            apply_results.append(result_entry)
            return {"apply_results": apply_results}

        easy_apply_btn = await _find_easy_apply_button(page)
        if not easy_apply_btn:
            logger.info("[LinkedIn] No Easy Apply button — {}", job.title)
            result_entry["error"] = "Easy Apply not available"
            apply_results.append(result_entry)
            return {"apply_results": apply_results}

        logger.info("[LinkedIn] Easy Apply found → clicking for {} @ {}", job.title, job.company)
        await _human_click(page, easy_apply_btn)
        await page.wait_for_timeout(2000)

        # Build candidate info for form auto-fill
        parsed = state.get("parsed_resume")
        name_parts = (parsed.name if parsed else "").split()
        fill_state = {
            "full_name":        parsed.name if parsed else "",
            "first_name":       name_parts[0] if name_parts else "",
            "last_name":        name_parts[-1] if len(name_parts) > 1 else "",
            "email":            parsed.email if parsed else settings.LINKEDIN_EMAIL,
            "phone":            parsed.phone or "9000000000",
            "location":         parsed.location or "Remote",
            "linkedin_url":     parsed.linkedin or "",
            "github":           parsed.github or "",
            "portfolio":        parsed.portfolio or "",
            "gpa":              "8.5",
            "experience_years": "0",
            "expected_salary":  "500000",
            "summary":          parsed.summary[:300] if parsed else "",
        }

        submitted = await _handle_modal(page, resume_pdf, fill_state)

        if submitted:
            result_entry["status"] = "applied"
            logger.success("[LinkedIn] Applied to {} @ {}", job.title, job.company)
        else:
            result_entry["status"] = "failed"
            result_entry["error"] = "Modal did not reach submit"
            logger.warning("[LinkedIn] Did not submit for {} @ {}", job.title, job.company)

    except Exception as e:
        err_str = str(e)
        logger.error("[LinkedIn] Apply error for {} @ {}: {}", job.title, job.company, err_str)
        result_entry["status"] = "failed"
        result_entry["error"] = err_str
        # Only reset the browser on hard crashes (closed context, process killed).
        # Navigation timeouts are recoverable — keep the same browser open.
        is_hard_crash = any(k in err_str for k in (
            "has been closed", "Target closed", "browser has disconnected",
            "Connection refused", "BrowserContext.new_page",
        ))
        if is_hard_crash:
            logger.warning("[LinkedIn] Hard browser crash — resetting context for next job")
            await _close_browser()

    apply_results.append(result_entry)

    # Close browser after the last job in the run
    jobs_filtered = state.get("jobs_filtered") or []
    current_index = state.get("current_job_index", 0)
    is_last_job = current_index >= len(jobs_filtered)
    if is_last_job:
        await _close_browser()

    return {"apply_results": apply_results}
