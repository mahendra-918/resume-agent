import asyncio
from resume_agent.graph.pipeline import run_pipeline

async def main():
    # Find the resume path — adjust if needed
    import glob, os
    resumes = glob.glob("**/*.pdf", recursive=True) + glob.glob("**/*.txt", recursive=True)
    resumes = [r for r in resumes if "resume" in r.lower() and "output" not in r]
    if not resumes:
        print("ERROR: No resume file found. Put a resume PDF in the project folder.")
        return

    resume_path = resumes[0]
    print(f"Using resume: {resume_path}")

    final_state = await run_pipeline(
        resume_path=resume_path,
        dry_run=True,   # no browser, just LLM
        max_applications=2,  # limit to 2 jobs for speed
    )

    packages = final_state.get("packages") or []
    print(f"\n✓ Packages generated: {len(packages)}")
    for p in packages:
        print(f"  → {p.job.title} @ {p.job.company}")
        print(f"     Dir: {p.output_dir}")
        print(f"     Cover letter: {'✓' if p.cover_letter else '✗'}")
        print(f"     Email draft:  {'✓' if p.email_draft else '✗'}")
        print(f"     Interview prep: {'✓' if p.interview_prep else '✗'}")

    if packages:
        import os
        first_dir = packages[0].output_dir
        print(f"\nFiles in {first_dir}:")
        for f in os.listdir(first_dir):
            print(f"  {f}")

asyncio.run(main())
