import json
from loguru import logger
from resume_agent.llm.client import get_llm
from resume_agent.llm.prompts import (
    RESUME_PARSE_PROMPT,
    QUERY_GENERATOR_PROMPT,
    JOB_RANK_PROMPT,
    RESUME_TAILOR_PROMPT,
)
from resume_agent.core.exceptions import LLMError


def _parse_json(raw: str) -> dict | list:
    """Strip markdown fences and parse JSON."""
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


async def run_resume_parse_chain(resume_text: str) -> dict:
    try:
        chain = RESUME_PARSE_PROMPT | get_llm()
        response = await chain.ainvoke({"resume_text": resume_text})
        return _parse_json(response.content)
    except Exception as e:
        logger.error(f"[LLM] Resume parse failed: {e}")
        raise LLMError(f"Resume parse failed: {e}") from e


async def run_query_generator_chain(
    target_roles: list[str],
    top_skills: list[str],
    experience_summary: str,
) -> list[str]:
    try:
        chain = QUERY_GENERATOR_PROMPT | get_llm()
        response = await chain.ainvoke({
            "target_roles": ", ".join(target_roles),
            "top_skills": ", ".join(top_skills[:15]),
            "experience_summary": experience_summary,
        })
        result = _parse_json(response.content)
        return result if isinstance(result, list) else [result]
    except Exception as e:
        logger.error(f"[LLM] Query generation failed: {e}")
        raise LLMError(f"Query generation failed: {e}") from e


async def run_job_rank_chain(
    candidate_skills: list[str],
    candidate_experience: str,
    job_title: str,
    job_description: str,
) -> dict:
    try:
        chain = JOB_RANK_PROMPT | get_llm()
        response = await chain.ainvoke({
            "candidate_skills": ", ".join(candidate_skills),
            "candidate_experience": candidate_experience,
            "job_title": job_title,
            "job_description": job_description[:2000],
        })
        return _parse_json(response.content)
    except Exception as e:
        logger.error(f"[LLM] Job ranking failed: {e}")
        raise LLMError(f"Job ranking failed: {e}") from e


async def run_resume_tailor_chain(
    job_title: str,
    company: str,
    job_description: str,
    resume_json: str,
) -> dict:
    try:
        chain = RESUME_TAILOR_PROMPT | get_llm()
        response = await chain.ainvoke({
            "job_title": job_title,
            "company": company,
            "job_description": job_description[:3000],
            "resume_json": resume_json,
        })
        return _parse_json(response.content)
    except Exception as e:
        logger.error(f"[LLM] Resume tailoring failed: {e}")
        raise LLMError(f"Resume tailoring failed: {e}") from e