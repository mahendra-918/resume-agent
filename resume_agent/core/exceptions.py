class ResumeAgentError(Exception):
    """Base exception for all resume agent errors."""


class ResumeParseError(ResumeAgentError):
    """Failed to parse the resume file."""


class JobSearchError(ResumeAgentError):
    """Failed to search for jobs on a platform."""


class ResumeGenerationError(ResumeAgentError):
    """Failed to generate PDF or DOCX."""


class ApplicationError(ResumeAgentError):
    """Failed to submit a job application."""


class PlatformLoginError(ApplicationError):
    """Failed to log in to a job platform."""


class LLMError(ResumeAgentError):
    """LLM call failed or returned invalid response."""