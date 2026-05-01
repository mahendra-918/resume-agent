from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from resume_agent.core.exceptions import ResumeParseError
from resume_agent.core.models import ParsedResume, ResumeSkills
from resume_agent.core.state import AgentState
from resume_agent.llm.chains import run_resume_parse_chain


async def _read_md(path: Path) -> str:
    return await asyncio.to_thread(path.read_text, encoding="utf-8")


async def _read_pdf(path: Path) -> str:
    import pdfplumber

    def _extract() -> str:
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    return await asyncio.to_thread(_extract)


async def _read_docx(path: Path) -> str:
    from docx import Document

    def _extract() -> str:
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)

    return await asyncio.to_thread(_extract)


async def parse_resume_node(state: AgentState) -> dict:
    path = Path(state["resume_path"])
    suffix = path.suffix.lower()

    try:
        if suffix == ".md":
            raw_text = await _read_md(path)
        elif suffix == ".pdf":
            raw_text = await _read_pdf(path)
        elif suffix == ".docx":
            raw_text = await _read_docx(path)
        else:
            raise ResumeParseError(f"Unsupported file type: {suffix}")

        logger.info(f"[ResumeParser] Read {len(raw_text)} chars from {path.name}")

        data = await run_resume_parse_chain(raw_text)

        skills_data = data.get("skills", {})
        skills = ResumeSkills(**skills_data) if isinstance(skills_data, dict) else ResumeSkills()

        # Coerce achievements to plain strings — LLMs sometimes return dicts
        # like {"title": "...", "description": "..."} instead of strings.
        raw_achievements = data.get("achievements", [])
        achievements: list[str] = []
        for item in raw_achievements:
            if isinstance(item, str):
                achievements.append(item)
            elif isinstance(item, dict):
                # Prefer "title" key; fall back to joined values
                title = item.get("title") or item.get("name") or ""
                desc = item.get("description") or item.get("detail") or ""
                achievements.append(f"{title}: {desc}".strip(": ") if desc else title or str(item))
            else:
                achievements.append(str(item))

        parsed = ParsedResume(
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone"),
            location=data.get("location"),
            portfolio=data.get("portfolio"),
            linkedin=data.get("linkedin"),
            github=data.get("github"),
            summary=data.get("summary", ""),
            target_roles=data.get("target_roles", []),
            skills=skills,
            experience=data.get("experience", []),
            projects=data.get("projects", []),
            education=data.get("education", []),
            achievements=achievements,
        )

        logger.info(f"[ResumeParser] Parsed resume for: {parsed.name}")
        return {"resume_raw": raw_text, "parsed_resume": parsed}

    except Exception as e:
        logger.error(f"[ResumeParser] Failed: {e}")
        errors = list(state.get("errors") or [])
        errors.append(f"ResumeParser: {e}")
        return {
            "resume_raw": "",
            "parsed_resume": ParsedResume(name="", email="", summary=""),
            "errors": errors,
        }
