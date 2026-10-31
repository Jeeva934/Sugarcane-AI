"""Capture verified disease labels and consented field conditions."""

from alembic import op
import sqlalchemy as sa

revision = "0004_verified_disease_observations"
down_revision = "0003_farm_soil_ph"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("disease_observations") as batch_op:
        batch_op.add_column(sa.Column("reported_by_user_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_disease_observations_reported_by_user_id_users",
            "users",
            ["reported_by_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.add_column(sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_disease_observations_reviewed_by_user_id_users",
            "users",
            ["reviewed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.add_column(
            sa.Column("reported_outcome", sa.String(length=30), nullable=False, server_default="unsure")
        )
        batch_op.add_column(
            sa.Column("verification_status", sa.String(length=20), nullable=False, server_default="pending")
        )
        batch_op.add_column(sa.Column("environment_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("research_consent", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.create_index(
        "ix_disease_observations_reported_by_user_id",
        "disease_observations",
        ["reported_by_user_id"],
    )
    op.create_index(
        "ix_disease_observations_reviewed_by_user_id",
        "disease_observations",
        ["reviewed_by_user_id"],
    )


def downgrade():
    op.drop_index(
        "ix_disease_observations_reviewed_by_user_id",
        table_name="disease_observations",
    )
    op.drop_index(
        "ix_disease_observations_reported_by_user_id",
        table_name="disease_observations",
    )
    with op.batch_alter_table("disease_observations") as batch_op:
        batch_op.drop_constraint("fk_disease_observations_reviewed_by_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("fk_disease_observations_reported_by_user_id_users", type_="foreignkey")
        batch_op.drop_column("research_consent")
        batch_op.drop_column("environment_snapshot")
        batch_op.drop_column("verification_status")
        batch_op.drop_column("reported_outcome")
        batch_op.drop_column("reviewed_by_user_id")
        batch_op.drop_column("reported_by_user_id")
