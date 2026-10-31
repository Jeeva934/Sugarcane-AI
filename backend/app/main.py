from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.core.limits import rate_limit

app = FastAPI(
    title="Sugarcane Disease Decision Support API",
    version="0.1.0",
    description="Explainable environmental risk and image diagnosis interfaces. Predictions are disabled until validated model artifacts are configured.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)
app.middleware("http")(rate_limit)
app.include_router(router, prefix="/api/v1")

docs_dir = Path(__file__).resolve().parents[2] / "docs"
if docs_dir.exists():
    app.mount("/reports", StaticFiles(directory=str(docs_dir)), name="reports")
