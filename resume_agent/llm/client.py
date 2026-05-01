from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from resume_agent.core.config import settings


def get_llm() -> BaseChatModel:
    """Return an LLM client based on LLM_PROVIDER setting.

    Supports:
      - "groq"   → ChatGroq   (requires GROQ_API_KEY)
      - "gemini" → ChatGoogleGenerativeAI (requires GEMINI_API_KEY)
      - "ollama" → ChatOllama (local, no API key required)
    """
    provider = (settings.LLM_PROVIDER or "groq").lower().strip()

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        model = settings.LLM_MODEL if settings.LLM_MODEL not in ("llama-3.3-70b-versatile", "gemini-2.0-flash") else "llama3.2:3b"
        return ChatOllama(model=model, temperature=settings.LLM_TEMPERATURE)

    if provider == "gemini":
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "LLM_PROVIDER is set to 'gemini' but GEMINI_API_KEY is missing. "
                "Add it in Settings → AI Provider."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Use gemini-2.0-flash by default (free tier, latest stable)
        model = settings.LLM_MODEL if "gemini" in settings.LLM_MODEL else "gemini-2.0-flash"
        return ChatGoogleGenerativeAI(
            google_api_key=settings.GEMINI_API_KEY,
            model=model,
            temperature=settings.LLM_TEMPERATURE,
        )

    # Default: Groq
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "LLM_PROVIDER is set to 'groq' but GROQ_API_KEY is missing. "
            "Add it in Settings → AI Provider."
        )
    from langchain_groq import ChatGroq
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )
