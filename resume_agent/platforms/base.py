from abc import ABC, abstractmethod
from resume_agent.core.models import Job, ApplicationResult


class BasePlatform(ABC):
    """Every job platform must implement this interface."""

    name: str

    @abstractmethod
    async def search(self, query: str, location: str, job_type: str) -> list[Job]:
        """Search for jobs matching the query. Returns a list of Job objects."""
        ...

    @abstractmethod
    async def apply(self, job: Job, resume_pdf_path: str) -> ApplicationResult:
        """Apply to a job using the tailored resume PDF."""
        ...

    def __repr__(self) -> str:
        return f"<Platform: {self.name}>"