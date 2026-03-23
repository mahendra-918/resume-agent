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
}}"""),
    ("human", "Parse this resume:\n\n{resume_text}"),
])

# ── Search Query Generator ─────────────────────────────────────────────────────

QUERY_GENERATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a job search expert.
Given a parsed resume, generate 3 optimized search queries to find the best matching jobs.
Return ONLY a JSON array of 3 strings. No explanation.
Example: ["ML Engineer Intern Python LangChain", "AI Agent Developer Intern", "Software Engineer Intern FastAPI Docker"]"""),
    ("human", """Generate search queries for this profile:
Target roles: {target_roles}
Top skills: {top_skills}
Experience: {experience_summary}"""),
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