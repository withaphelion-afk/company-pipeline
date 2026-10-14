"""person relevance: score, intent, reason"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("people")}
    if "score" not in cols:  # fresh databases already got them from 0001's create_all
        op.add_column("people", sa.Column("score", sa.Integer(), nullable=False, server_default="0"))
        op.add_column("people", sa.Column("intent", sa.String(10), nullable=True))
        op.add_column("people", sa.Column("reason", sa.Text(), nullable=True))
        op.create_index("ix_people_score", "people", ["score"])


def downgrade() -> None:
    op.drop_index("ix_people_score", "people")
    for c in ("reason", "intent", "score"):
        op.drop_column("people", c)
