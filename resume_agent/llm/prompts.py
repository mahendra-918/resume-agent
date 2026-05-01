from langchain_core.prompts import ChatPromptTemplate

# ── Resume Parser ──────────────────────────────────────────────────────────────

RESUME_PARSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert resume parser.
Extract structured information from the resume text and return ONLY valid JSON.
No explanation. No markdown. Just raw JSON matching this exact structure:
{{
  "name": "", "email": "", "phone": "", "location": "",
  "portfolio": "", "linkedin": "", "github": "",
  "summary": "",
  "target_roles": [],
  "skills": {{
    "languages": [], "frameworks": [], "ml_ai": [],
    "cloud_devops": [], "databases": [], "tools": []
  }},
  "experience": [{{"title":"","org":"","duration":"","highlights":[]}}],
  "projects": [{{"name":"","tech_stack":[],"description":"","highlights":[]}}],
  "education": [{{"degree":"","institution":"","duration":"","gpa":""}}],
  "achievements": []
}}

IMPORTANT for target_roles:
- Always infer 2-3 likely job titles the candidate would apply for, based on their skills and experience
- Use short, standard job titles (e.g. "Software Engineer", "ML Engineer", "Backend Developer")
- Never leave target_roles as an empty list — always provide at least one role
- achievements must be a list of plain strings, not objects"""),
    ("human", "Parse this resume:\n\n{resume_text}"),
])

# ── Search Query Generator ─────────────────────────────────────────────────────

QUERY_GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a job search expert.
Given a candidate's profile, generate 3 short, effective LinkedIn job search queries.

STRICT RULES:
- Each query must be 2 to 4 words ONLY — no more
- Use simple, common job titles that real companies post
- Do NOT stuff keywords — short titles rank much better on LinkedIn
- Always include "intern" or "internship" somewhere in the query
- Return ONLY a valid JSON array of exactly 3 strings. Nothing else.

Good examples:
["Software Engineer Intern", "Backend Developer Intern", "ML Engineer Intern"]
["Python Developer Intern", "Data Engineer Intern", "AI Engineer Intern"]

Bad examples (too long — never do this):
["Python Software Engineer Intern FastAPI Docker LangChain", ...]"""),
    ("human", """Generate 3 short job search queries for this candidate:
Target roles: {target_roles}
Top skills: {top_skills}
Experience: {experience_summary}

Remember: 2-4 words per query ONLY. Return JSON array."""),
])

# ── Job Ranker ─────────────────────────────────────────────────────────────────

JOB_RANK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a job-candidate matching expert.
Score how well the candidate matches this job from 0.0 to 1.0.
Return ONLY valid JSON:
{{
  "relevance_score": 0.0,
  "matched_skills": [],
  "missing_skills": [],
  "reason": ""
}}"""),
    ("human", """Candidate skills: {candidate_skills}
Candidate experience: {candidate_experience}

Job title: {job_title}
Job description: {job_description}"""),
])

# ── Resume Tailor ──────────────────────────────────────────────────────────────

RESUME_TAILOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert resume writer. 
Tailor the candidate's resume specifically for the given job.
Rules:
- NEVER fabricate skills or experience that don't exist
- Only reorder, reword, and emphasize what already exists
- Add relevant keywords from the job description naturally
- Make the summary directly address the role
- Prioritize the most relevant projects first

Return ONLY valid JSON:
{{
  "tailored_summary": "",
  "highlighted_skills": [],
  "reordered_projects": [{{"name":"","tech_stack":[],"description":"","highlights":[]}}],
  "reordered_experience": [{{"title":"","org":"","duration":"","highlights":[]}}],
  "added_keywords": []
}}"""),
    ("human", """Job Title: {job_title}
Company: {company}
Job Description: {job_description}

Candidate Resume:
{resume_json}"""),
])

# ── Cover Letter Generator ─────────────────────────────────────────────────────

COVER_LETTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert career coach who writes compelling, personalized cover letters.
Write a professional cover letter for the candidate applying to this job.
Rules:
- 3 paragraphs: opening (why this role/company), middle (2-3 specific skills/projects that match), closing (call to action)
- Be specific — reference actual skills and projects from the resume
- Sound natural and human, not templated
- Keep it under 300 words
- Do NOT use placeholder text like [Your Name] — use the actual name
- Return ONLY the cover letter text, no subject line, no JSON"""),
    ("human", """Candidate Name: {name}
Job Title: {job_title}
Company: {company}
Job Description: {job_description}

Candidate Resume Summary:
{resume_summary}

Key Skills: {skills}
Relevant Projects: {projects}"""),
])

# ── Email Draft Generator ──────────────────────────────────────────────────────

EMAIL_DRAFT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert at writing cold outreach emails to hiring teams.
Write a concise cold email the candidate can send to apply for this job.
Rules:
- Include a subject line on the first line, prefixed with "Subject: "
- Then a blank line
- Then the email body (4-6 sentences max)
- Reference 1-2 specific skills that match the job
- End with a clear ask (e.g. "I'd love to discuss this opportunity")
- Sign off with the candidate's name
- Return ONLY the subject line + email body, no JSON"""),
    ("human", """Candidate Name: {name}
Job Title: {job_title}
Company: {company}
Key Matching Skills: {skills}"""),
])

# ── Interview Prep Generator ───────────────────────────────────────────────────

INTERVIEW_PREP_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert interview coach. Be concise.
Generate a SHORT interview prep guide. Plain text, no JSON.

LIKELY QUESTIONS:
1. [question] → [1-sentence answer]
2. [question] → [1-sentence answer]
3. [question] → [1-sentence answer]

KEY TALKING POINTS:
- [project/achievement]
- [project/achievement]

SKILLS TO EMPHASIZE:
- [skill matching JD]
- [skill matching JD]"""),
    ("human", """Job Title: {job_title}
Company: {company}
Job Description: {job_description}

Candidate Resume Summary: {resume_summary}
Key Skills: {skills}
Projects: {projects}"""),
])