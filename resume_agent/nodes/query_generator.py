from __future__ import annotations

from loguru import logger

from resume_agent.core.models import ParsedResume
from resume_agent.core.state import AgentState
from resume_agent.llm.chains import run_query_generator_chain


async def generate_queries_node(state: AgentState) -> dict:
    parsed: ParsedResume = state["parsed_resume"]

    top_skills = parsed.skills.all_skills()[:15]

    experience_summary = ""
    if parsed.experience:
        first = parsed.experience[0]
        experience_summary = f"{first.title} at {first.org} ({first.duration})"
        if first.highlights:
            experience_summary += ": " + "; ".join(first.highlights[:2])
    elif parsed.summary:
        experience_summary = parsed.summary[:300]

    logger.info(
        f"[QueryGenerator] Generating queries for roles: {parsed.target_roles}, "
        f"skills: {top_skills[:5]}..."
    )

    try:
        queries = await run_query_generator_chain(
            target_roles=parsed.target_roles,
            top_skills=top_skills,
            experience_summary=experience_summary,
        )
        logger.info(f"[QueryGenerator] Generated {len(queries)} queries")
        return {"search_queries": queries}
    except Exception as e:
        logger.error(f"[QueryGenerator] Failed: {e}")
        errors = list(state.get("errors") or [])
        errors.append(f"QueryGenerator: {e}")
        fallback = parsed.target_roles[:3] if parsed.target_roles else ["software engineer intern"]
        return {"search_queries": fallback, "errors": errors}
