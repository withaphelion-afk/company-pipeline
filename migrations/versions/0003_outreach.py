"""outreach cadence: draft kind/parent/due, person outreach status"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "kind" not in {c["name"] for c in insp.get_columns("drafts")}:  # fresh databases got them from create_all
        op.add_column("drafts", sa.Column("kind", sa.String(10), nullable=False, server_default="initial"))
        op.add_column("drafts", sa.Column("parent_id", sa.Integer(), sa.ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True))
        op.add_column("drafts", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    if "outreach" not in {c["name"] for c in insp.get_columns("people")}:
        op.add_column("people", sa.Column("outreach", sa.String(12), nullable=False, server_default="none"))


def downgrade() -> None:
    op.drop_column("people", "outreach")
    for c in ("due_at", "parent_id", "kind"):
        op.drop_column("drafts", c)
