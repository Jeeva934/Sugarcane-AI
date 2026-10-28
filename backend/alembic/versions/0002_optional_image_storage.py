"""Allow image prediction metadata to be saved without storing an upload."""

from alembic import op
from sqlalchemy import String

revision =  "0002_optional_image_storage"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("image_diagnoses") as batch_op:
        batch_op.alter_column("image_storage_key", existing_type=String(length=500), nullable=True)


def downgrade():
    with op.batch_alter_table("image_diagnoses") as batch_op:
        batch_op.alter_column("image_storage_key", existing_type=String(length=500), nullable=False)
