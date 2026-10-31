import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import math
from time import perf_counter
import logging

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import AuditLog, DiseaseKnowledge, DiseaseObservation, Explanation, Farm, ImageDiagnosis, ModelVersion, RiskPrediction, User, WeatherObservation
from app.schemas import (
    DiseaseObservationCreate,
    DiseaseObservationReview,
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
    WeatherGuidanceOut,
    WeatherGuidanceRequest,
)
from app.services.image_classifier import ImageModelUnavailable, classify_image
from app.services.gemini_weather_guidance import WeatherGuidanceError, generate_weather_guidance, generate_risk_age_guidance
from app.services.synthetic_demo_predictor import (
    SyntheticDemoUnavailable,
    run_synthetic_fusion_demo,
)
from app.services.verified_risk_predictor import (
    RiskModelUnavailable,
    has_any_model,
    has_model,
    model_artifact_path,
    predict_disease_presence,
)
from app.services.security import clear_session_cookie, hash_password, set_session_cookie, verify_password

router = APIRouter()
logger = logging.getLogger(__name__)


def record_audit(db: Session, actor: User | None, action: str, resource_type: str, resource_id: str | None = None, metadata: dict | None = None) -> None:
    db.add(AuditLog(actor_user_id=actor.id if actor else None, action=action, resource_type=resource_type, resource_id=resource_id, metadata_json=metadata))


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, db: Session = Depends(get_db)):
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), full_name=payload.full_name.strip(), preferred_language=payload.preferred_language)
    db.add(user)
    record_audit(db, user, "auth.registered", "user", user.id)
    try:
        db.flush()
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


@router.delete("/auth/me", status_code=204)
def delete_account(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record_audit(db, user, "auth.account_deleted", "user", user.id)
    db.delete(user)
    db.commit()
    clear_session_cookie(response)
    response.status_code = 204
    return response


@router.get("/farms", response_model=list[FarmOut])
def list_farms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Farm).where(Farm.user_id == user.id).order_by(Farm.created_at.desc())))


@router.post("/farms", response_model=FarmOut, status_code=201)
def create_farm(payload: FarmCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = Farm(user_id=user.id, **payload.model_dump())
    db.add(farm)
    record_audit(db, user, "farm.created", "farm", farm.id)
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
    record_audit(db, user, "farm.updated", "farm", farm.id)
    db.commit()
    db.refresh(farm)
    return farm


@router.delete("/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = owned_farm(farm_id, user, db)
    record_audit(db, user, "farm.deleted", "farm", farm.id)
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


def fetch_recent_weather_context(farm: Farm, end_at: datetime) -> dict:
    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(status_code=422, detail="Add confirmed farm coordinates before requesting weather guidance.")

    params = {
        "latitude": farm.latitude,
        "longitude": farm.longitude,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "UTC",
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
            response = client.get(settings.open_meteo_base_url, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Recent weather history request failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "weather_history_unavailable",
                "message": "Recent farm weather history is unavailable, so a disease-risk screening cannot be generated.",
            },
        ) from None

    hourly = payload.get("hourly") if isinstance(payload, dict) else None
    if not isinstance(hourly, dict):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "weather_history_unavailable",
                "message": "Recent farm weather history is unavailable, so a disease-risk screening cannot be generated.",
            },
        )

    times = hourly.get("time")
    temperatures = hourly.get("temperature_2m")
    humidities = hourly.get("relative_humidity_2m")
    precipitation = hourly.get("precipitation")
    if not all(isinstance(values, list) for values in (times, temperatures, humidities, precipitation)):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "weather_history_unavailable",
                "message": "Recent farm weather history is incomplete, so a disease-risk screening cannot be generated.",
            },
        )

    end_time = end_at if end_at.tzinfo else end_at.replace(tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=7)
    days: dict[str, dict[str, list[float]]] = {}
    for index, value in enumerate(times):
        if not isinstance(value, str) or index >= len(temperatures) or index >= len(humidities) or index >= len(precipitation):
            continue
        try:
            observed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        if observed_at < start_time or observed_at > end_time:
            continue

        day = days.setdefault(observed_at.date().isoformat(), {
            "temperature": [],
            "humidity": [],
            "precipitation": [],
            "humid_hours": [],
        })
        for field, raw_value in (
            ("temperature", temperatures[index]),
            ("humidity", humidities[index]),
            ("precipitation", precipitation[index]),
        ):
            if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool) and math.isfinite(raw_value):
                day[field].append(float(raw_value))
        humidity = humidities[index]
        if isinstance(humidity, (int, float)) and not isinstance(humidity, bool) and math.isfinite(humidity) and humidity >= 80:
            day["humid_hours"].append(1.0)

    daily_summaries = []
    for date, readings in sorted(days.items()):
        rainfall = readings["precipitation"]
        daily_summaries.append({
            "date": date,
            "hours_with_temperature": len(readings["temperature"]),
            "mean_temperature_c": round(sum(readings["temperature"]) / len(readings["temperature"]), 1) if readings["temperature"] else None,
            "mean_relative_humidity_pct": round(sum(readings["humidity"]) / len(readings["humidity"]), 1) if readings["humidity"] else None,
            "hours_relative_humidity_at_least_80_pct": len(readings["humid_hours"]),
            "total_precipitation_mm": round(sum(rainfall), 1) if rainfall else None,
        })

    return {
        "provider": "Open-Meteo",
        "period_start_utc": start_time.isoformat(),
        "period_end_utc": end_time.isoformat(),
        "available_days": len(daily_summaries),
        "days": daily_summaries,
    }


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


