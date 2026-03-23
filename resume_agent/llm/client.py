from functools import lru_cache
from langchain_groq import ChatGroq
from resume_agent.core.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    """Returns a singleton Groq LLM client."""
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )