"""Tenant budgets and idempotent usage records with forced RLS."""

import sqlalchemy as sa
from alembic import op

revision = "0006_budgets_usage_idempotency"
down_revision = "0005_usage"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenant_budgets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("monthly_cost_micros", sa.BigInteger(), nullable=True),
        sa.Column("monthly_tokens", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_budgets_tenant_id"),
        sa.CheckConstraint(
            "(monthly_cost_micros IS NULL OR monthly_cost_micros >= 0) AND "
            "(monthly_tokens IS NULL OR monthly_tokens >= 0)",
            name="ck_tenant_budgets_nonnegative",
        ),
    )
    op.execute("ALTER TABLE tenant_budgets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_budgets FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON tenant_budgets
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)""")

    op.add_column("usage_records", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.create_index(
        "uq_usage_records_tenant_idempotency",
        "usage_records",
        ["tenant_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_usage_records_tenant_idempotency", table_name="usage_records")
    op.drop_column("usage_records", "idempotency_key")
    op.drop_table("tenant_budgets")
