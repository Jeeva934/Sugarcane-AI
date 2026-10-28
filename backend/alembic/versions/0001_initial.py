"""Create application tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("preferred_language", sa.String(length=2), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "farms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("crop_variety", sa.String(length=120)),
        sa.Column("planting_date", sa.Date()),
        sa.Column("growth_stage", sa.String(length=80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_farms_user_id", "farms", ["user_id"])
    op.create_table(
        "weather_observations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("farm_id", sa.String(length=36), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_mean", sa.Float()),
        sa.Column("temperature_min", sa.Float()),
        sa.Column("temperature_max", sa.Float()),
        sa.Column("relative_humidity", sa.Float()),
        sa.Column("dew_point", sa.Float()),
        sa.Column("precipitation", sa.Float()),
        sa.Column("wind_speed", sa.Float()),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_metadata", sa.JSON()),
        sa.UniqueConstraint("farm_id", "source", "observed_at", name="uq_weather_farm_source_time"),
    )
    op.create_index("ix_weather_observations_farm_id", "weather_observations", ["farm_id"])
    op.create_index("ix_weather_farm_observed", "weather_observations", ["farm_id", "observed_at"])
    op.create_table(
        "disease_observations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("farm_id", sa.String(length=36), sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("disease_class", sa.String(length=100), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("verification_method", sa.String(length=120)),
        sa.Column("source_reference", sa.String(length=500)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_disease_observations_farm_id", "disease_observations", ["farm_id"])
    op.create_index("ix_disease_observations_disease_class", "disease_observations", ["disease_class"])
    op.create_table(
        "risk_predictions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", sa.String(length=36), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("disease_class", sa.String(length=100), nullable=False),
        sa.Column("risk_score", sa.Float()),
        sa.Column("risk_category", sa.String(length=40)),
        sa.Column("prediction_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weather_data_timestamp", sa.DateTime(timezone=True)),
        sa.Column("data_freshness_status", sa.String(length=40), nullable=False),
        sa.Column("model_version", sa.String(length=80)),
        sa.Column("explanation_reference", sa.String(length=500)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_period_start", sa.DateTime(timezone=True)),
        sa.Column("input_period_end", sa.DateTime(timezone=True)),
        sa.Column("forecast_horizon_days", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_risk_predictions_user_id", "risk_predictions", ["user_id"])
    op.create_index("ix_risk_predictions_farm_id", "risk_predictions", ["farm_id"])
    op.create_index("ix_risk_user_created", "risk_predictions", ["user_id", "created_at"])
    op.create_table(
        "image_diagnoses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("farm_id", sa.String(length=36), sa.ForeignKey("farms.id", ondelete="SET NULL")),
        sa.Column("image_storage_key", sa.String(length=500), nullable=False),
        sa.Column("predicted_class", sa.String(length=100)),
        sa.Column("confidence", sa.Float()),
        sa.Column("alternative_predictions", sa.JSON()),
        sa.Column("detector_model_version", sa.String(length=80)),
        sa.Column("classifier_model_version", sa.String(length=80)),
        sa.Column("processing_time_ms", sa.Integer()),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("uncertainty_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_image_diagnoses_user_id", "image_diagnoses", ["user_id"])
    op.create_index("ix_image_diagnoses_farm_id", "image_diagnoses", ["farm_id"])
    op.create_index("ix_diagnosis_user_created", "image_diagnoses", ["user_id", "created_at"])
    op.create_table(
        "explanations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("prediction_type", sa.String(length=40), nullable=False),
        sa.Column("prediction_id", sa.String(length=36), nullable=False),
        sa.Column("explanation_type", sa.String(length=40), nullable=False),
        sa.Column("storage_reference", sa.String(length=500)),
        sa.Column("structured_result", sa.JSON()),
        sa.Column("model_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_explanations_prediction_type", "explanations", ["prediction_type"])
    op.create_index("ix_explanations_prediction_id", "explanations", ["prediction_id"])
    op.create_table(
        "disease_knowledge",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("disease_class", sa.String(length=100), nullable=False),
        sa.Column("language_code", sa.String(length=2), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("scientific_name", sa.String(length=160)),
        sa.Column("symptoms", sa.Text(), nullable=False),
        sa.Column("preventive_guidance", sa.Text(), nullable=False),
        sa.Column("monitoring_guidance", sa.Text(), nullable=False),
        sa.Column("management_guidance", sa.Text()),
        sa.Column("source_reference", sa.String(length=1000), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("disease_class", "language_code", name="uq_knowledge_disease_language"),
    )
    op.create_index("ix_disease_knowledge_disease_class", "disease_knowledge", ["disease_class"])
    op.create_table(
        "model_versions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("model_type", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("artifact_reference", sa.String(length=500)),
        sa.Column("framework", sa.String(length=80)),
        sa.Column("dataset_version", sa.String(length=120)),
        sa.Column("metrics", sa.JSON()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("model_type", "version", name="uq_model_type_version"),
    )
    op.create_index("ix_model_versions_model_type", "model_versions", ["model_type"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON()),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])


def downgrade():
    op.drop_table("audit_logs")
    op.drop_table("model_versions")
    op.drop_table("disease_knowledge")
    op.drop_table("explanations")
    op.drop_table("image_diagnoses")
    op.drop_table("risk_predictions")
    op.drop_table("disease_observations")
    op.drop_table("weather_observations")
    op.drop_table("farms")
    op.drop_table("users")
