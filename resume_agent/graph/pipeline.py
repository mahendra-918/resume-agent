from __future__ import annotations

import datetime
from typing import Callable, Awaitable, Any

from loguru import logger
from langgraph.graph import StateGraph, START, END

from resume_agent.core.config import settings
from resume_agent.core.models import ApplicationStatus
from resume_agent.core.state import AgentState
from resume_agent.db.repository import save_application, is_already_applied
from resume_agent.graph.checkpointer import get_checkpointer
from resume_agent.nodes.resume_parser import parse_resume_node
from resume_agent.nodes.query_generator import generate_queries_node
from resume_agent.nodes.job_searcher import search_jobs_node
from resume_agent.nodes.job_ranker import rank_jobs_node
from resume_agent.nodes.resume_tailor import tailor_resume_node
from resume_agent.nodes.job_applier import apply_job_node



async def process_next_job_node(state: AgentState) -> dict:
    index: int = state.get("current_job_index", 0)
    jobs = state["jobs_filtered"]
    current_job = jobs[index]

    # ── De-duplication check ──────────────────────────────────────────────────
    # Before spending LLM tokens tailoring and applying, check if we already
    # successfully applied to this exact job URL in a previous run.
    if await is_already_applied(current_job.url):
        logger.info(
            f"[Pipeline] Skipping duplicate: {current_job.title} @ {current_job.company} "
            f"(already applied in a previous run)"
        )
        # Advance the index but set current_job to None so tailor/apply are skipped
        return {"current_job": None, "current_job_index": index + 1}

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


async def print_summary_node(state: AgentState, emit: Callable | None = None) -> dict:
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



def _has_jobs(state: AgentState) -> str:
    return "process_next_job" if state.get("jobs_filtered") else END


def _more_jobs(state: AgentState) -> str:
    index = state.get("current_job_index", 0)
    jobs = state.get("jobs_filtered") or []
    return "process_next_job" if index < len(jobs) else "print_summary"



def _build_graph(emit: Callable | None = None) -> StateGraph:
    """Build the LangGraph StateGraph.

    `emit` is an optional async callable — when provided, each node is wrapped
    so it fires a WebSocket progress event after completing.
    When emit is None (CLI mode), nodes run unchanged — no events fired.
    """
    g = StateGraph(AgentState)

    # ── Node wrapper factory ───────────────────────────────────────────────────
    # Instead of copy-pasting the same try/emit/return pattern 6 times,
    # we use a factory: _node(fn, event_builder) returns a new async function
    # that runs fn(state), then emits the event returned by event_builder.
    #
    # event_builder(state, result) → dict
    #   state  = full AgentState BEFORE the node ran
    #   result = the dict the node returned (the state DELTA)

    def _node(fn, event_builder):
        async def _wrapped(state: AgentState) -> dict:
            result = await fn(state)           # run the real node
            if emit:
                try:
                    event = event_builder(state, result)
                    await emit(event)          # fire the WebSocket event
                except Exception:
                    pass                       # never let emit crash the pipeline
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

    # ── 5. process_next_job ────────────────────────────────────────────────────
    # Emits which job is being picked up next so frontend knows the loop position
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

    # ── 6. tailor_resume ───────────────────────────────────────────────────────
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

    # ── 7. apply_to_job ────────────────────────────────────────────────────────
    # Uses "applied" type for rich frontend display (icon, colour)
    g.add_node("apply_to_job", _node(
        apply_job_node,
        lambda s, r: (
            {
                "type": "applied",
                "job":     r["applications"][-1].job.title    if r.get("applications") else "?",
                "company": r["applications"][-1].job.company  if r.get("applications") else "?",
                "status":  r["applications"][-1].status.value if r.get("applications") else "?",
                "file_path": r["applications"][-1].tailored_resume_path if r.get("applications") else None,
            }
            if r.get("applications")
            else {"type": "node_done", "node": "apply_to_job", "message": "Application processed"}
        )
    ))

    # ── 8. save_application (silent — DB write, no user-visible event) ─────────
    g.add_node("save_application", save_application_node)

    # ── 9. print_summary — fires the final "done" event ───────────────────────
    async def _summary_with_emit(state: AgentState) -> dict:
        result = await print_summary_node(state)
        if emit:
            applications = state.get("applications") or []
            await emit({
                "type": "done",
                "summary": {
                    "applied": sum(1 for a in applications if a.status == ApplicationStatus.APPLIED),
                    "skipped": sum(1 for a in applications if a.status == ApplicationStatus.SKIPPED),
                    "failed":  sum(1 for a in applications if a.status == ApplicationStatus.FAILED),
                    "total":   len(applications),
                }
            })
        return result

    g.add_node("print_summary", _summary_with_emit)

    # ── Edges (unchanged) ──────────────────────────────────────────────────────
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
    run_id: str = "",                          # unique ID for this run (from POST /run)
    emit: Callable[..., Awaitable[Any]] | None = None,  # broadcast() from api.py
) -> dict:
    """Initialise AgentState and run the full LangGraph pipeline.

    When `run_id` and `emit` are provided (i.e. triggered via the API),
    each node fires a WebSocket progress event to the connected frontend.
    When called from the CLI, both are None and progress is logged only.
    """

    # _emit wraps broadcast() so nodes just call await _emit({...})
    # without needing to know the run_id themselves.
    # If no emit is provided (CLI mode), this is a no-op.
    async def _emit(event: dict) -> None:
        if emit and run_id:
            event["ts"] = datetime.datetime.utcnow().isoformat()  # add timestamp
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
        "applications": [],
        "errors": [],
        "dry_run": dry_run,
        "max_applications": max_applications,
    }

    # Pass _emit into graph builder so nodes can reference it via closures
    graph_builder = _build_graph(emit=_emit)

    async with get_checkpointer() as checkpointer:
        graph = graph_builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": f"run-{resume_path}"}}
        logger.info(f"[Pipeline] Starting run — resume: {resume_path}, dry_run: {dry_run}")
        final_state = await graph.ainvoke(initial_state, config=config)

    logger.info("[Pipeline] Run finished.")
    return final_state
