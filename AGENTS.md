Project: Career Guide AI, an existing Flask app (live on Render) for Indian students. We are REFACTORING it, not rewriting it.

Rules:
- Preserve existing behavior. Reuse existing code, templates, CSS and logic. Move and clean up before replacing anything.
- Small steps. After each step the app must run and all tests must pass. Commit-sized changes only.
- Target structure: app/{__init__.py, models.py, blueprints/, services/}, data/, templates/, static/, tests/
- Routes only validate and call services. Logic lives in app/services/.
- Secrets only from env vars; keep .env.example updated. No hardcoded credentials anywhere.
- Ranking/matching is done by code. The LLM only writes explanations/roadmaps as validated JSON, with a non-LLM fallback.
- Do only what the current prompt asks. No extra features.

FRONTEND LOCK:
- Do NOT modify existing templates, CSS, JS or layout except screens explicitly named in the current prompt.
- Keep base.html, navbar, footer, colors, fonts and CSS classes as they are.
- New screens reuse base.html and existing CSS classes. No new UI libraries, no redesign.
- If a backend change needs a template edit (url_for names, CSRF token, escaping), make the smallest possible edit and list the files first.
