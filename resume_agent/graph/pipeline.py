from __future__ import annotations

from loguru import logger
from langgraph.graph import StateGraph, START, END

from resume_agent.core.config import settings
from resume_agent.core.models import ApplicationStatus
from resume_agent.core.state import AgentState
from resume_agent.db.repository import save_application
from resume_agent.graph.checkpointer import get_checkpointer
from resume_agent.nodes.resume_parser import parse_resume_node
from resume_agent.nodes.query_generator import generate_queries_node
from resume_agent.nodes.job_searcher import search_jobs_node
from resume_agent.nodes.job_ranker import rank_jobs_node
from resume_agent.nodes.resume_tailor import tailor_resume_node
from resume_agent.nodes.job_applier import apply_job_node


# ── Inline nodes ───────────────────────────────────────────────────────────────

async def process_next_job_node(state: AgentState) -> dict:
    index: int = state.get("current_job_index", 0)
    jobs = state["jobs_filtered"]
    current_job = jobs[index]
    logger.info(
        f"[Pipeline] Processing job {index + 1}/{len(jobs)}: "
        f"{current_job.title} @ {current_job.company}"
    )
    return {"current_job": current_job, "current_job_index": index + 1}


async def save_application_node(state: AgentState) -> dict:
    applications = state.get("applications") or []
    if applications:
        latest = applications[-1]
        try:
            await save_application(latest)
            logger.info(
                f"[Pipeline] Saved application: {latest.job.title} @ {latest.job.company} "
                f"— {latest.status}"
            )
        except Exception as e:
            logger.error(f"[Pipeline] Failed to save application: {e}")
    return {}


async def print_summary_node(state: AgentState) -> dict:
    applications = state.get("applications") or []
    total = len(applications)
    applied = sum(1 for a in applications if a.status == ApplicationStatus.APPLIED)
    skipped = sum(1 for a in applications if a.status == ApplicationStatus.SKIPPED)
    failed = sum(1 for a in applications if a.status == ApplicationStatus.FAILED)

    logger.info(
        f"[Pipeline] ── Run complete ──────────────────────────────\n"
        f"  Jobs found:    {len(state.get('jobs_found') or [])}\n"
        f"  Jobs filtered: {len(state.get('jobs_filtered') or [])}\n"
        f"  Total processed: {total}\n"
        f"    ✓ Applied:  {applied}\n"
        f"    ⊘ Skipped:  {skipped}\n"
        f"    ✗ Failed:   {failed}\n"
        f"─────────────────────────────────────────────────────"
    )
    return {}


# ── Conditional edge functions ─────────────────────────────────────────────────

def _has_jobs(state: AgentState) -> str:
    return "process_next_job" if state.get("jobs_filtered") else END


def _more_jobs(state: AgentState) -> str:
    index = state.get("current_job_index", 0)
    jobs = state.get("jobs_filtered") or []
    return "process_next_job" if index < len(jobs) else "print_summary"


# ── Graph construction ─────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("parse_resume", parse_resume_node)
    g.add_node("generate_queries", generate_queries_node)
    g.add_node("search_jobs", search_jobs_node)
    g.add_node("rank_jobs", rank_jobs_node)
    g.add_node("process_next_job", process_next_job_node)
    g.add_node("tailor_resume", tailor_resume_node)
    g.add_node("apply_to_job", apply_job_node)
    g.add_node("save_application", save_application_node)
    g.add_node("print_summary", print_summary_node)

    g.add_edge(START, "parse_resume")
    g.add_edge("parse_resume", "generate_queries")
    g.add_edge("generate_queries", "search_jobs")
    g.add_edge("search_jobs", "rank_jobs")
    g.add_conditional_edges("rank_jobs", _has_jobs)
    g.add_edge("process_next_job", "tailor_resume")
    g.add_edge("tailor_resume", "apply_to_job")
    g.add_edge("apply_to_job", "save_application")
    g.add_conditional_edges("save_application", _more_jobs)
    g.add_edge("print_summary", END)

    return g


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_pipeline(
    resume_path: str,
    dry_run: bool = False,
    max_applications: int = 20,
) -> dict:
    """Initialise AgentState and run the full LangGraph pipeline."""
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
        "applications": [],
        "errors": [],
        "dry_run": dry_run,
        "max_applications": max_applications,
    }

    graph_builder = _build_graph()

    async with get_checkpointer() as checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": f"run-{resume_path}"}}
        logger.info(f"[Pipeline] Starting run — resume: {resume_path}, dry_run: {dry_run}")
        final_state = await graph.ainvoke(initial_state, config=config)

    logger.info("[Pipeline] Run finished.")
    return final_state
