FROM python:3.11-slim

# ── System deps + Node.js ─────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    curl wget gnupg git \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

# ── Python deps ───────────────────────────────────────────────────────────────
COPY pyproject.toml ./
RUN uv sync --no-dev 2>/dev/null || uv pip install -r pyproject.toml

# ── Playwright Chromium ───────────────────────────────────────────────────────
RUN uv run playwright install chromium --with-deps || python -m playwright install chromium

# ── Frontend build ────────────────────────────────────────────────────────────
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci

COPY frontend/ frontend/
RUN cd frontend && npm run build

# ── App source ────────────────────────────────────────────────────────────────
COPY . .

RUN mkdir -p output/resumes output/packages output/tailored output/sessions

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "resume_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
