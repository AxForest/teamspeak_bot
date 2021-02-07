"""add is_leader to link_account_guild

Revision ID: 2b6daf0b7566
Revises: fba1fdd7123a
Create Date: 2020-07-05 22:24:09.581633

"""
import sqlalchemy as sa
from alembic import op  # type: ignore
from sqlalchemy.sql import expression

# revision identifiers, used by Alembic.
revision = "2b6daf0b7566"
down_revision = "fba1fdd7123a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "link_account_guild",
        sa.Column(
            "is_leader", sa.Boolean(), server_default=expression.false(), nullable=False
        ),
    )


def downgrade():
    op.drop_column("link_account_guild", "is_leader")
