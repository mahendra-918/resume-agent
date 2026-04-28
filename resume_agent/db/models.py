from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    job_title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    job_url = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    job_type = Column(String, nullable=False)
    location = Column(String, nullable=True)
    relevance_score = Column(Float, default=0.0)
    matched_skills = Column(Text, nullable=True)
    missing_skills = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    applied_at = Column(DateTime, nullable=True)
    resume_pdf_path = Column(Text, nullable=True)
    resume_docx_path = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
