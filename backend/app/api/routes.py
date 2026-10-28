from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import logging

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import DiseaseKnowledge, Farm, ImageDiagnosis, ModelVersion, RiskPrediction, User, WeatherObservation
from app.schemas import (
    FarmCreate,
    FarmOut,
    FarmUpdate,
    KnowledgeCreate,
    KnowledgeOut,
    KnowledgeUpdate,
    LoginRequest,
    RiskRequest,
    UserCreate,
    UserOut,
    UserPreferences,
)
from app.services.image_classifier import ImageModelUnavailable, classify_image
from app.services.security import clear_session_cookie, hash_password, set_session_cookie, verify_password

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, db: Session = Depends(get_db)):
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), full_name=payload.full_name.strip(), preferred_language=payload.preferred_language)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
    db.refresh(user)
    set_session_cookie(response, user.id)
    return user


@router.post("/auth/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive.")
    set_session_cookie(response, user.id)
    return user


@router.post("/auth/logout", status_code=204)
def logout(response: Response):
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.patch("/auth/me", response_model=UserOut)
def update_preferences(payload: UserPreferences, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.preferred_language = payload.preferred_language
    db.commit()
    db.refresh(user)
    return user


@router.get("/farms", response_model=list[FarmOut])
def list_farms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Farm).where(Farm.user_id == user.id).order_by(Farm.created_at.desc())))


