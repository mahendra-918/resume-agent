from __future__ import annotations

import asyncio
import os
from pathlib import Path

from loguru import logger

from resume_agent.core.config import settings
from resume_agent.core.state import AgentState

APPLIER_DIR = Path(__file__).parent.parent.parent / "linkedin_applier"


async def apply_linkedin_node(state: AgentState) -> dict:
    if state.get("dry_run"):
        logger.info("[LinkedIn] dry_run=True, skipping apply")
        return {}

    job = state.get("current_job")
    if not job:
        return {}

    if not job.url or "linkedin.com" not in job.url:
        logger.info(f"[LinkedIn] Skipping non-LinkedIn job: {job.title} @ {job.company}")
        return {}

    if job.is_easy_apply is False:
        logger.info(f"[LinkedIn] Skipping non-Easy-Apply job: {job.title} @ {job.company}")
        return {}

    resume_path = state.get("resume_path") or ""

    env = {
        **os.environ,
        "LINKEDIN_EMAIL": settings.LINKEDIN_EMAIL,
        "LINKEDIN_PASSWORD": settings.LINKEDIN_PASSWORD,
        "LINKEDIN_PHONE": settings.LINKEDIN_PHONE,
        "LINKEDIN_JOB_URL": job.url,
        "LINKEDIN_RESUME_PATH": str(Path(resume_path).resolve()) if resume_path else "",
    }

    script = APPLIER_DIR / "apply.js"

    logger.info(f"[LinkedIn] Applying for '{job.title}' @ {job.company} → {job.url}")

    try:
        proc = await asyncio.create_subprocess_exec(
            "node", str(script),
            cwd=str(APPLIER_DIR),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        output = stdout.decode(errors="replace") if stdout else ""
        for line in output.splitlines():
            logger.info(f"[LinkedIn] {line}")

        if proc.returncode != 0:
            logger.error(f"[LinkedIn] apply.js exited with code {proc.returncode}")
            errors = state.get("errors") or []
            return {"errors": errors + [f"LinkedIn apply failed for {job.title} @ {job.company}"]}

    except FileNotFoundError:
        logger.error("[LinkedIn] 'node' not found. Run: cd linkedin_applier && npm install && npx playwright install chromium")
        errors = state.get("errors") or []
        return {"errors": errors + ["node not found — LinkedIn apply skipped"]}

    return {}