@router.post("/weather/guidance", response_model=WeatherGuidanceOut)
def analyze_weather_guidance(
    payload: WeatherGuidanceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.gemini_api_key.strip():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "gemini_not_configured",
                "message": "AI weather guidance is not configured. Set GEMINI_API_KEY on the backend.",
            },
        )

    farm = owned_farm(payload.farm_id, user, db)
    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(status_code=422, detail="Add confirmed farm coordinates before requesting weather guidance.")

    fresh_observation = fetch_current_weather(farm, db)
    observation = fresh_observation or (cached_weather(farm.id, db, limit=1) or [None])[0]
    if observation is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "weather_unavailable", "message": "No current or cached weather observation is available."},
        )

    language_code = payload.language_code or user.preferred_language
    knowledge_language = "ta" if language_code == "ta" else "en"
    knowledge_entry = db.scalar(select(DiseaseKnowledge).where(
        DiseaseKnowledge.disease_class == payload.disease_class,
        DiseaseKnowledge.language_code == knowledge_language,
        DiseaseKnowledge.is_published.is_(True),
    ))
    knowledge = ({
        "display_name": knowledge_entry.display_name,
        "symptoms": knowledge_entry.symptoms,
        "preventive_guidance": knowledge_entry.preventive_guidance,
        "monitoring_guidance": knowledge_entry.monitoring_guidance,
        "source_reference": knowledge_entry.source_reference,
    } if knowledge_entry else {})
    weather_data = {
        "temperature_c": observation.temperature_mean,
        "relative_humidity_pct": observation.relative_humidity,
        "dew_point_c": observation.dew_point,
        "rainfall_mm": observation.precipitation,
        "wind_speed_kmh": observation.wind_speed,
    }
    if all(value is None for value in weather_data.values()):
        raise HTTPException(
            status_code=503,
            detail={"code": "weather_measurements_unavailable", "message": "Saved weather data has no usable measurements."},
        )
    recent_weather = fetch_recent_weather_context(farm, observation.observed_at)

    try:
        guidance = generate_weather_guidance(
            api_key=settings.gemini_api_key.strip(),
            model=settings.gemini_model,
            language_code=language_code,
            disease_class=payload.disease_class,
            observed_at=observation.observed_at,
            freshness="current" if fresh_observation else "cached",
            weather=weather_data,
            location={"latitude": farm.latitude, "longitude": farm.longitude},
            recent_weather=recent_weather,
            crop_variety=farm.crop_variety,
            growth_stage=farm.growth_stage,
            soil_ph=farm.soil_ph,
            knowledge=knowledge,
            grass_age=payload.grass_age,
        )
    except WeatherGuidanceError as exc:
        if exc.code in {"provider_timeout", "provider_unavailable", "provider_rate_limited"}:
            logger.warning(
                "Gemini weather guidance failed with code %s (provider HTTP status: %s, message: %s).",
                exc.code,
                exc.provider_status_code or "unavailable",
                exc.provider_message or "no provider message",
            )
            status_code = 429 if exc.code == "provider_rate_limited" else 503
            raise HTTPException(
                status_code=status_code,
                detail={"code": exc.code, "message": "AI weather guidance is temporarily unavailable. Try again later."},
            ) from exc
        logger.warning("Gemini weather guidance returned invalid output (%s).", exc.code)
        raise HTTPException(
            status_code=502,
            detail={"code": "invalid_ai_response", "message": "AI weather guidance could not be validated. Try again."},
        ) from exc

    return {
        "status": "generated",
        "model": settings.gemini_model,
        "weather_observed_at": observation.observed_at,
        "weather_freshness": "current" if fresh_observation else "cached",
        "weather_history_days": recent_weather["available_days"],
        "weather_measurements": weather_data,
        "disease_class": payload.disease_class,
        **guidance,
    }