@router.post("/farms", response_model=FarmOut, status_code=201)
def create_farm(payload: FarmCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = Farm(user_id=user.id, **payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


def owned_farm(farm_id: str, user: User, db: Session) -> Farm:
    farm = db.scalar(select(Farm).where(Farm.id == farm_id, Farm.user_id == user.id))
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found.")
    return farm


@router.get("/farms/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return owned_farm(farm_id, user, db)


@router.patch("/farms/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: str, payload: FarmUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = owned_farm(farm_id, user, db)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(farm, key, value)
    if (farm.latitude is None) != (farm.longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together.")
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = owned_farm(farm_id, user, db)
    db.delete(farm)
    db.commit()


def cached_weather(farm_id: str, db: Session, limit: int = 24):
    return list(db.scalars(select(WeatherObservation).where(WeatherObservation.farm_id == farm_id).order_by(WeatherObservation.observed_at.desc()).limit(limit)))


def fetch_current_weather(farm: Farm, db: Session):
    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(status_code=422, detail="Add confirmed farm coordinates before requesting weather.")
    params = {
        "latitude": farm.latitude,
        "longitude": farm.longitude,
        "current": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,wind_speed_10m",
        "timezone": "UTC",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0)) as client:
            response = client.get(settings.open_meteo_base_url, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Weather provider request failed: %s", type(exc).__name__)
        return None

    if not isinstance(payload, dict):
        logger.warning("Weather provider response was not a JSON object.")
        return None
    current = payload.get("current")
    units = payload.get("current_units", {})
    if not isinstance(current, dict) or not current.get("time"):
        logger.warning("Weather provider response omitted current observation fields.")
        return None
    try:
        observed_at = datetime.fromisoformat(current["time"].replace("Z", "+00:00"))
    except (TypeError, ValueError):
        logger.warning("Weather provider response contained an invalid observation timestamp.")
        return None
    values = {
        "temperature_mean": current.get("temperature_2m"),
        "relative_humidity": current.get("relative_humidity_2m"),
        "dew_point": current.get("dew_point_2m"),
        "precipitation": current.get("precipitation"),
        "wind_speed": current.get("wind_speed_10m"),
    }
    source = "Open-Meteo"
    observation = db.scalar(select(WeatherObservation).where(
        WeatherObservation.farm_id == farm.id,
        WeatherObservation.source == source,
        WeatherObservation.observed_at == observed_at,
    ))
    if observation is None:
        observation = WeatherObservation(
            farm_id=farm.id,
            observed_at=observed_at,
            temperature_min=None,
            temperature_max=None,
            source=source,
            retrieved_at=datetime.now(timezone.utc),
            raw_metadata={"units": units},
            **values,
        )
        db.add(observation)
    else:
        observation.retrieved_at = datetime.now(timezone.utc)
        observation.raw_metadata = {"units": units}
        for key, value in values.items():
            setattr(observation, key, value)
    db.commit()
    db.refresh(observation)
    return observation


@router.get("/weather/current")
def current_weather(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = owned_farm(farm_id, user, db)
    latest = cached_weather(farm_id, db, limit=1)
    fresh = fetch_current_weather(farm, db) if farm.latitude is not None else None
    observation = fresh or (latest[0] if latest else None)
    return {
        "status": "available" if fresh else "stale" if observation else "unavailable",
        "provider": "Open-Meteo",
        "cached": fresh is None and observation is not None,
        "observation": observation,
        "timestamp": observation.observed_at if observation else None,
        "unavailable_fields": ["temperature_min", "temperature_max"],
        "message": None if fresh else "Provider data could not be refreshed; showing the last cached observation." if observation else "No weather observations are available.",
    }


@router.get("/weather/history")
def weather_history(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = Query(default=24, ge=1, le=168)):
    owned_farm(farm_id, user, db)
    observations = cached_weather(farm_id, db, limit)
    return {"status": "available" if observations else "unavailable", "provider": "Open-Meteo", "cached": True, "observations": observations, "unavailable_fields": ["temperature_min", "temperature_max"]}


@router.post("/weather/refresh")
def refresh_weather(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = owned_farm(farm_id, user, db)
    observation = fetch_current_weather(farm, db)
    if observation:
        return {"status": "available", "provider": "Open-Meteo", "cached": False, "observation": observation, "unavailable_fields": ["temperature_min", "temperature_max"]}
    cached = cached_weather(farm_id, db, limit=1)
    return {"status": "unavailable" if not cached else "stale", "provider": "Open-Meteo", "cached": bool(cached), "observation": cached[0] if cached else None, "unavailable_fields": ["temperature_min", "temperature_max"], "message": "Weather refresh failed; no current weather assessment should be inferred."}


@router.post("/risk/predict", status_code=503)
def predict_risk(payload: RiskRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_farm(payload.farm_id, user, db)
    if not Path(settings.risk_model_path).is_file():
        raise HTTPException(status_code=503, detail={"code": "risk_model_unavailable", "message": "No validated risk model is configured. No risk score was generated."})
    raise HTTPException(status_code=503, detail={"code": "risk_inference_not_implemented", "message": "Configured model artifacts require an inference adapter before predictions can be served."})


@router.get("/risk/history")
def risk_history(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return list(db.scalars(select(RiskPrediction).where(RiskPrediction.user_id == user.id).order_by(RiskPrediction.created_at.desc()).offset(offset).limit(limit)))


@router.get("/risk/{prediction_id}")
def get_risk(prediction_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prediction = db.scalar(select(RiskPrediction).where(RiskPrediction.id == prediction_id, RiskPrediction.user_id == user.id))
    if not prediction:
        raise HTTPException(status_code=404, detail="Risk assessment not found.")
    return prediction


@router.get("/risk/{prediction_id}/explanation")
def risk_explanation(prediction_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_risk(prediction_id, user, db)
    return {"status": "unavailable", "message": "No explanation is available because a validated model is not configured."}


@router.post("/diagnosis/predict")
async def diagnose(
    file: UploadFile = File(...),
    farm_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if farm_id:
        owned_farm(farm_id, user, db)
    started = perf_counter()
    raw = await file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds the configured 10 MB limit.")
    try:
        image = Image.open(__import__("io").BytesIO(raw))
        if image.width * image.height > 30_000_000:
            raise HTTPException(status_code=415, detail="Image dimensions exceed the supported limit.")
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=415, detail="Uploaded content is not a supported image.") from exc
    if not Path(settings.image_model_path).is_file():
        raise HTTPException(status_code=503, detail={"code": "image_model_unavailable", "message": "No validated image model is configured. No diagnosis was generated.", "validation_ms": round((perf_counter() - started) * 1000)})
    try:
        result = await run_in_threadpool(classify_image, raw)
    except ImageModelUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "image_model_unavailable", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return result


@router.get("/diagnosis/history")
def diagnosis_history(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return list(db.scalars(select(ImageDiagnosis).where(ImageDiagnosis.user_id == user.id).order_by(ImageDiagnosis.created_at.desc()).offset(offset).limit(limit)))


@router.get("/diagnosis/{diagnosis_id}")
def get_diagnosis(diagnosis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    diagnosis = db.scalar(select(ImageDiagnosis).where(ImageDiagnosis.id == diagnosis_id, ImageDiagnosis.user_id == user.id))
    if not diagnosis:
        raise HTTPException(status_code=404, detail="Diagnosis not found.")
    return diagnosis


@router.get("/diagnosis/{diagnosis_id}/heatmap")
def diagnosis_heatmap(diagnosis_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_diagnosis(diagnosis_id, user, db)
    raise HTTPException(status_code=404, detail="No heatmap was generated for this diagnosis.")


@router.get("/knowledge/diseases", response_model=list[KnowledgeOut])
def list_knowledge(language: str = Query(default="en", pattern="^(en|ta)$"), db: Session = Depends(get_db)):
    return list(db.scalars(select(DiseaseKnowledge).where(DiseaseKnowledge.is_published.is_(True), DiseaseKnowledge.language_code == language).order_by(DiseaseKnowledge.display_name)))


@router.get("/knowledge/diseases/{disease_class}", response_model=KnowledgeOut)
def get_knowledge(disease_class: str, language: str = Query(default="en", pattern="^(en|ta)$"), db: Session = Depends(get_db)):
    entry = db.scalar(select(DiseaseKnowledge).where(DiseaseKnowledge.disease_class == disease_class, DiseaseKnowledge.language_code == language, DiseaseKnowledge.is_published.is_(True)))
    if not entry:
        raise HTTPException(status_code=404, detail="No reviewed knowledge entry is available in this language.")
    return entry


@router.get("/admin/models")
def admin_models(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(ModelVersion).order_by(ModelVersion.model_type, ModelVersion.created_at.desc())))


@router.post("/admin/knowledge", response_model=KnowledgeOut, status_code=201)
def create_knowledge(payload: KnowledgeCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    entry = DiseaseKnowledge(**payload.model_dump())
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A knowledge entry already exists for this disease and language.") from exc
    db.refresh(entry)
    return entry


@router.patch("/admin/knowledge/{knowledge_id}", response_model=KnowledgeOut)
def update_knowledge(knowledge_id: str, payload: KnowledgeUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    entry = db.get(DiseaseKnowledge, knowledge_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/admin/data-quality")
def admin_data_quality(user: User = Depends(require_admin)):
    return {"status": "not_configured", "issues": [], "message": "Dataset quality checks have not been connected."}


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    def artifact_status(path: str) -> str:
        return "disabled" if Path(path).is_file() else "unavailable"

    checks = {
        "database": "ok",
        "image_model": (
            "experimental_enabled"
            if settings.enable_experimental_image_model and Path(settings.image_model_path).is_file()
            else artifact_status(settings.image_model_path)
        ),
        "risk_model": artifact_status(settings.risk_model_path),
    }
    try:
        db.execute(select(User.id).limit(1))
    except Exception as exc:
        logger.error("Readiness database check failed: %s", type(exc).__name__)
        checks["database"] = "unavailable"
        return {"status": "not_ready", "checks": checks}
    return {"status": "ready" if checks["database"] == "ok" else "not_ready", "checks": checks}
