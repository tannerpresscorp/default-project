"""Initial tenant-scoped platform tables and PostgreSQL isolation."""

import sqlalchemy as sa
from alembic import op

revision = "0001_platform"
down_revision = None
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade():
    op.create_table("tenants", *common(), sa.Column("name", sa.String(200), nullable=False))
    op.create_table(
        "agents",
        *common(),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_agents_tenant_id_id"),
    )
    op.create_table(
        "agent_versions",
        *common(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        *(
            sa.Column(name, sa.String(200), nullable=False)
            for name in ("code", "prompt", "model_policy", "tool_policy", "retrieval_config")
        ),
        sa.ForeignKeyConstraint(["tenant_id", "agent_id"], ["agents.tenant_id", "agents.id"]),
        sa.UniqueConstraint("tenant_id", "agent_id", "id", name="uq_versions_tenant_agent_id"),
    )
    op.create_table(
        "conversations",
        *common(),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_conversations_tenant_id_id"),
    )
    op.create_table(
        "agent_runs",
        *common(),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "agent_id", "agent_version_id"],
            ["agent_versions.tenant_id", "agent_versions.agent_id", "agent_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "conversation_id"], ["conversations.tenant_id", "conversations.id"]
        ),
    )
    for table in ("agents", "agent_versions", "conversations", "agent_runs"):
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
    for table in ("tenants", "agents", "agent_versions", "conversations", "agent_runs"):
        column = "id" if table == "tenants" else "tenant_id"
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY tenant_isolation ON "{table}"
            USING ({column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK ({column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)''')
    op.execute("""CREATE FUNCTION reject_agent_version_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'agent versions are immutable'; END $$""")
    op.execute("""CREATE TRIGGER immutable_agent_version BEFORE UPDATE OR DELETE ON agent_versions
        FOR EACH ROW EXECUTE FUNCTION reject_agent_version_mutation()""")


def downgrade():
    op.execute("DROP TRIGGER immutable_agent_version ON agent_versions")
    op.execute("DROP FUNCTION reject_agent_version_mutation()")
    for table in ("agent_runs", "conversations", "agent_versions", "agents", "tenants"):
        op.drop_table(table)
