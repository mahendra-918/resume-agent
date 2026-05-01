import asyncio
import json
import re

from loguru import logger

from resume_agent.llm.client import get_llm
from resume_agent.llm.prompts import (
    RESUME_PARSE_PROMPT,
    QUERY_GENERATOR_PROMPT,
    JOB_RANK_PROMPT,
    RESUME_TAILOR_PROMPT,
    COVER_LETTER_PROMPT,
    EMAIL_DRAFT_PROMPT,
    INTERVIEW_PREP_PROMPT,
)
from resume_agent.core.exceptions import LLMError


def _parse_json(raw: str) -> dict | list:
    """Strip markdown fences and parse JSON.

    Handles:
    - Markdown code fences (```json ... ```)
    - Extra text / multiple JSON objects after the first valid one
      (causes json.JSONDecodeError 'Extra data')
    """
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # Fast path — clean JSON
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Slow path — LLM appended extra text; extract the first complete JSON
    # object {...} or array [...] using a regex that handles nesting via
    # a simple brace/bracket counter.
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        idx = raw.find(start_char)
        if idx == -1:
            continue
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(raw[idx:], start=idx):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_str:
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    candidate = raw[idx:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break  # try the other bracket type

    # Last resort — let json.loads raise with the original error
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
            "job_description": job_description[:1200],
            "resume_json": resume_json,
        }, f"resume tailor ({job_title} @ {company})")
        return _parse_json(content)
    except Exception as e:
        logger.error(f"[LLM] Resume tailoring failed: {e}")
        raise LLMError(f"Resume tailoring failed: {e}") from e


async def run_cover_letter_chain(
    name: str,
    job_title: str,
    company: str,
    job_description: str,
    resume_summary: str,
    skills: str,
    projects: str,
) -> str:
    try:
        chain = COVER_LETTER_PROMPT | get_llm()
        content = await _invoke_with_retry(chain, {
            "name": name,
            "job_title": job_title,
            "company": company,
            "job_description": job_description[:2000],
            "resume_summary": resume_summary,
            "skills": skills,
            "projects": projects,
        }, f"cover letter ({job_title} @ {company})")
        return content.strip()
    except Exception as e:
        logger.error(f"[LLM] Cover letter failed: {e}")
        raise LLMError(f"Cover letter generation failed: {e}") from e


async def run_email_draft_chain(
    name: str,
    job_title: str,
    company: str,
    skills: str,
) -> str:
    try:
        chain = EMAIL_DRAFT_PROMPT | get_llm()
        content = await _invoke_with_retry(chain, {
            "name": name,
            "job_title": job_title,
            "company": company,
            "skills": skills,
        }, f"email draft ({job_title} @ {company})")
        return content.strip()
    except Exception as e:
        logger.error(f"[LLM] Email draft failed: {e}")
        raise LLMError(f"Email draft generation failed: {e}") from e


async def run_interview_prep_chain(
    job_title: str,
    company: str,
    job_description: str,
    resume_summary: str,
    skills: str,
    projects: str,
) -> str:
    try:
        chain = INTERVIEW_PREP_PROMPT | get_llm()
        content = await _invoke_with_retry(chain, {
            "job_title": job_title,
            "company": company,
            "job_description": job_description[:2000],
            "resume_summary": resume_summary,
            "skills": skills,
            "projects": projects,
        }, f"interview prep ({job_title} @ {company})")
        return content.strip()
    except Exception as e:
        logger.error(f"[LLM] Interview prep failed: {e}")
        raise LLMError(f"Interview prep generation failed: {e}") from e