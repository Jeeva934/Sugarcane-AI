"""Allow all supported interface language codes."""

from alembic import op
import sqlalchemy as sa

revision = "0005_user_language_codes"
down_revision = "0004_verified_disease_observations"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "preferred_language",
            existing_type=sa.String(length=2),
            type_=sa.String(length=5),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "preferred_language",
            existing_type=sa.String(length=5),
            type_=sa.String(length=2),
            existing_nullable=False,
        )
