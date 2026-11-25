# 🎯 Career Guide AI

An AI-assisted career guidance web application for Indian students and career
changers. Users can either choose a career directly or complete one 12-question
discovery assessment. Both paths lead to a code-ranked shortlist, a personal
roadmap with saved progress, and an AI Career Mentor that uses the user's saved
context.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.3-000000?logo=flask&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3-F7931E?logo=scikit-learn&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2.0-150458?logo=pandas&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql&logoColor=white)
![Deployed on Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?logo=render&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-Live-brightgreen)

🔗 **Live Demo:** https://career-guide-ai-yr2f.onrender.com

> ⏳ Hosted on Render's free tier, so the first visit after a period of inactivity can take up to a minute to wake up.

---

## 📸 Screenshots

### Landing Page
![Landing Page](Screenshots/Landling_Page.png)

### Features
![Features](Screenshots/Features.png)

---

## ✨ Features

- 🧭 **Two Entry Paths** – "I Know What I Want" for direct browsing and "Help Me Discover My Career" for guided exploration
- 🔍 **Career Explorer** – search 300 careers across 20 industries, compare roles and choose without an assessment
- 📝 **Career Discovery** – one 12-question, roughly three-minute flow with no right or wrong answers
- 🏆 **Code-Ranked Recommendations** – deterministic ranking from answers, profile, education, skills and location, with top three shown first
- 🗺️ **Personal Roadmap** – qualifications, skills, resources, projects, internships, resume preparation and saved progress
- 🤖 **AI Career Mentor** – practical, structured answers using saved profile, discovery answers, recommendations and roadmap milestones
- 👤 **User Accounts & Dashboard** – register, log in, complete a one-time profile and resume a journey at any point
- 🛡️ **Admin Dashboard** – user statistics, user management and action logs

Ranking and matching are always done in Python. The language model only writes
explanations and roadmaps as validated JSON; if it is unavailable or returns
invalid data, the application uses a deterministic non-LLM fallback.

The old `/quiz`, `/psychometric-test`, `/iq-test` and result pages still redirect
to the legacy combined assessment for compatibility, but they are no longer in
the primary navigation or shown as a required step in the new journeys. See
[UPGRADE_NOTES.md](UPGRADE_NOTES.md) for the full change summary.

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask, Flask-SQLAlchemy, Flask-Migrate |
| Data / ML | Pandas, NumPy, scikit-learn (TF-IDF, cosine similarity) |
| Database | SQLite locally, PostgreSQL via `DATABASE_URL` |
| Frontend | HTML, CSS, JavaScript (Jinja2 templates) |
| Server | Gunicorn |
| Hosting | Render |

## 📁 Project Structure

```
career-guide-ai/
├── app/
│   ├── __init__.py          # App factory, config, extensions, security
│   ├── models.py            # SQLAlchemy models and compatibility facade
│   ├── extensions.py        # Shared SQLAlchemy and Migrate instances
│   ├── blueprints/          # auth, main, api and admin routes (validation only)
│   └── services/            # Assessment, scoring, ranking, roadmap, chat and data logic
├── data/
│   ├── career.csv           # Enriched 300-career dataset
│   ├── discovery_questions.py # 12-question discovery bank
│   ├── questions.py         # Legacy question banks
│   └── assessment_questions.py
├── migrations/              # Flask-Migrate revisions
├── scripts/
│   └── prepare_career_data.py
├── templates/               # Jinja2 screens (all extend base.html)
├── static/                  # CSS, JS, images
├── tests/                   # Pytest suite with isolated temp database
├── render.yaml
├── requirements.txt
└── wsgi.py
```

## 🚀 Run Locally

```bash
# 1. Clone and enter the project
git clone https://github.com/Gayathri-Reddy874/career-guide-ai.git
cd career-guide-ai

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file from the example and set SECRET_KEY
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

# 5. Prepare the dataset and apply migrations
python scripts/prepare_career_data.py
flask --app app db upgrade

# 6. Run the app
flask --app app run
```

Open http://127.0.0.1:5000 in your browser.

Run the tests with:

```bash
python -m pytest tests/ -q
```

## ⚙️ Environment Variables

See `.env.example` for a copyable template.

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret (required in production) | Required |
| `DATABASE_URL` | PostgreSQL connection URL; `postgres://` is normalised | SQLite when empty |
| `DATABASE_PATH` | SQLite file path when `DATABASE_URL` is empty | `instance/career_guide.db` |
| `LEGACY_DATABASE_PATH` | Optional old SQLite file copied into an empty Postgres DB on first startup | Empty |
| `SKIP_DB_CREATE` | Set to `1` for migration commands to skip app seeding | `0` |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Optional admin bootstrap; all three are required and no admin is created unless none exists | Empty |
| `FLASK_DEBUG` | Set to `1` for local debug only | `0` |
| `GROQ_API_KEY` | Groq API key for AI explanations, roadmaps and chat | Optional (fallback used) |
| `GROQ_MODEL` | Groq model identifier | `openai/gpt-oss-120b` |

No default admin account is created. Set all three `ADMIN_*` values if you need
one; otherwise create it through your own seed process.

## ☁️ Deploy on Render

`render.yaml` defines the web service, including a pre-deploy migration step.

1. Push this repo to your GitHub remote (for example, `Gayathri-Reddy874/career-guide-ai`).
2. In Render, create a PostgreSQL database and copy its **Internal Database URL**.
3. Click **New + → Web Service** and connect the repo, or deploy with the Blueprint in `render.yaml`.
4. Use these settings:
   - **Language:** Python 3
   - **Build Command:** `pip install --upgrade pip && pip install -r requirements.txt`
   - **Pre-Deploy Command:** `SKIP_DB_CREATE=1 flask --app app db upgrade`
   - **Start Command:** `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
   - **Health Check Path:** `/health`
5. Configure Environment Variables in the Render dashboard:
   - `SECRET_KEY` (auto-generated or a long random string)
   - `DATABASE_URL` (the Internal Database URL from step 2)
   - `GROQ_API_KEY` (optional; AI features fall back gracefully without it)
   - `GROQ_MODEL` (optional, defaults to `openai/gpt-oss-120b`)
   - `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` (optional bootstrap)
6. Deploy. The pre-deploy command applies migrations before Gunicorn starts.
7. To import the existing SQLite database, set `LEGACY_DATABASE_PATH` to a path
   Render can read and redeploy. Copying only happens when the target tables are empty.

## 🔮 Future Improvements

- Resume upload and skill-gap analysis
- More granular roadmap progress analytics
- Additional language support

## 👩‍💻 Author

**Mallareddygari Gayathri**
B.E. in AI & ML Engineering | Aspiring Data Analyst

- GitHub: [@Gayathri-Reddy874](https://github.com/Gayathri-Reddy874)
- LinkedIn: [your-linkedin-url](https://www.linkedin.com/in/your-linkedin-id) *(replace)*

## 📄 License

This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.

---

⭐ If you found this project useful, please give it a star!
