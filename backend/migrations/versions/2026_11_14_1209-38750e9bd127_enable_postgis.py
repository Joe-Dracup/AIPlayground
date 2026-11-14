"""enable postgis

Revision ID: 38750e9bd127
Revises: d566cf435632
Create Date: 2026-11-14 12:09:49.645239

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "38750e9bd127"
down_revision: str | Sequence[str] | None = "d566cf435632"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Adds the geometry and geography types and the ST_* functions. The image has to include
    # PostGIS (see db/Dockerfile) for this to work.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS postgis")
