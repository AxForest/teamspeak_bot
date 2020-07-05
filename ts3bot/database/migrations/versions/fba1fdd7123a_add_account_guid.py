"""Add account guid column

Revision ID: fba1fdd7123a
Revises: 40a5381846f2
Create Date: 2020-07-05 22:01:42.143181

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fba1fdd7123a"
down_revision = "40a5381846f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("guid", sa.String(length=36), nullable=True))


def downgrade():
    op.drop_column("accounts", "guid")
