# Explainable AI-Based Multi-Modal Decision Support System for Sugarcane Disease Risk Assessment and Diagnosis

A farmer-focused academic prototype for independently assessing environmental
disease risk and sugarcane leaf images. An experimental image classifier can
be trained on the sourced public image set; it is not independently field
validated and returns only explicitly labeled, uncalibrated experimental
outputs when manually enabled. No environmental risk model is included.
The image and environmental modules are not fused into a jointly trained model.

## Project status checklist

- [x] FastAPI backend, OpenAPI documentation, SQLAlchemy entities, and Alembic migration.
- [x] Registration/login/logout with Argon2 password hashing and HttpOnly session cookie.
- [x] User-scoped farm CRUD and coordinate validation.
- [x] Open-Meteo current observation integration with cached/stale status.
- [x] Upload content/size/dimension validation and experimental image inference behind explicit opt-in.
- [x] Explicit risk-model unavailable response; no fallback thresholds or scores.
- [x] Frontend localization in English and 15 Indian languages; generated translations need local review.
- [x] Gemini weather guidance based on the latest farm observations and reviewed disease guidance.
- [x] Admin-protected knowledge CRUD API and disease-language records.
- [x] Focused backend API tests and image dataset audit utility.
- [x] Experimental image-classifier training pipeline with exact-duplicate removal, split-manifest output, and computed holdout metrics.
- [x] Experimental image-classifier API adapter behind an explicit opt-in setting.
- [ ] Trained and independently validated image and environmental models, plus SHAP/ALE/Grad-CAM++ adapters.
- [ ] Historical weather ingestion, persisted image storage/retention, deployment-grade monitoring and distributed throttling.
- [ ] Full administration/settings/history experiences, accessibility/browser testing, PWA, offline inference, and frontend tests.

## Quick start

Prerequisites: Python 3.11+, Node.js 20+, and npm. Local development uses
SQLite and does not require Docker.

```powershell
Copy-Item .env.example .env
python -m pip install -r backend\requirements.txt
alembic -c backend\alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

The API is documented at `http://localhost:8000/docs`. Backend tests:
`python -m pytest`. Frontend build:
`Set-Location frontend; npm run build`.

## Configuration and security

Copy `.env.example` to `.env`. Never use the example secret or database
credentials outside local development. Set `COOKIE_SECURE=true` behind HTTPS,
use a long random `SECRET_KEY`, and set `FRONTEND_ORIGINS` to exact trusted
origins. Weather requests use Open-Meteo and only use coordinates entered for a
farm. No device location is collected. Rate limiting is process-local and must
be replaced with a shared store for multi-worker hosting.

To enable weather-specific farmer tips, set `GEMINI_API_KEY` in the backend
`.env` file and restart the API. `GEMINI_MODEL` defaults to
`gemini-3.1-flash-lite`. The key stays on the backend; the frontend never receives
it. The Analyze weather action sends the exact farm GPS coordinates, the
previous seven days of Open-Meteo weather summaries, current readings, selected
disease, reviewed disease context, and saved crop/soil details to Gemini. Do not
use this feature unless you consent to sharing the precise farm location with
Google. It does not send account details, farm names, or farmer notes. Gemini
returns a preliminary environmental risk screening, not a validated disease
model, diagnosis, or forecast; confirm concerns with a local agriculture
expert. Open-Meteo values are gridded provider estimates, not measurements from
sensors in the farmer's field.

Model artifact paths are explicit. The service does not download weights at
startup. The image model remains disabled by default; enabling it exposes only
an experimental, uncalibrated classifier result. No environmental risk model
is available.
See [ML workflow](ml/README.md), [architecture](docs/architecture.md),
[database notes](docs/database.md), and [API reference](docs/api.md).

## Important limitations

No password-reset mailer, account deletion workflow, admin interface/admin
bootstrap, saved image object storage, prediction history UI, ALE/SHAP/
Grad-CAM++ computation, PWA/offline model, containerized app deployment, or
complete frontend/integration test coverage is currently implemented. A
weather provider response is observational data, not a disease risk estimate.
This project is not agricultural advice; consult local agricultural experts.

The dataset provenance, training steps, actual artifact, and experimental API
opt-in are documented in [ML workflow](ml/README.md). Training requires an
explicit `--pretrained` flag; the API does not enable experimental inference by
default.
