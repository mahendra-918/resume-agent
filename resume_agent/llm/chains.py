import asyncio
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


async def _invoke_with_retry(chain, inputs: dict, label: str, max_retries: int = 4) -> str:
    """Invoke a LangChain chain with automatic retry on Groq 429 rate-limit errors.

    Distinguishes two kinds of Groq rate limits:
    - TPM (tokens per minute): wait a few seconds and retry — quota refills in 60s
    - TPD (tokens per day):    daily quota exhausted — pointless to retry, raise immediately

    Backoff starts at 6s because Groq's TPM error usually says "try again in 5s".
    """
    delay = 6  # seconds — first retry delay
    for attempt in range(1, max_retries + 1):
        try:
            response = await chain.ainvoke(inputs)
            return response.content
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate_limit_exceeded" in err_str
            is_daily_limit = "tokens per day" in err_str or "TPD" in err_str

            if is_rate_limit and is_daily_limit:
                # Daily quota exhausted — retrying won't help, fail fast
                logger.error(
                    f"[LLM] {label} — daily token limit (TPD) exhausted. "
                    f"Resets at midnight UTC (5:30 AM IST). Skipping this job."
                )
                raise

            if is_rate_limit and attempt < max_retries:
                logger.warning(
                    f"[LLM] {label} — rate limit hit (attempt {attempt}/{max_retries}). "
                    f"Retrying in {delay}s…"
                )
                await asyncio.sleep(delay)
                delay *= 2   # exponential backoff: 6 → 12 → 24 → 48
            else:
                raise   # non-429 error or all retries exhausted — re-raise



async def run_resume_parse_chain(resume_text: str) -> dict:
    try:
        chain = RESUME_PARSE_PROMPT | get_llm()
        content = await _invoke_with_retry(chain, {"resume_text": resume_text}, "resume parse")
        return _parse_json(content)
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
        content = await _invoke_with_retry(chain, {
            "target_roles": ", ".join(target_roles),
            "top_skills": ", ".join(top_skills[:15]),
            "experience_summary": experience_summary,
        }, "query generation")
        result = _parse_json(content)
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
        content = await _invoke_with_retry(chain, {
            "candidate_skills": ", ".join(candidate_skills),
            "candidate_experience": candidate_experience,
            "job_title": job_title,
            "job_description": job_description[:2000],
        }, f"job rank ({job_title})")
        return _parse_json(content)
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
        content = await _invoke_with_retry(chain, {
            "job_title": job_title,
            "company": company,
            "job_description": job_description[:3000],
            "resume_json": resume_json,
        }, f"resume tailor ({job_title} @ {company})")
        return _parse_json(content)
    except Exception as e:
        logger.error(f"[LLM] Resume tailoring failed: {e}")
        raise LLMError(f"Resume tailoring failed: {e}") from e