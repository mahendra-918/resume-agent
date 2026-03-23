from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from resume_agent.core.models import JobType


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.0

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    LINKEDIN_EMAIL: str = ""
    LINKEDIN_PASSWORD: str = ""

    # ── Internshala ───────────────────────────────────────────────────────────
    INTERNSHALA_EMAIL: str = ""
    INTERNSHALA_PASSWORD: str = ""

    # ── Naukri ────────────────────────────────────────────────────────────────
    NAUKRI_EMAIL: str = ""
    NAUKRI_PASSWORD: str = ""

    # ── Job Search ────────────────────────────────────────────────────────────
    JOB_LOCATION: str = "Bangalore, India"
    JOB_TYPE: JobType = JobType.INTERNSHIP
    MAX_APPLICATIONS: int = Field(default=20, ge=1, le=100)
    MIN_RELEVANCE_SCORE: float = Field(default=0.6, ge=0.0, le=1.0)
    RESULTS_PER_PLATFORM: int = Field(default=20, ge=1, le=50)

    # ── Platforms toggle ──────────────────────────────────────────────────────
    USE_LINKEDIN: bool = True
    USE_INTERNSHALA: bool = True
    USE_NAUKRI: bool = True
    USE_WELLFOUND: bool = True

    # ── Output ────────────────────────────────────────────────────────────────
    OUTPUT_DIR: str = "./output/resumes"
    DB_PATH: str = "./output/applications_log.db"

    # ── Browser ───────────────────────────────────────────────────────────────
    HEADLESS: bool = True
    BROWSER_SLOW_MO: int = Field(default=500, ge=0)


settings = Settings()