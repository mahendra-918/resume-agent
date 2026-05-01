from __future__ import annotations

import datetime
from typing import Callable, Awaitable, Any

from loguru import logger
from langgraph.graph import StateGraph, START, END

from resume_agent.core.config import settings
from resume_agent.core.state import AgentState
from resume_agent.graph.checkpointer import get_checkpointer
from resume_agent.nodes.resume_parser import parse_resume_node
from resume_agent.nodes.query_generator import generate_queries_node
from resume_agent.nodes.job_searcher import search_jobs_node
from resume_agent.nodes.job_ranker import rank_jobs_node
from resume_agent.nodes.resume_tailor import tailor_resume_node
from resume_agent.nodes.package_generator import generate_package_node
from resume_agent.nodes.linkedin_applier import apply_linkedin_node


async def process_next_job_node(state: AgentState) -> dict:
    index: int = state.get("current_job_index", 0)
    jobs = state["jobs_filtered"]
    current_job = jobs[index]

    logger.info(
        f"[Pipeline] Processing job {index + 1}/{len(jobs)}: "
        f"{current_job.title} @ {current_job.company}"
    )
    return {"current_job": current_job, "current_job_index": index + 1}


async def print_summary_node(state: AgentState) -> dict:
    packages = state.get("packages") or []
    logger.info(
        f"[Pipeline] ── Run complete ──────────────────────────────\n"
        f"  Jobs found:    {len(state.get('jobs_found') or [])}\n"
        f"  Jobs ranked:   {len(state.get('jobs_filtered') or [])}\n"
        f"  Packages generated: {len(packages)}\n"
        + "\n".join(
            f"    ✓ {p.job.title} @ {p.job.company} → {p.output_dir}"
            for p in packages
        ) +
        f"\n─────────────────────────────────────────────────────"
    )
    return {}


def _has_jobs(state: AgentState) -> str:
    return "process_next_job" if state.get("jobs_filtered") else END


def _more_jobs(state: AgentState) -> str:
    index = state.get("current_job_index", 0)
    jobs = state.get("jobs_filtered") or []
    return "process_next_job" if index < len(jobs) else "print_summary"


