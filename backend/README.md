# Backend

FastAPI service with SQLAlchemy 2, Alembic, PostgreSQL support, and a SQLite
fallback for local tests. Python 3.11+ is recommended; the backend currently
uses standard APIs compatible with Python 3.13 as well.

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up -d db
python -m pip install -r backend\requirements.txt
alembic -c backend\alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --reload
```

OpenAPI: `http://localhost:8000/docs`. Run tests:

```powershell
python -m pytest
```

## Optional experimental image classifier

The API returns an unavailable response for image inference by default. To
enable the experimental classifier, install the pinned ML dependencies in the
same Python environment, set both values in the repository `.env`, then restart
the API:

```powershell
python -m pip install -r ml\requirements.txt
```

```env
IMAGE_MODEL_PATH=artifacts/image/efficientnet_v2_s.pt
ENABLE_EXPERIMENTAL_IMAGE_MODEL=true
```

The local checkpoint must be trained first; the API does not download model
weights. Results are uncalibrated and not independently field-validated, are
not confirmed diagnoses, and are not saved to diagnosis history. See
[ML workflow](../ml/README.md) for dataset provenance and limitations.

`SECRET_KEY`, database credentials, allowed origins, and cookie security must be
set appropriately before deployment. The in-memory rate limiter is intended
for a single-process development instance; replace it with a shared limiter for
multi-worker production.
