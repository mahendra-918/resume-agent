import os
import re
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright

from resume_agent.core.models import TailoredResume

OUTPUT_DIR = Path("output/tailored")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _clean_filename(name: str) -> str:
    """Clean a string to be safe for filenames."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


def _generate_html(tailored: TailoredResume) -> str:
    """Generate a clean, professional HTML resume from the tailored data."""
    base = tailored.base
    
    # Header
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                color: #333;
                line-height: 1.5;
                margin: 0;
                padding: 40px;
                font-size: 11pt;
            }}
            h1 {{ font-size: 24pt; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px; }}
            .contact-info {{ font-size: 10pt; color: #555; margin-bottom: 20px; }}
            .contact-info span {{ margin-right: 15px; }}
            h2 {{
                font-size: 14pt;
                color: #222;
                border-bottom: 1px solid #ccc;
                padding-bottom: 5px;
                margin-top: 20px;
                margin-bottom: 15px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .summary {{ font-size: 11pt; margin-bottom: 20px; }}
            .item-header {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 5px; }}
            .item-title {{ font-weight: bold; font-size: 12pt; }}
            .item-subtitle {{ font-style: italic; color: #555; }}
            .item-date {{ font-size: 10pt; color: #666; }}
            ul {{ margin-top: 5px; padding-left: 20px; margin-bottom: 15px; }}
            li {{ margin-bottom: 5px; text-align: justify; }}
            .skills-section {{ margin-bottom: 15px; }}
            .skill-category {{ font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>{base.name}</h1>
        <div class="contact-info">
            <span>{base.email}</span>
            {f'<span>{base.phone}</span>' if base.phone else ''}
            {f'<span>{base.location}</span>' if base.location else ''}
            {f'<span><a href="{base.linkedin}">{base.linkedin}</a></span>' if base.linkedin else ''}
            {f'<span><a href="{base.github}">{base.github}</a></span>' if base.github else ''}
        </div>
        
        <h2>Summary</h2>
        <div class="summary">{tailored.tailored_summary}</div>
    """

    # Skills
    if tailored.highlighted_skills or base.skills.all_skills():
        html += "<h2>Skills</h2><div class='skills-section'>"
        if tailored.highlighted_skills:
            html += f"<div><span class='skill-category'>Key Skills:</span> {', '.join(tailored.highlighted_skills)}</div>"
        
        skills = base.skills
        if skills.languages: html += f"<div><span class='skill-category'>Languages:</span> {', '.join(skills.languages)}</div>"
        if skills.frameworks: html += f"<div><span class='skill-category'>Frameworks:</span> {', '.join(skills.frameworks)}</div>"
        if skills.ml_ai: html += f"<div><span class='skill-category'>AI/ML:</span> {', '.join(skills.ml_ai)}</div>"
        if skills.cloud_devops: html += f"<div><span class='skill-category'>Cloud & DevOps:</span> {', '.join(skills.cloud_devops)}</div>"
        if skills.databases: html += f"<div><span class='skill-category'>Databases:</span> {', '.join(skills.databases)}</div>"
        if skills.tools: html += f"<div><span class='skill-category'>Tools:</span> {', '.join(skills.tools)}</div>"
        html += "</div>"

    # Experience
    if tailored.reordered_experience:
        html += "<h2>Experience</h2>"
        for exp in tailored.reordered_experience:
            html += f"""
            <div class="item-header">
                <div><span class="item-title">{exp.title}</span>, <span class="item-subtitle">{exp.org}</span></div>
                <div class="item-date">{exp.duration}</div>
            </div>
            <ul>
            """
            for hl in exp.highlights:
                html += f"<li>{hl}</li>"
            html += "</ul>"

    # Projects
    if tailored.reordered_projects:
        html += "<h2>Projects</h2>"
        for proj in tailored.reordered_projects:
            tech_stack = f" | <i>{', '.join(proj.tech_stack)}</i>" if proj.tech_stack else ""
            html += f"""
            <div class="item-header">
                <div><span class="item-title">{proj.name}</span>{tech_stack}</div>
            </div>
            <div class="summary">{proj.description}</div>
            <ul>
            """
            for hl in proj.highlights:
                html += f"<li>{hl}</li>"
            html += "</ul>"

    # Education
    if base.education:
        html += "<h2>Education</h2>"
        for edu in base.education:
            gpa = f" | GPA: {edu.gpa}" if edu.gpa else ""
            html += f"""
            <div class="item-header">
                <div><span class="item-title">{edu.degree}</span>, <span class="item-subtitle">{edu.institution}</span>{gpa}</div>
                <div class="item-date">{edu.duration}</div>
            </div>
            """

    html += """
    </body>
    </html>
    """
    return html


async def generate_tailored_pdf(tailored: TailoredResume) -> str:
    """
    Generate a PDF from the tailored resume data and return the absolute file path.
    """
    company_clean = _clean_filename(tailored.company)
    role_clean = _clean_filename(tailored.job_title)
    filename = f"Resume_{company_clean}_{role_clean}.pdf"
    output_path = (OUTPUT_DIR / filename).resolve()

    html_content = _generate_html(tailored)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="networkidle")
            
            # Print to PDF
            await page.pdf(
                path=str(output_path),
                format="A4",
                print_background=True,
                margin={"top": "20mm", "bottom": "20mm", "left": "20mm", "right": "20mm"}
            )
            await browser.close()
            
        logger.info(f"[PDF Generator] Successfully generated {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"[PDF Generator] Failed to generate PDF: {e}")
        raise