@router.post("/disease-observations", status_code=status.HTTP_201_CREATED)
def create_disease_observation(
    payload: DiseaseObservationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    farm = owned_farm(payload.farm_id, user, db)
    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(status_code=422, detail="Add the farm GPS location before recording a disease observation.")

    observation = fetch_current_weather(farm, db)
    if observation is None:
        observation = (cached_weather(farm.id, db, limit=1) or [None])[0]
    weather_snapshot = None
    if observation:
        retrieved_at = observation.retrieved_at
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - retrieved_at).total_seconds()
        weather_snapshot = {
            "temperature_c": observation.temperature_mean,
            "relative_humidity_pct": observation.relative_humidity,
            "rainfall_mm": observation.precipitation,
            "wind_speed_kmh": observation.wind_speed,
            "dew_point_c": observation.dew_point,
            "observed_at": observation.observed_at.isoformat(),
            "source": observation.source,
            "freshness": "current" if 0 <= age_seconds < 3600 else "cached",
        }

    report = DiseaseObservation(
        farm_id=farm.id,
        reported_by_user_id=user.id,
        disease_class=payload.disease_class,
        observation_date=observation.observed_at.date() if observation else datetime.now(timezone.utc).date(),
        outcome="pending_verification",
        reported_outcome=payload.reported_outcome,
        verification_status="pending",
        verification_method="farmer_report",
        environment_snapshot={
            "latitude": farm.latitude if payload.research_consent else None,
            "longitude": farm.longitude if payload.research_consent else None,
            "soil_ph": farm.soil_ph,
            "weather": weather_snapshot,
        },
        research_consent=payload.research_consent,
        notes=payload.notes,
    )
    db.add(report)
    db.flush()
    record_audit(
        db,
        user,
        "disease_observation.reported",
        "disease_observation",
        report.id,
        {"research_consent": payload.research_consent, "weather_available": weather_snapshot is not None},
    )
    db.commit()
    return {
        "id": report.id,
        "disease_class": report.disease_class,
        "reported_outcome": report.reported_outcome,
        "verification_status": report.verification_status,
        "observation_date": report.observation_date,
        "weather_captured": weather_snapshot is not None,
        "research_consent": report.research_consent,
        "message": "Saved for expert review. This farmer report is not a verified training label or a disease prediction.",
    }


@router.get("/disease-observations")
def list_disease_observations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
):
    reports = db.scalars(
        select(DiseaseObservation)
        .join(Farm, DiseaseObservation.farm_id == Farm.id)
        .where(Farm.user_id == user.id)
        .order_by(DiseaseObservation.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": report.id,
            "farm_id": report.farm_id,
            "disease_class": report.disease_class,
            "reported_outcome": report.reported_outcome,
            "outcome": report.outcome if report.verification_status == "verified" else None,
            "verification_status": report.verification_status,
            "observation_date": report.observation_date,
            "research_consent": report.research_consent,
            "created_at": report.created_at,
        }
        for report in reports
    ]


