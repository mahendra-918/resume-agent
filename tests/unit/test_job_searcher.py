from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from resume_agent.core.models import Job, JobType, Platform
from resume_agent.core.state import AgentState


def _make_job(title: str, company: str, platform: Platform = Platform.LINKEDIN) -> Job:
    return Job(
        title=title,
        company=company,
        location="Remote",
        description="",
        url=f"https://example.com/{title.replace(' ', '-')}",
        platform=platform,
        job_type=JobType.INTERNSHIP,
    )


def _base_state(**overrides) -> AgentState:
    state: AgentState = {
        "resume_path": "resume.pdf",
        "resume_raw": "",
        "parsed_resume": None,
        "search_queries": ["python intern"],
        "jobs_found": [],
        "jobs_filtered": [],
        "current_job_index": 0,
        "current_job": None,
        "tailored_resume": None,
        "applications": [],
        "errors": [],
        "platform_status": {},
        "dry_run": True,
        "max_applications": 5,
    }
    state.update(overrides)
    return state


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_platform(name: str, jobs: list[Job]) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.search = AsyncMock(return_value=jobs)
    return p


def _mock_platform_raises(name: str, exc: Exception) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.search = AsyncMock(side_effect=exc)
    return p


# ── Tests ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dedup_across_platforms():
    """Same title+company from two platforms should appear only once."""
    job_a = _make_job("ML Intern", "Acme", Platform.LINKEDIN)
    job_b = _make_job("ML Intern", "Acme", Platform.INTERNSHALA)  # duplicate
    job_c = _make_job("Data Intern", "Beta", Platform.NAUKRI)

    linkedin = _mock_platform("linkedin", [job_a])
    naukri = _mock_platform("naukri", [job_c])
    internshala = _mock_platform("internshala", [job_b])
    wellfound = _mock_platform("wellfound", [])

    with (
        patch("resume_agent.nodes.job_searcher.settings") as mock_settings,
        patch("resume_agent.nodes.job_searcher.BrowserPool") as MockPool,
        patch("resume_agent.platforms.linkedin.LinkedInPlatform", return_value=linkedin),
        patch("resume_agent.platforms.internshala.IntershalaPlatform", return_value=internshala),
        patch("resume_agent.platforms.naukri.NaukriPlatform", return_value=naukri),
        patch("resume_agent.platforms.wellfound.WellfoundPlatform", return_value=wellfound),
    ):
        mock_settings.USE_LINKEDIN = True
        mock_settings.USE_INTERNSHALA = True
        mock_settings.USE_NAUKRI = True
        mock_settings.USE_WELLFOUND = True
        mock_settings.JOB_LOCATION = "Remote"
        mock_settings.JOB_TYPE = JobType.INTERNSHIP
        mock_settings.RESULTS_PER_PLATFORM = 20

        # BrowserPool context manager mock
        pool_instance = AsyncMock()
        pool_instance.__aenter__ = AsyncMock(return_value=pool_instance)
        pool_instance.__aexit__ = AsyncMock(return_value=None)
        pool_instance.context = MagicMock()
        MockPool.return_value = pool_instance

        from resume_agent.nodes.job_searcher import search_jobs_node

        # Patch platform constructors inside the node
        with (
            patch("resume_agent.nodes.job_searcher.LinkedInPlatform", return_value=linkedin),
            patch("resume_agent.nodes.job_searcher.NaukriPlatform", return_value=naukri),
            patch("resume_agent.nodes.job_searcher.IntershalaPlatform", return_value=internshala),
            patch("resume_agent.nodes.job_searcher.WellfoundPlatform", return_value=wellfound),
        ):
            result = await search_jobs_node(_base_state())

    jobs = result["jobs_found"]
    titles = [(j.title, j.company) for j in jobs]
    assert ("ML Intern", "Acme") in titles
    assert ("Data Intern", "Beta") in titles
    # Should appear only once despite two platforms returning it
    assert titles.count(("ML Intern", "Acme")) == 1


