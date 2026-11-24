# Career Guide AI — DISCOVER → EXPLORE → CHOOSE → GROW upgrade

Branch: `feature/new-flow` (local only; not pushed, PR'd or merged).

## Summary

The existing Flask/Jinja/vanilla-JS application was refactored in place. Users can
now enter through either a direct career-choice path or one short discovery
assessment. Both paths lead to code-ranked recommendations, a persistent roadmap
and a context-aware AI Career Mentor. The existing UI identity, base template,
navigation style, colours, fonts and CSS classes were preserved; no React, new UI
library or visual redesign was introduced.

Upgrade commits after `e8a0f4d`:

- `b0a2e1b` — two-path dashboard, direct choice, profile country/region
- `4fc94f5` — single 12-question discovery assessment
- `1e5e5f1` — location, eligibility and non-technical career guidance
- `999a58c` — richer roadmap overview, milestones and career switching
- `281e5be` — context-aware, JSON-validated AI Career Mentor
- final documentation/test commit on the same branch

## New journeys

### Journey A — I Know What I Want

1. Dashboard or nav → **Discover Careers** (`/discover`).
2. Search by career name or browse by industry; 300 careers across 20 industries.
3. Open a career for requirements, education, skills, tools/salary where the
   source data is reliable, and compare up to three careers.
4. `POST /career/<career_id>/choose` saves the career without requiring an
   assessment and redirects to the roadmap.

### Journey B — Help Me Discover My Career

1. Dashboard, Discover Careers or footer → **Career Discovery** (`/discovery`).
2. One simple 12-question flow (about three minutes) with progress, plain
   language and no right/wrong answers.
3. Answers are stored in the existing assessment tables under a namespaced
   `discovery` key. They map to the existing `riasec`/`aptitude`/`prefs` shapes,
   so the code-side recommender remains shared.
4. `/recommendations` shows the top three first, then additional matches, with
   explanations, strengths, gaps, education and possible pathways. No arbitrary
   match percentages are displayed.

### Grow and mentor

- Roadmap shows career overview, qualifications, entry route, skills, resources,
  weekly/monthly milestones, portfolio projects, internships, resume/interview
  preparation and progress percentage. Steps can be marked complete and resume
  from the dashboard or roadmap.
- **Change career** on the roadmap returns to Discover; choosing another career
  creates a new roadmap while preserving old roadmap rows.
- AI Career Mentor uses profile, discovery answers, top suggestions, chosen
  career, skills, completed milestones, next milestone and location. It asks a
  clarifying question when needed and never invents courses, qualifications,
  licences, jobs, salaries, rankings or statistics.

## Navigation removals

- Logged-in primary nav now contains exactly: Dashboard, Discover Careers, My
  Recommendations, My Roadmap, AI Career Mentor, Profile & Settings.
- Dashboard no longer shows Psychometric Assessment, Career Quiz or IQ Test.
- Footer no longer links to the old quiz/psychometric pages.
- Chatbot sidebar quick tools now point to Career Discovery, My Recommendations
  and My Roadmap.
- Legacy URLs (`/quiz`, `/psychometric-test`, `/results`,
  `/psychometric-results`, `/iq-test`, `/iq-test-results`, `/assessment`) are
  retained for compatibility and still use the old three-part assessment where
  applicable; they are no longer presented as the primary journey.

## Backend and database changes

- New route: `/discovery` (GET/POST), backed by `app/services/discovery_service.py`
  and `data/discovery_questions.py`.
- New route: `POST /career/<career_id>/choose`, backed by
  `choose_career_direct()`; no assessment required.
- Migrations: one new revision,
  `migrations/versions/9c1d4b7a2e6f_profile_country_region.py`, adds nullable
  `profiles.country` and `profiles.region`. No enum changes; stage remains
  `class10|class12|college`.
- No new business tables were introduced. Discovery reuses `assessments`,
  `assessment_answers`, `assessment_scores`, `recommendations`, `chosen_careers`,
  `roadmaps`, `roadmap_items` and `chat_messages`.
- `data/career.csv` keeps all 300 rows and the original 15 columns. New
  deterministic metadata columns were added: `country`, `region`,
  `eligible_streams`, `non_tech_eligible`, `licensing_note`, `pathway`.
- Ranking remains application-side and transparent. Stream eligibility, location
  context and non-technical coverage were added; the LLM only writes validated
  JSON explanations/roadmaps with deterministic fallbacks.
- Mentor replies are JSON-validated for logged-in users; invalid or unavailable
  LLM output falls back to a structured, non-LLM answer. Anonymous chatbot
  compatibility is unchanged.

## Tests and results

Command used:

```powershell
python -m pytest tests/ -q
```

Result:

```text
111 passed, 24 warnings, 68 subtests passed
```

Warnings are from Flask-Limiter's in-memory storage notice and existing
`datetime.utcnow()` / SQLAlchemy `Query.get()` deprecations. No live Groq calls
are made: `tests/conftest.py` clears `GROQ_API_KEY`, and generation tests patch
`app.services.chatbot_service.call_groq_completion`.

Coverage includes:

- Journey A: browse/search, direct choice without assessment, unknown career
  rejection, dashboard state.
- Journey B: 12-question page, incomplete answers, completion feeding
  recommendations, top-three/additional-match rendering, no percentage text.
- Existing users and legacy redirects, users without assessments, profile
  country/region, stage/stream/location eligibility, career changers, four
  education backgrounds and ≥15 industries with non-tech paths.
- Roadmap persistence, progress toggling, resume next milestone and career
  change.
- LLM success, invalid JSON, plain-text rejection for logged-in mentor and
  non-LLM fallback.
- Mobile layout hooks (viewport, media queries, single-column grid) and
  Render/migration/Postgres-driver configuration.

## Limitations

- The career catalogue is India-centric. Country/region fields make that
  explicit and prompt local verification; this is not a full multi-country
  qualifications database.
- The `profiles.stage` enum still only has `class10`, `class12` and `college`.
  A career changer is stored as `college` plus free-text stream; the discovery
  answer "Working / changing career" maps to `college`.
- Internal numeric scores remain for deterministic ordering and legacy API
  compatibility, but they are not presented as match percentages.
- No specific courses, institutes, employers or salary figures are generated;
  users must verify current local requirements.
- Mobile responsiveness was verified through existing markup/CSS assertions,
  not device-level visual testing.

## Files changed

- Backend/services: `app/blueprints/main.py`, `app/models.py`,
  `app/services/career_dataset.py`, `app/services/chat_service.py`,
  `app/services/chatbot_service.py`, `app/services/discovery_service.py`,
  `app/services/llm_response.py`, `app/services/profile_service.py`,
  `app/services/recommendation_service.py`, `app/services/roadmap_service.py`,
  `app/services/user_service.py`.
- Data/migrations: `data/career.csv`, `data/discovery_questions.py`,
  `migrations/versions/9c1d4b7a2e6f_profile_country_region.py`.
- Templates: `templates/base.html`, `templates/career.html`,
  `templates/chatbot.html`, `templates/dashboard.html`, `templates/discover.html`,
  `templates/discovery.html`, `templates/profile.html`,
  `templates/recommendations.html`, `templates/roadmap.html`.
- Tests: `tests/conftest.py`, `tests/test_new_journeys.py`,
  `tests/test_phase4.py`, `tests/test_phase7.py`.
- Docs/config: `README.md`, `UPGRADE_NOTES.md`.

## Deployment compatibility

- Existing Flask app factory, SQLAlchemy/Postgres setup, authentication, Render
  blueprint and integrations are unchanged in shape.
- `render.yaml` still runs `SKIP_DB_CREATE=1 flask --app app db upgrade` before
  `gunicorn wsgi:app`; the new profile migration is picked up automatically.
- `requirements.txt` retains both `psycopg2-binary` and `psycopg[binary]` for
  Render.
- Secrets remain environment-only (`SECRET_KEY`, `DATABASE_URL`,
  `GROQ_API_KEY`, `GROQ_MODEL`, `ADMIN_*`); `.env.example` needs no new variable.
- No "Stitch" reference appears anywhere in the repository.
