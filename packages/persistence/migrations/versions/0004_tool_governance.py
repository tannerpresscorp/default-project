"""Audited tool invocations and durable approval records."""

import sqlalchemy as sa
from alembic import op

from packages.domain.tools import ApprovalStatus, InvocationStatus

revision = "0004_tool_governance"
down_revision = "0003_retrieval"
branch_labels = None
depends_on = None

INVOCATION_STATUSES = tuple(status.value for status in InvocationStatus)
APPROVAL_STATUSES = tuple(status.value for status in ApprovalStatus)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _tenant_policy(table: str) -> None:
    op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
    op.execute(f'''CREATE POLICY tenant_isolation ON "{table}"
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)''')


def upgrade():
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("arguments_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tool_invocations_tenant_id_id"),
        sa.CheckConstraint(
            f"status IN ({_quoted(INVOCATION_STATUSES)})", name="ck_tool_invocations_status"
        ),
    )
    op.create_index(
        "uq_tool_invocations_tenant_idempotency",
        "tool_invocations",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_tool_invocations_tenant_tool", "tool_invocations", ["tenant_id", "tool_name"]
    )
    _tenant_policy("tool_invocations")

    op.create_table(
        "tool_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("arguments_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tool_approvals_tenant_id_id"),
        sa.CheckConstraint(
            f"status IN ({_quoted(APPROVAL_STATUSES)})", name="ck_tool_approvals_status"
        ),
    )
    op.create_index(
        "ix_tool_approvals_lookup",
        "tool_approvals",
        ["tenant_id", "tool_name", "arguments_digest", "status"],
    )
    _tenant_policy("tool_approvals")


def downgrade():
    op.drop_table("tool_approvals")
    op.drop_table("tool_invocations")