@router.post("/risk/predict")
async def predict_risk(payload: RiskRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    farm = owned_farm(payload.farm_id, user, db)
    if not settings.enable_experimental_risk_model:
        raise HTTPException(
            status_code=503,
            detail={"code": "risk_model_unavailable", "message": "Environmental model inference is disabled. No score was generated."}
        )
    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(status_code=422, detail="Add confirmed farm coordinates before requesting environmental risk.")
    artifact_path = model_artifact_path(str(settings.resolved_risk_model_path), payload.disease_class)
    if not artifact_path.is_file():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "risk_model_unavailable",
                "message": f"No trained environmental model is available for {payload.disease_class}. "
                "Collect and expert-verify consented observations, then train the per-disease model.",
            },
        )

    observation = fetch_current_weather(farm, db)
    is_fresh = observation is not None
    if observation is None:
        observation = (cached_weather(farm.id, db, limit=1) or [None])[0]
    if observation is None:
        raise HTTPException(status_code=503, detail="Current weather is unavailable and no cached observation exists.")

    feature_values = {
        "soil_ph": farm.soil_ph,
        "temperature_c": observation.temperature_mean,
        "relative_humidity_pct": observation.relative_humidity,
        "rainfall_mm": observation.precipitation,
        "wind_speed_kmh": observation.wind_speed,
        "dew_point_c": observation.dew_point,
    }
    missing_weather = [name for name, value in feature_values.items() if name != "soil_ph" and value is None]
    if missing_weather:
        raise HTTPException(
            status_code=503,
            detail=f"Weather provider did not return required model features: {', '.join(missing_weather)}.",
        )
    try:
        result = await run_in_threadpool(
            predict_disease_presence,
            payload.disease_class,
            feature_values,
            str(settings.resolved_risk_model_path),
        )
    except RiskModelUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "risk_model_unavailable", "message": str(exc)}) from exc
    except Exception as exc:
        logger.exception("Environmental risk inference failed")
        raise HTTPException(status_code=500, detail="Risk calculation encountered an internal error.") from exc

    now = datetime.now(timezone.utc)
    record = RiskPrediction(
        user_id=user.id,
        farm_id=farm.id,
        disease_class=payload.disease_class,
        risk_score=result["disease_presence_score"],
        risk_category="uncalibrated",
        prediction_timestamp=now,
        weather_data_timestamp=observation.observed_at,
        data_freshness_status="current" if is_fresh else "cached",
        model_version=result["model_version"],
        input_period_start=observation.observed_at,
        input_period_end=observation.observed_at,
        forecast_horizon_days=0,
        status="experimental",
    )
    db.add(record)
    db.flush()

    db.add(Explanation(
        prediction_type="risk_assessment",
        prediction_id=record.id,
        explanation_type="shap_tree",
        structured_result={"drivers": result["primary_drivers"]},
        model_version=result["model_version"],
    ))

    record_audit(db, user, "risk.experimental_generated", "risk_prediction", record.id, {"saved_to_history": True})
    db.commit()
    db.refresh(record)

    if payload.grass_age:
        result["grass_age"] = payload.grass_age
        try:
            age_text = await run_in_threadpool(
                generate_risk_age_guidance,
                api_key=settings.gemini_api_key.strip(),
                model=settings.gemini_model,
                language_code=user.preferred_language or "en",
                disease_class=payload.disease_class,
                grass_age=payload.grass_age,
                risk_score=result["disease_presence_score"],
                primary_drivers=result.get("primary_drivers", []),
            )
            result["age_ai_guidance"] = age_text
        except Exception:
            result["age_ai_guidance"] = None

    result["id"] = record.id
    result["saved_to_history"] = True
    return result


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
    expl = db.scalar(select(Explanation).where(
        Explanation.prediction_id == prediction_id,
        Explanation.explanation_type == "shap_tree"
    ))
    if not expl or not expl.structured_result:
        return {"status": "unavailable", "message": "No SHAP explanation was recorded for this assessment."}
    return {
        "status": "available",
        "explanation_type": "shap_tree",
        "drivers": expl.structured_result.get("drivers", []),
        "model_version": expl.model_version
    }


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
    if not settings.enable_experimental_image_model or not settings.resolved_image_model_path.is_file():
        raise HTTPException(status_code=503, detail={"code": "image_model_unavailable", "message": "The experimental image model is disabled or no validated artifact is configured. No diagnosis was generated.", "validation_ms": round((perf_counter() - started) * 1000)})
    try:
        result = await run_in_threadpool(classify_image, raw)
    except ImageModelUnavailable as exc:
        raise HTTPException(status_code=503, detail={"code": "image_model_unavailable", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    record = ImageDiagnosis(
        user_id=user.id,
        farm_id=farm_id,
        image_storage_key=None,
        predicted_class=result["predicted_class"],
        confidence=result["uncalibrated_score"],
        alternative_predictions=result["alternative_predictions"],
        classifier_model_version=result["model_version"],
        processing_time_ms=result["processing_time_ms"],
        status="experimental",
        uncertainty_reason="Uncalibrated output; independent field validation and calibration are incomplete.",
    )
    db.add(record)
    db.flush()
    if result.get("heatmap_base64"):
        db.add(Explanation(
            prediction_type="image_diagnosis",
            prediction_id=record.id,
            explanation_type="grad_cam_plus_plus",
            structured_result={"heatmap_base64": result["heatmap_base64"]},
            model_version=result["model_version"],
        ))
    record_audit(db, user, "diagnosis.experimental_generated", "image_diagnosis", record.id, {"saved_to_history": True, "image_stored": False})
    db.commit()
    db.refresh(record)
    result["saved_to_history"] = True
    return result


@router.post("/demo/fusion/predict")
async def synthetic_fusion_demo(
    file: UploadFile = File(...),
    farm_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if settings.app_env.lower() == "production":
        raise HTTPException(status_code=404, detail="Not found.")

    farm = owned_farm(farm_id, user, db)
    if farm.latitude is None or farm.longitude is None:
        raise HTTPException(status_code=422, detail="Add confirmed farm GPS coordinates before running the demo.")
    if not settings.enable_experimental_image_model or not settings.resolved_image_model_path.is_file():
        raise HTTPException(
            status_code=503,
            detail={
                "code": "image_model_unavailable",
                "message": "Configure and enable the EfficientNetV2 image artifact before running the demo.",
            },
        )

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

    fresh_observation = fetch_current_weather(farm, db)
    observation = fresh_observation
    if observation is None:
        observation = (cached_weather(farm.id, db, limit=1) or [None])[0]
    if observation is None:
        raise HTTPException(status_code=503, detail="Current weather is unavailable and no cached observation exists.")

    feature_values = {
        "soil_ph": farm.soil_ph,
        "temperature_c": observation.temperature_mean,
        "relative_humidity_pct": observation.relative_humidity,
        "rainfall_mm": observation.precipitation,
        "wind_speed_kmh": observation.wind_speed,
        "dew_point_c": observation.dew_point,
    }
    if any(value is None for name, value in feature_values.items() if name != "soil_ph"):
        raise HTTPException(status_code=503, detail="Required current weather measurements are unavailable.")

    try:
        image_result = await run_in_threadpool(classify_image, raw)
        fusion_result = await run_in_threadpool(
            run_synthetic_fusion_demo,
            image_result["class_scores"],
            feature_values,
        )
    except (ImageModelUnavailable, SyntheticDemoUnavailable) as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "demo_unavailable", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Synthetic fusion demo failed")
        raise HTTPException(status_code=500, detail="Synthetic demo encountered an internal error.") from exc

    return {
        **fusion_result,
        "image": {
            "predicted_class": image_result["predicted_class"],
            "uncalibrated_score": image_result["uncalibrated_score"],
            "class_scores": image_result["class_scores"],
            "heatmap_base64": image_result["heatmap_base64"],
            "model_version": image_result["model_version"],
        },
        "detector": {
            "status": "not_used",
            "message": "YOLO11 is not used: no suitable bounding-box training data or detector weights are present, and prior evaluation rejected the crop pipeline for field inference.",
        },
        "weather": {
            "source": observation.source,
            "observed_at": observation.observed_at,
            "freshness": "current" if fresh_observation else "cached",
        },
        "saved_to_history": False,
    }


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
    expl = db.scalar(select(Explanation).where(
        Explanation.prediction_id == diagnosis_id,
        Explanation.explanation_type == "grad_cam_plus_plus"
    ))
    if not expl or not expl.structured_result or not expl.structured_result.get("heatmap_base64"):
        raise HTTPException(status_code=404, detail="No heatmap was generated for this diagnosis.")
    import base64
    img_data = base64.b64decode(expl.structured_result["heatmap_base64"])
    return Response(content=img_data, media_type="image/jpeg")


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
def admin_data_quality(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    pending_count = db.scalar(
        select(func.count()).select_from(DiseaseObservation).where(DiseaseObservation.verification_status == "pending")
    ) or 0
    verified_count = db.scalar(
        select(func.count()).select_from(DiseaseObservation).where(
            DiseaseObservation.verification_status == "verified",
            DiseaseObservation.research_consent.is_(True),
        )
    ) or 0
    weather_complete_count = db.scalar(
        select(func.count()).select_from(DiseaseObservation).where(
            DiseaseObservation.verification_status == "verified",
            DiseaseObservation.research_consent.is_(True),
            DiseaseObservation.environment_snapshot.is_not(None),
        )
    ) or 0
    return {
        "status": "collecting_observations",
        "pending_review": pending_count,
        "verified_consented": verified_count,
        "verified_consented_with_weather_snapshot": weather_complete_count,
        "issues": ["No environmental disease model is activated; field labels and validation data are still required."],
        "message": "Farmer reports are not training labels until reviewed with field or laboratory evidence. Current weather snapshots are not a future disease forecast.",
    }


@router.get("/admin/disease-observations/pending")
def admin_pending_disease_observations(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    reports = db.scalars(
        select(DiseaseObservation)
        .where(DiseaseObservation.verification_status == "pending")
        .order_by(DiseaseObservation.created_at.asc())
        .limit(200)
    )
    return [
        {
            "id": report.id,
            "farm_id": report.farm_id,
            "reported_by_user_id": report.reported_by_user_id,
            "disease_class": report.disease_class,
            "reported_outcome": report.reported_outcome,
            "observation_date": report.observation_date,
            "environment_snapshot": report.environment_snapshot,
            "research_consent": report.research_consent,
            "notes": report.notes,
            "created_at": report.created_at,
        }
        for report in reports
    ]


@router.patch("/admin/disease-observations/{observation_id}/review")
def review_disease_observation(
    observation_id: str,
    payload: DiseaseObservationReview,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = db.get(DiseaseObservation, observation_id)
    if not report:
        raise HTTPException(status_code=404, detail="Disease observation was not found.")
    if report.verification_status != "pending":
        raise HTTPException(status_code=409, detail="Only pending reports can be reviewed.")
    report.outcome = payload.outcome
    report.verification_status = "verified"
    report.verification_method = payload.verification_method.strip()
    report.source_reference = payload.source_reference.strip()
    report.reviewed_by_user_id = user.id
    record_audit(
        db,
        user,
        "disease_observation.verified",
        "disease_observation",
        report.id,
        {"outcome": report.outcome, "method": report.verification_method},
    )
    db.commit()
    return {
        "id": report.id,
        "outcome": report.outcome,
        "verification_status": report.verification_status,
        "verification_method": report.verification_method,
        "source_reference": report.source_reference,
        "included_in_training_export": report.research_consent,
    }


@router.get("/admin/disease-observations/training.csv")
def export_verified_training_observations(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    reports = db.scalars(
        select(DiseaseObservation)
        .where(
            DiseaseObservation.verification_status == "verified",
            DiseaseObservation.research_consent.is_(True),
            DiseaseObservation.farm_id.is_not(None),
        )
        .order_by(DiseaseObservation.observation_date.asc())
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "date", "farm_group", "disease_class", "outcome", "verification_status", "research_consent", "soil_ph",
        "temperature_c", "relative_humidity_pct", "rainfall_mm",
        "wind_speed_kmh", "dew_point_c",
    ])
    for report in reports:
        snapshot = report.environment_snapshot or {}
        weather = snapshot.get("weather") or {}
        writer.writerow([
            report.observation_date.isoformat(),
            report.farm_id,
            report.disease_class,
            report.outcome,
            report.verification_status,
            report.research_consent,
            snapshot.get("soil_ph"),
            weather.get("temperature_c"),
            weather.get("relative_humidity_pct"),
            weather.get("rainfall_mm"),
            weather.get("wind_speed_kmh"),
            weather.get("dew_point_c"),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="verified-environmental-observations.csv"'},
    )


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    image_model_status = (
        "experimental_enabled"
        if settings.enable_experimental_image_model and settings.resolved_image_model_path.is_file()
        else "disabled" if not settings.enable_experimental_image_model else "unavailable"
    )
    risk_model_status = (
        "experimental_enabled"
        if settings.enable_experimental_risk_model and has_any_model(str(settings.resolved_risk_model_path))
        else "disabled" if not settings.enable_experimental_risk_model else "unavailable"
    )
    checks = {
        "database": "ok",
        "image_model": image_model_status,
        "synthetic_demo": "disabled" if settings.app_env.lower() == "production" else "development_only",
        "risk_model": risk_model_status,
        "risk_models": {
            disease: (
                "experimental_enabled"
                if settings.enable_experimental_risk_model and has_model(str(settings.resolved_risk_model_path), disease)
                else "disabled" if not settings.enable_experimental_risk_model else "unavailable"
            )
            for disease in ("Mosaic", "RedRot", "Rust", "Yellow", "Wilt")
        },
    }
    try:
        db.execute(select(User.id).limit(1))
    except Exception as exc:
        logger.error("Readiness database check failed: %s", type(exc).__name__)
        checks["database"] = "unavailable"
        return {"status": "not_ready", "checks": checks}
    return {"status": "ready" if checks["database"] == "ok" else "not_ready", "checks": checks}
