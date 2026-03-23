# resume-agent

An autonomous AI agent that searches for jobs, tailors your resume per job using Groq LLM, generates a PDF + DOCX, and auto-applies via Playwright browser automation — all from a single command.

---

## How it works

```
Your Resume (.md / .pdf / .docx)
        │
        ▼
  Parse Resume  ──► Generate Search Queries
        │
        ▼
  Search Jobs (LinkedIn · Internshala · Naukri · Wellfound) ← parallel
        │
        ▼
  Rank & Filter Jobs  (Groq LLM relevance scoring)
        │
        ▼
  For each job:
    Tailor Resume  →  Generate PDF + DOCX  →  Auto-Apply  →  Save to DB
        │
        ▼
  Summary logged to terminal + SQLite
```

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| LangGraph 0.2+ | Agent pipeline (StateGraph) |
| Groq (llama-3.3-70b-versatile) | LLM inference — parse, rank, tailor |
| python-jobspy | Multi-platform job search |
| Playwright (async) | Browser automation for form filling |
| WeasyPrint + Jinja2 | HTML → PDF resume generation |
| python-docx | DOCX resume generation |
| FastAPI + uvicorn | Optional REST API mode |
| Typer | CLI |
| SQLAlchemy + aiosqlite | Application tracking (SQLite) |
| Pydantic v2 | Data models and settings |
| Loguru | Structured logging |
| uv | Package manager |

---

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Install Playwright browsers

```bash
playwright install chromium
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
# Required
GROQ_API_KEY=your_groq_api_key_here   # https://console.groq.com

# Platform credentials (only needed for platforms you enable)
LINKEDIN_EMAIL=you@email.com
LINKEDIN_PASSWORD=yourpassword
NAUKRI_EMAIL=you@email.com
NAUKRI_PASSWORD=yourpassword
INTERNSHALA_EMAIL=you@email.com
INTERNSHALA_PASSWORD=yourpassword
```

---

## Usage

### Dry run (no applications submitted)

Search, rank, tailor resumes, and generate PDF/DOCX — but do **not** submit anything:

```bash
uv run python -m resume_agent.main dry-run --resume ./my_resume.md
```

### Full run

```bash
uv run python -m resume_agent.main run --resume ./my_resume.md
```

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--resume` | required | Path to your resume (.md, .pdf, or .docx) |
| `--max` | 20 | Maximum number of applications to submit |
| `--dry-run` | false | Skip actual submissions |

### Check application history

```bash
uv run python -m resume_agent.main status
```

Output:

```
-----------------------------------------------------------------------
#    Company                Role                           Platform     Status    Score  Applied At
-----------------------------------------------------------------------
1    athenahealth           Member of Technical Staff      linkedin     applied   0.87   2026-03-24 01:40:00
2    Acme Corp              Backend Intern                 internshala  skipped   0.74   —
-----------------------------------------------------------------------
Total: 2
```

### REST API

```bash
uv run uvicorn resume_agent.api:app --reload
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/run` | Start the agent in the background |
| GET | `/status` | All applications |
| GET | `/status/{platform}` | Filter by platform |
| GET | `/health` | Health check |

**POST /run body:**

```json
{
  "resume_path": "./my_resume.md",
  "dry_run": false,
  "max_applications": 20
}
```

---

## Project Structure

```
resume-agent/
├── resume_agent/
│   ├── core/        ← config, state, models, exceptions
│   ├── graph/       ← LangGraph StateGraph + checkpointer
│   ├── nodes/       ← one file per pipeline stage
│   ├── platforms/   ← LinkedIn, Internshala, Naukri, Wellfound
│   ├── llm/         ← Groq client, chains, prompts
│   ├── document/    ← PDF and DOCX generation
│   ├── browser/     ← Playwright setup and form filling
│   ├── db/          ← SQLAlchemy models and repository
│   └── utils/       ← logger and helpers
├── tests/
│   ├── unit/
│   └── integration/
└── output/          ← generated resumes (git-ignored)
```

---

## Configuration

All settings are controlled via `.env` / environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | required | Groq API key |
| `JOB_LOCATION` | `Bangalore, India` | Target job location |
| `JOB_TYPE` | `internship` | `internship`, `full_time`, or `both` |
| `MAX_APPLICATIONS` | `20` | Max applications per run |
| `MIN_RELEVANCE_SCORE` | `0.6` | Minimum LLM relevance score (0–1) |
| `RESULTS_PER_PLATFORM` | `20` | Jobs fetched per platform |
| `USE_LINKEDIN` | `true` | Enable LinkedIn search |
| `USE_INTERNSHALA` | `true` | Enable Internshala search |
| `USE_NAUKRI` | `true` | Enable Naukri search |
| `USE_WELLFOUND` | `true` | Enable Wellfound search |
| `OUTPUT_DIR` | `./output/resumes` | Where generated resumes are saved |
| `DB_PATH` | `./output/applications_log.db` | SQLite database path |
| `HEADLESS` | `true` | Run browser headlessly |

---

## Running Tests

```bash
# All unit tests
uv run pytest tests/unit/ -v

# All tests including integration
uv run pytest tests/ -v

# Integration tests only (requires real credentials)
uv run pytest tests/integration/ -v -m integration
```

---

## Resume Format

Your resume can be `.md`, `.pdf`, or `.docx`. The LLM parses it into structured fields automatically. A Markdown resume works best — see the structure the agent expects:

```markdown
# Your Name
email@example.com | +91-XXXXXXXXXX | City, India
GitHub: github.com/you | LinkedIn: linkedin.com/in/you

## Summary
...

## Skills
**Languages:** Python, Go, ...
**Frameworks:** FastAPI, React, ...

## Experience
### Job Title — Company (Month Year – Month Year)
- Highlight 1
- Highlight 2

## Projects
### Project Name | Python, FastAPI, ...
- Description

## Education
### Degree — Institution (Year – Year)
GPA: X.X
```
