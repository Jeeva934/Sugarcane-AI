"""Store optional soil pH with farm location details."""

from alembic import op
import sqlalchemy as sa

revision = "0003_farm_soil_ph"
down_revision = "0002_optional_image_storage"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("farms", sa.Column("soil_ph", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("farms", "soil_ph")
