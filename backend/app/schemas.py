from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

SUPPORTED_LANGUAGES = (
    "en", "hi", "bn", "te", "mr", "ta", "ur", "gu",
    "kn", "or", "ml", "pa", "as", "mai", "sa", "ks",
)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    preferred_language: Literal[
        "en", "hi", "bn", "te", "mr", "ta", "ur", "gu",
        "kn", "or", "ml", "pa", "as", "mai", "sa", "ks",
    ] = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    preferred_language: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class UserPreferences(BaseModel):
    preferred_language: Literal[
        "en", "hi", "bn", "te", "mr", "ta", "ur", "gu",
        "kn", "or", "ml", "pa", "as", "mai", "sa", "ks",
    ]


class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    soil_ph: float | None = Field(default=None, ge=0, le=14)
    crop_variety: str | None = Field(default=None, max_length=120)
    planting_date: date | None = None
    growth_stage: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together.")
        return self


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    soil_ph: float | None = Field(default=None, ge=0, le=14)
    crop_variety: str | None = Field(default=None, max_length=120)
    planting_date: date | None = None
    growth_stage: str | None = Field(default=None, max_length=80)


class FarmOut(BaseModel):
    id: str
    name: str
    latitude: float | None
    longitude: float | None
    soil_ph: float | None
    crop_variety: str | None
    planting_date: date | None
    growth_stage: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RiskRequest(BaseModel):
    farm_id: str
    disease_class: Literal["Mosaic", "RedRot", "Rust", "Yellow", "Wilt"]
    period_start: datetime | None = None
    period_end: datetime | None = None
    grass_age: str | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_start is not None and self.period_end is not None and self.period_start >= self.period_end:
            raise ValueError("period_start must be earlier than period_end.")
        return self


class WeatherGuidanceRequest(BaseModel):
    farm_id: str
    disease_class: Literal["Mosaic", "RedRot", "Rust", "Yellow", "Wilt"]
    language_code: Literal[
        "en", "hi", "bn", "te", "mr", "ta", "ur", "gu",
        "kn", "or", "ml", "pa", "as", "mai", "sa", "ks",
    ] | None = None
    grass_age: str | None = None


class WeatherMeasurementsOut(BaseModel):
    temperature_c: float | None
    relative_humidity_pct: float | None
    dew_point_c: float | None
    rainfall_mm: float | None
    wind_speed_kmh: float | None


class WeatherGuidanceOut(BaseModel):
    status: Literal["generated"]
    model: str
    weather_observed_at: datetime
    weather_freshness: Literal["current", "cached"]
    weather_history_days: int = Field(ge=0, le=8)
    weather_measurements: WeatherMeasurementsOut
    disease_class: str
    risk_level: Literal["insufficient_data", "low", "moderate", "high"]
    risk_reason: str
    summary: str
    weather_effect: str
    actions: list[str] = Field(min_length=1, max_length=4)
    watch_for: list[str] = Field(max_length=4)
    limitations: str


class DiseaseObservationCreate(BaseModel):
    farm_id: str
    disease_class: Literal["Healthy", "Mosaic", "RedRot", "Rust", "Yellow", "Wilt"]
    reported_outcome: Literal["symptoms_seen", "not_seen", "unsure"]
    research_consent: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class DiseaseObservationReview(BaseModel):
    outcome: Literal["present", "absent"]
    verification_method: str = Field(min_length=3, max_length=120)
    source_reference: str = Field(min_length=3, max_length=500)


class KnowledgeOut(BaseModel):
    disease_class: str
    language_code: str
    display_name: str
    scientific_name: str | None
    symptoms: str
    preventive_guidance: str
    monitoring_guidance: str
    management_guidance: str | None
    source_reference: str
    last_reviewed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeCreate(BaseModel):
    disease_class: str = Field(min_length=1, max_length=100)
    language_code: Literal["en", "ta"]
    display_name: str = Field(min_length=1, max_length=160)
    scientific_name: str | None = Field(default=None, max_length=160)
    symptoms: str = Field(min_length=1)
    preventive_guidance: str = Field(min_length=1)
    monitoring_guidance: str = Field(min_length=1)
    management_guidance: str | None = None
    source_reference: str = Field(min_length=1, max_length=1000)
    last_reviewed_at: datetime | None = None
    is_published: bool = False


class KnowledgeUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    scientific_name: str | None = Field(default=None, max_length=160)
    symptoms: str | None = Field(default=None, min_length=1)
    preventive_guidance: str | None = Field(default=None, min_length=1)
    monitoring_guidance: str | None = Field(default=None, min_length=1)
    management_guidance: str | None = None
    source_reference: str | None = Field(default=None, min_length=1, max_length=1000)
    last_reviewed_at: datetime | None = None
    is_published: bool | None = None
