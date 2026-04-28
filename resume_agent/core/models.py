from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    INTERNSHALA = "internshala"
    NAUKRI = "naukri"
    WELLFOUND = "wellfound"


class JobType(str, Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    BOTH = "both"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


# ── Resume Models ──────────────────────────────────────────────────────────────

class ResumeSkills(BaseModel):
    languages: list[str] = []
    frameworks: list[str] = []
    ml_ai: list[str] = []
    cloud_devops: list[str] = []
    databases: list[str] = []
    tools: list[str] = []

    def all_skills(self) -> list[str]:
        return (
            self.languages + self.frameworks + self.ml_ai +
            self.cloud_devops + self.databases + self.tools
        )


class ResumeExperience(BaseModel):
    title: str
    org: str
    duration: str
    highlights: list[str] = []


class ResumeProject(BaseModel):
    name: str
    tech_stack: list[str] = []
    description: str
    highlights: list[str] = []


class ResumeEducation(BaseModel):
    degree: str
    institution: str
    duration: str
    gpa: Optional[str] = None


class ParsedResume(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    portfolio: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    summary: str
    target_roles: list[str] = []
    skills: ResumeSkills = Field(default_factory=ResumeSkills)
    experience: list[ResumeExperience] = []
    projects: list[ResumeProject] = []
    education: list[ResumeEducation] = []
    achievements: list[str] = []


class TailoredResume(BaseModel):
    """Resume content rewritten by LLM for a specific job."""
    base: ParsedResume
    job_title: str
    company: str
    tailored_summary: str
    highlighted_skills: list[str] = []
    reordered_projects: list[ResumeProject] = []
    reordered_experience: list[ResumeExperience] = []
    added_keywords: list[str] = []
    file_path: Optional[str] = None


# ── Job Models ─────────────────────────────────────────────────────────────────

class Job(BaseModel):
    id: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = None
    description: str
    url: str
    platform: Platform
    job_type: JobType = JobType.INTERNSHIP
    salary: Optional[str] = None
    posted_at: Optional[datetime] = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_skills: list[str] = []
    missing_skills: list[str] = []


# ── Application Models ─────────────────────────────────────────────────────────

class ApplicationResult(BaseModel):
    job: Job
    status: ApplicationStatus
    applied_at: Optional[datetime] = None
    error: Optional[str] = None
    notes: Optional[str] = None
    tailored_resume_path: Optional[str] = None