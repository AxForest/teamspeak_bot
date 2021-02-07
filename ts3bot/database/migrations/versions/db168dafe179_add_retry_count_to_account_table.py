"""Add retry count to account table

Revision ID: db168dafe179
Revises: 2b6daf0b7566
Create Date: 2020-10-16 18:31:25.047238

"""
import sqlalchemy as sa
from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision = "db168dafe179"
down_revision = "2b6daf0b7566"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column(
            "retries",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("accounts", "retries")
