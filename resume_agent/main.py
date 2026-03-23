from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from resume_agent.core.config import settings
from resume_agent.utils.logger import setup_logger

app = typer.Typer(name="resume-agent", help="Autonomous job application agent")


# ── run ────────────────────────────────────────────────────────────────────────

@app.command()
def run(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume file (.md/.pdf/.docx)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Search and tailor but do not submit"),
    max_applications: int = typer.Option(
        settings.MAX_APPLICATIONS,
        "--max",
        "-n",
        help="Maximum number of applications to submit",
    ),
) -> None:
    """Search jobs, tailor resume, and auto-apply."""
    setup_logger()

    if not resume.exists():
        typer.echo(f"Error: resume file not found: {resume}", err=True)
        raise typer.Exit(code=1)

    logger.info(f"Starting full run — resume: {resume}, dry_run: {dry_run}")

    from resume_agent.graph.pipeline import run_pipeline

    final_state = asyncio.run(
        run_pipeline(
            resume_path=str(resume),
            dry_run=dry_run,
            max_applications=max_applications,
        )
    )

    errors: list[str] = final_state.get("errors") or []
    if errors:
        typer.echo("\nErrors encountered during run:", err=True)
        for e in errors:
            typer.echo(f"  • {e}", err=True)


# ── dry-run ────────────────────────────────────────────────────────────────────

@app.command(name="dry-run")
def dry_run_cmd(
    resume: Path = typer.Option(..., "--resume", "-r", help="Path to resume file"),
    max_applications: int = typer.Option(
        settings.MAX_APPLICATIONS,
        "--max",
        "-n",
        help="Maximum jobs to process",
    ),
) -> None:
    """Dry run: search, rank, tailor, generate — but do not submit applications."""
    setup_logger()

    if not resume.exists():
        typer.echo(f"Error: resume file not found: {resume}", err=True)
        raise typer.Exit(code=1)

    logger.info(f"Starting dry run — resume: {resume}")

    from resume_agent.graph.pipeline import run_pipeline

    asyncio.run(
        run_pipeline(
            resume_path=str(resume),
            dry_run=True,
            max_applications=max_applications,
        )
    )


# ── status ─────────────────────────────────────────────────────────────────────

@app.command()
def status() -> None:
    """Show a summary of all job applications submitted so far."""
    setup_logger()

    from resume_agent.db.repository import get_all_applications

    applications = asyncio.run(get_all_applications())

    if not applications:
        typer.echo("No applications yet. Run `resume-agent run` to start.")
        return

    col_widths = {"num": 4, "company": 22, "role": 30, "platform": 12, "status": 9, "score": 6, "at": 19}
    header = (
        f"{'#':<{col_widths['num']}} "
        f"{'Company':<{col_widths['company']}} "
        f"{'Role':<{col_widths['role']}} "
        f"{'Platform':<{col_widths['platform']}} "
        f"{'Status':<{col_widths['status']}} "
        f"{'Score':<{col_widths['score']}} "
        f"{'Applied At':<{col_widths['at']}}"
    )
    separator = "-" * len(header)

    typer.echo(separator)
    typer.echo(header)
    typer.echo(separator)

    for i, app_result in enumerate(applications, start=1):
        job = app_result.job
        applied_at = (
            app_result.applied_at.strftime("%Y-%m-%d %H:%M:%S")
            if app_result.applied_at
            else "—"
        )
        score = f"{job.relevance_score:.2f}" if job.relevance_score else "—"
        row = (
            f"{i:<{col_widths['num']}} "
            f"{job.company[:col_widths['company']]:<{col_widths['company']}} "
            f"{job.title[:col_widths['role']]:<{col_widths['role']}} "
            f"{job.platform.value[:col_widths['platform']]:<{col_widths['platform']}} "
            f"{app_result.status.value[:col_widths['status']]:<{col_widths['status']}} "
            f"{score:<{col_widths['score']}} "
            f"{applied_at:<{col_widths['at']}}"
        )
        typer.echo(row)

    typer.echo(separator)
    typer.echo(f"Total: {len(applications)}")


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