def _build_graph(emit: Callable | None = None) -> StateGraph:
    g = StateGraph(AgentState)

    def _node(fn, event_builder):
        async def _wrapped(state: AgentState) -> dict:
            result = await fn(state)
            if emit:
                try:
                    event = event_builder(state, result)
                    await emit(event)
                except Exception:
                    pass
            return result
        return _wrapped

    g.add_node("parse_resume", _node(
        parse_resume_node,
        lambda s, r: {
            "type": "node_done",
            "node": "parse_resume",
            "message": (
                f"Resume parsed for {r['parsed_resume'].name}"
                if r.get("parsed_resume") and r["parsed_resume"].name
                else "Resume parsed"
            ),
        }
    ))

    g.add_node("generate_queries", _node(
        generate_queries_node,
        lambda s, r: {
            "type": "node_done",
            "node": "generate_queries",
            "message": f"{len(r.get('search_queries', []))} search queries generated",
        }
    ))

    g.add_node("search_jobs", _node(
        search_jobs_node,
        lambda s, r: {
            "type": "node_done",
            "node": "search_jobs",
            "message": f"{len(r.get('jobs_found', []))} jobs found across all platforms",
            "platform_status": r.get("platform_status", {}),
        }
    ))

    g.add_node("rank_jobs", _node(
        rank_jobs_node,
        lambda s, r: {
            "type": "node_done",
            "node": "rank_jobs",
            "message": (
                f"{len(r.get('jobs_filtered', []))} jobs passed relevance threshold"
                f" (≥ {settings.MIN_RELEVANCE_SCORE})"
            ),
        }
    ))

    g.add_node("process_next_job", _node(
        process_next_job_node,
        lambda s, r: {
            "type": "node_done",
            "node": "process_next_job",
            "message": (
                f"Processing job {r.get('current_job_index', '?')}"
                f"/{len(s.get('jobs_filtered') or [])}: "
                f"{r['current_job'].title} @ {r['current_job'].company}"
                if r.get("current_job") else "Processing next job"
            ),
        }
    ))

    g.add_node("tailor_resume", _node(
        tailor_resume_node,
        lambda s, r: {
            "type": "node_done",
            "node": "tailor_resume",
            "message": (
                f"Resume tailored for "
                f"{r['tailored_resume'].job_title} @ {r['tailored_resume'].company}"
                if r.get("tailored_resume") else "Resume tailored"
            ),
        }
    ))

    # ── 7. generate_package ────────────────────────────────────────────────────
    g.add_node("generate_package", _node(
        generate_package_node,
        lambda s, r: {
            "type": "package_generated",
            "job":     r["packages"][-1].job.title   if r.get("packages") else "?",
            "company": r["packages"][-1].job.company if r.get("packages") else "?",
            "dir":     r["packages"][-1].output_dir  if r.get("packages") else None,
        }
    ))

    # ── 8. apply_linkedin ─────────────────────────────────────────────────────
    def _apply_event(s, r):
        results = r.get("apply_results") or []
        last = results[-1] if results else {}
        status  = last.get("status", "skipped")
        job     = last.get("job_title", "?")
        company = last.get("company", "?")
        error   = last.get("error", "")

        if status == "applied":
            msg = f"✅ Applied → {job} @ {company}"
        elif not s.get("apply_enabled"):
            msg = f"Apply disabled — {job} @ {company}"
        elif error == "Easy Apply not available":
            msg = f"No Easy Apply — {job} @ {company}"
        elif error == "No LinkedIn credentials configured":
            msg = f"⚠ Missing credentials — set LinkedIn email/password in Settings"
        elif error:
            msg = f"Apply error — {job} @ {company}: {error}"
        else:
            msg = f"Skipped apply — {job} @ {company}"

        return {
            "type":    status,        # "applied" | "skipped" | "failed"
            "job":     job,
            "company": company,
            "status":  status,
            "message": msg,
        }

    g.add_node("apply_linkedin", _node(apply_linkedin_node, _apply_event))

    async def _summary_with_emit(state: AgentState) -> dict:
        result = await print_summary_node(state)
        if emit:
            packages = state.get("packages") or []
            await emit({
                "type": "done",
                "summary": {
                    "jobs_found":  len(state.get("jobs_found") or []),
                    "jobs_ranked": len(state.get("jobs_filtered") or []),
                    "packages":    len(packages),
                    "output_dirs": [p.output_dir for p in packages if p.output_dir],
                }
            })
        return result

    g.add_node("print_summary", _summary_with_emit)

    g.add_edge(START, "parse_resume")
    g.add_edge("parse_resume", "generate_queries")
    g.add_edge("generate_queries", "search_jobs")
    g.add_edge("search_jobs", "rank_jobs")
    g.add_conditional_edges("rank_jobs", _has_jobs)
    g.add_edge("process_next_job", "tailor_resume")
    g.add_edge("tailor_resume", "generate_package")
    g.add_edge("generate_package", "apply_linkedin")
    g.add_conditional_edges("apply_linkedin", _more_jobs)
    g.add_edge("print_summary", END)

    return g


async def run_pipeline(
    resume_path: str,
    dry_run: bool = False,
    max_applications: int = 20,
    apply_enabled: bool = False,
    run_id: str = "",
    emit: Callable[..., Awaitable[Any]] | None = None,
) -> dict:
    async def _emit(event: dict) -> None:
        if emit and run_id:
            event["ts"] = datetime.datetime.utcnow().isoformat()
            await emit(run_id, event)

    initial_state: AgentState = {
        "resume_path": resume_path,
        "resume_raw": "",
        "parsed_resume": None,
        "search_queries": [],
        "jobs_found": [],
        "jobs_filtered": [],
        "current_job_index": 0,
        "current_job": None,
        "tailored_resume": None,
        "packages": [],
        "errors": [],
        "platform_status": {},
        "apply_enabled": apply_enabled,
        "apply_results": [],
        "dry_run": dry_run,
        "max_applications": max_applications,
    }

    graph_builder = _build_graph(emit=_emit)

    async with get_checkpointer() as checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)
        import uuid as _uuid
        config = {"configurable": {"thread_id": f"run-{_uuid.uuid4().hex}"}}
        logger.info(f"[Pipeline] Starting run — resume: {resume_path}, dry_run: {dry_run}")
        final_state = await graph.ainvoke(initial_state, config=config)

    logger.info("[Pipeline] Run finished.")
    return final_state
