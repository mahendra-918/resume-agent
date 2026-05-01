from __future__ import annotations

from loguru import logger

from resume_agent.core.models import ParsedResume
from resume_agent.core.state import AgentState
from resume_agent.llm.chains import run_query_generator_chain


async def generate_queries_node(state: AgentState) -> dict:
    parsed: ParsedResume = state["parsed_resume"]

    top_skills = parsed.skills.all_skills()[:15]

    # Build a meaningful experience summary for the LLM
    experience_summary = ""
    if parsed.experience:
        first = parsed.experience[0]
        experience_summary = f"{first.title} at {first.org} ({first.duration})"
        if first.highlights:
            experience_summary += ": " + "; ".join(first.highlights[:2])
    elif parsed.summary:
        experience_summary = parsed.summary[:300]

    # Derive sensible fallback roles from skills if the LLM didn't extract any
    target_roles = parsed.target_roles or []
    if not target_roles:
        skills_lower = [s.lower() for s in top_skills]
        if any(k in skills_lower for k in ["langchain", "langgraph", "llm", "openai", "gemini"]):
            target_roles = ["AI Engineer", "ML Engineer", "Software Engineer"]
        elif any(k in skills_lower for k in ["react", "vue", "next.js", "typescript"]):
            target_roles = ["Frontend Engineer", "Software Engineer", "Web Developer"]
        elif any(k in skills_lower for k in ["fastapi", "django", "flask", "go", "node"]):
            target_roles = ["Backend Engineer", "Software Engineer", "Python Developer"]
        else:
            target_roles = ["Software Engineer", "Backend Developer", "Python Developer"]
        logger.warning(f"[QueryGenerator] No target_roles found — using fallback: {target_roles}")

    logger.info(
        f"[QueryGenerator] Generating queries for roles: {target_roles}, "
        f"skills: {top_skills[:5]}..."
    )

    try:
        queries = await run_query_generator_chain(
            target_roles=target_roles,
            top_skills=top_skills,
            experience_summary=experience_summary,
        )
        # Validate: strip out any query longer than 5 words (LLM hallucination guard)
        queries = [q for q in queries if isinstance(q, str) and len(q.split()) <= 5]
        if not queries:
            queries = [f"{r} Intern" for r in target_roles[:3]]
        logger.info(f"[QueryGenerator] Generated {len(queries)} queries: {queries}")
        return {"search_queries": queries}
    except Exception as e:
        logger.error(f"[QueryGenerator] Failed: {e}")
        errors = list(state.get("errors") or [])
        errors.append(f"QueryGenerator: {e}")
        fallback = [f"{r} Intern" for r in target_roles[:3]]
        return {"search_queries": fallback, "errors": errors}
