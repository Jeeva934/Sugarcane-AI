import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    preferred_language: Mapped[str] = mapped_column(String(5), default="en")
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    farms: Mapped[list["Farm"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    soil_ph: Mapped[float | None] = mapped_column(Float)
    crop_variety: Mapped[str | None] = mapped_column(String(120))
    planting_date: Mapped[date | None] = mapped_column(Date)
    growth_stage: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    owner: Mapped[User] = relationship(back_populates="farms")


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    __table_args__ = (
        UniqueConstraint("farm_id", "source", "observed_at", name="uq_weather_farm_source_time"),
        Index("ix_weather_farm_observed", "farm_id", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature_mean: Mapped[float | None] = mapped_column(Float)
    temperature_min: Mapped[float | None] = mapped_column(Float)
    temperature_max: Mapped[float | None] = mapped_column(Float)
    relative_humidity: Mapped[float | None] = mapped_column(Float)
    dew_point: Mapped[float | None] = mapped_column(Float)
    precipitation: Mapped[float | None] = mapped_column(Float)
    wind_speed: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(80))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON)


class DiseaseObservation(Base):
    __tablename__ = "disease_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    farm_id: Mapped[str | None] = mapped_column(ForeignKey("farms.id", ondelete="SET NULL"), index=True)
    reported_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    disease_class: Mapped[str] = mapped_column(String(100), index=True)
    observation_date: Mapped[date] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(20))
    reported_outcome: Mapped[str] = mapped_column(String(30), default="unsure")
    verification_status: Mapped[str] = mapped_column(String(20), default="pending")
    verification_method: Mapped[str | None] = mapped_column(String(120))
    source_reference: Mapped[str | None] = mapped_column(String(500))
    environment_snapshot: Mapped[dict | None] = mapped_column(JSON)
    research_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RiskPrediction(Base):
    __tablename__ = "risk_predictions"
    __table_args__ = (Index("ix_risk_user_created", "user_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    farm_id: Mapped[str] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"), index=True)
    disease_class: Mapped[str] = mapped_column(String(100))
    risk_score: Mapped[float | None] = mapped_column(Float)
    risk_category: Mapped[str | None] = mapped_column(String(40))
    prediction_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    weather_data_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_freshness_status: Mapped[str] = mapped_column(String(40))
    model_version: Mapped[str | None] = mapped_column(String(80))
    explanation_reference: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40))
    input_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    forecast_horizon_days: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ImageDiagnosis(Base):
    __tablename__ = "image_diagnoses"
    __table_args__ = (Index("ix_diagnosis_user_created", "user_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    farm_id: Mapped[str | None] = mapped_column(ForeignKey("farms.id", ondelete="SET NULL"), index=True)
    image_storage_key: Mapped[str | None] = mapped_column(String(500))
    predicted_class: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    alternative_predictions: Mapped[list | None] = mapped_column(JSON)
    detector_model_version: Mapped[str | None] = mapped_column(String(80))
    classifier_model_version: Mapped[str | None] = mapped_column(String(80))
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    uncertainty_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Explanation(Base):
    __tablename__ = "explanations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prediction_type: Mapped[str] = mapped_column(String(40), index=True)
    prediction_id: Mapped[str] = mapped_column(String(36), index=True)
    explanation_type: Mapped[str] = mapped_column(String(40))
    storage_reference: Mapped[str | None] = mapped_column(String(500))
    structured_result: Mapped[dict | None] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DiseaseKnowledge(Base):
    __tablename__ = "disease_knowledge"
    __table_args__ = (UniqueConstraint("disease_class", "language_code", name="uq_knowledge_disease_language"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    disease_class: Mapped[str] = mapped_column(String(100), index=True)
    language_code: Mapped[str] = mapped_column(String(2))
    display_name: Mapped[str] = mapped_column(String(160))
    scientific_name: Mapped[str | None] = mapped_column(String(160))
    symptoms: Mapped[str] = mapped_column(Text)
    preventive_guidance: Mapped[str] = mapped_column(Text)
    monitoring_guidance: Mapped[str] = mapped_column(Text)
    management_guidance: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(String(1000))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_type", "version", name="uq_model_type_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    model_type: Mapped[str] = mapped_column(String(40), index=True)
    version: Mapped[str] = mapped_column(String(80))
    artifact_reference: Mapped[str | None] = mapped_column(String(500))
    framework: Mapped[str | None] = mapped_column(String(80))
    dataset_version: Mapped[str | None] = mapped_column(String(120))
    metrics: Mapped[dict | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(120))
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
