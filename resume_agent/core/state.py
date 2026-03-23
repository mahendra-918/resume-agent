from typing import TypedDict, Optional
from resume_agent.core.models import (
    ParsedResume, Job, TailoredResume, ApplicationResult
)


class AgentState(TypedDict):
    # ── Input ─────────────────────────────────────────────────────────────────
    resume_path: str
    resume_raw: str
    parsed_resume: Optional[ParsedResume]

    # ── Job Search ────────────────────────────────────────────────────────────
    search_queries: list[str]
    jobs_found: list[Job]
    jobs_filtered: list[Job]

    # ── Per-job loop ──────────────────────────────────────────────────────────
    current_job_index: int
    current_job: Optional[Job]
    tailored_resume: Optional[TailoredResume]

    # ── Results ───────────────────────────────────────────────────────────────
    applications: list[ApplicationResult]
    errors: list[str]

    # ── Control ───────────────────────────────────────────────────────────────
    dry_run: bool
    max_applications: int