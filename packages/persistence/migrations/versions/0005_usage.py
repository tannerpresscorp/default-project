"""Tenant-scoped usage records with forced RLS."""

import sqlalchemy as sa
from alembic import op

revision = "0005_usage"
down_revision = "0004_tool_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("logical_model", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_usage_records_tenant_id_id"),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cost_micros >= 0",
            name="ck_usage_records_nonnegative",
        ),
    )
    op.create_index("ix_usage_records_tenant_created", "usage_records", ["tenant_id", "created_at"])
    op.create_index(
        "ix_usage_records_tenant_model", "usage_records", ["tenant_id", "logical_model"]
    )
    op.execute("ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE usage_records FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON usage_records
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)""")


def downgrade():
    op.drop_table("usage_records")
