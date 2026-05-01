#!/bin/bash
# ── ResumeAgent — Production Start Script ─────────────────────────────────────

set -e

echo "🚀 Starting ResumeAgent..."

# Build frontend if dist doesn't exist or source is newer
if [ ! -d "frontend/dist" ] || [ "frontend/src" -nt "frontend/dist" ]; then
  echo "📦 Building frontend..."
  cd frontend && npm install && npm run build && cd ..
  echo "✅ Frontend built"
fi

# Create output dirs
mkdir -p output/resumes output/packages output/tailored output/sessions

echo ""
echo "✅ ResumeAgent is ready!"
echo "👉 Open http://localhost:8000 in your browser"
echo ""

# Start FastAPI (serves both API and frontend)
uv run uvicorn resume_agent.api:app --host 0.0.0.0 --port 8000