@pytest.mark.asyncio
async def test_platform_status_populated_for_all_active_platforms():
    """platform_status must have an entry for every enabled platform."""
    linkedin = _mock_platform("linkedin", [_make_job("SWE Intern", "Corp")])
    naukri = _mock_platform("naukri", [])
    internshala = _mock_platform("internshala", [])
    wellfound = _mock_platform("wellfound", [])

    with (
        patch("resume_agent.nodes.job_searcher.settings") as mock_settings,
        patch("resume_agent.nodes.job_searcher.BrowserPool") as MockPool,
    ):
        mock_settings.USE_LINKEDIN = True
        mock_settings.USE_INTERNSHALA = True
        mock_settings.USE_NAUKRI = True
        mock_settings.USE_WELLFOUND = True
        mock_settings.JOB_LOCATION = "Remote"
        mock_settings.JOB_TYPE = JobType.INTERNSHIP
        mock_settings.RESULTS_PER_PLATFORM = 20

        pool_instance = AsyncMock()
        pool_instance.__aenter__ = AsyncMock(return_value=pool_instance)
        pool_instance.__aexit__ = AsyncMock(return_value=None)
        pool_instance.context = MagicMock()
        MockPool.return_value = pool_instance

        from resume_agent.nodes.job_searcher import search_jobs_node

        with (
            patch("resume_agent.nodes.job_searcher.LinkedInPlatform", return_value=linkedin),
            patch("resume_agent.nodes.job_searcher.NaukriPlatform", return_value=naukri),
            patch("resume_agent.nodes.job_searcher.IntershalaPlatform", return_value=internshala),
            patch("resume_agent.nodes.job_searcher.WellfoundPlatform", return_value=wellfound),
        ):
            result = await search_jobs_node(_base_state())

    ps = result["platform_status"]
    for name in ("linkedin", "naukri", "internshala", "wellfound"):
        assert name in ps, f"{name} missing from platform_status"
        assert "count" in ps[name]
        assert "error" in ps[name]
        assert "duration_ms" in ps[name]


@pytest.mark.asyncio
async def test_platform_status_records_error_on_exception():
    """A platform that raises should record its error in platform_status."""
    linkedin = _mock_platform_raises("linkedin", RuntimeError("network timeout"))
    naukri = _mock_platform("naukri", [])
    internshala = _mock_platform("internshala", [])
    wellfound = _mock_platform("wellfound", [])

    with (
        patch("resume_agent.nodes.job_searcher.settings") as mock_settings,
        patch("resume_agent.nodes.job_searcher.BrowserPool") as MockPool,
    ):
        mock_settings.USE_LINKEDIN = True
        mock_settings.USE_INTERNSHALA = True
        mock_settings.USE_NAUKRI = True
        mock_settings.USE_WELLFOUND = True
        mock_settings.JOB_LOCATION = "Remote"
        mock_settings.JOB_TYPE = JobType.INTERNSHIP
        mock_settings.RESULTS_PER_PLATFORM = 20

        pool_instance = AsyncMock()
        pool_instance.__aenter__ = AsyncMock(return_value=pool_instance)
        pool_instance.__aexit__ = AsyncMock(return_value=None)
        pool_instance.context = MagicMock()
        MockPool.return_value = pool_instance

        from resume_agent.nodes.job_searcher import search_jobs_node

        with (
            patch("resume_agent.nodes.job_searcher.LinkedInPlatform", return_value=linkedin),
            patch("resume_agent.nodes.job_searcher.NaukriPlatform", return_value=naukri),
            patch("resume_agent.nodes.job_searcher.IntershalaPlatform", return_value=internshala),
            patch("resume_agent.nodes.job_searcher.WellfoundPlatform", return_value=wellfound),
        ):
            result = await search_jobs_node(_base_state())

    ps = result["platform_status"]
    assert ps["linkedin"]["error"] is not None
    assert "network timeout" in ps["linkedin"]["error"]
    assert ps["linkedin"]["count"] == 0


@pytest.mark.asyncio
async def test_platform_status_empty_result_flagged():
    """A platform that returns [] without raising should record error='empty_result'."""
    linkedin = _mock_platform("linkedin", [])
    naukri = _mock_platform("naukri", [])
    internshala = _mock_platform("internshala", [])
    wellfound = _mock_platform("wellfound", [])

    with (
        patch("resume_agent.nodes.job_searcher.settings") as mock_settings,
        patch("resume_agent.nodes.job_searcher.BrowserPool") as MockPool,
    ):
        mock_settings.USE_LINKEDIN = True
        mock_settings.USE_INTERNSHALA = False
        mock_settings.USE_NAUKRI = False
        mock_settings.USE_WELLFOUND = False
        mock_settings.JOB_LOCATION = "Remote"
        mock_settings.JOB_TYPE = JobType.INTERNSHIP
        mock_settings.RESULTS_PER_PLATFORM = 20

        pool_instance = AsyncMock()
        pool_instance.__aenter__ = AsyncMock(return_value=pool_instance)
        pool_instance.__aexit__ = AsyncMock(return_value=None)
        pool_instance.context = MagicMock()
        MockPool.return_value = pool_instance

        from resume_agent.nodes.job_searcher import search_jobs_node

        with (
            patch("resume_agent.nodes.job_searcher.LinkedInPlatform", return_value=linkedin),
            patch("resume_agent.nodes.job_searcher.NaukriPlatform", return_value=naukri),
            patch("resume_agent.nodes.job_searcher.IntershalaPlatform", return_value=internshala),
            patch("resume_agent.nodes.job_searcher.WellfoundPlatform", return_value=wellfound),
        ):
            result = await search_jobs_node(_base_state())

    assert result["platform_status"]["linkedin"]["error"] == "empty_result"
