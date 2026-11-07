"""Tenant-scoped pgvector retrieval chunks and HNSW similarity index."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from packages.domain.retrieval import EMBEDDING_DIMENSIONS

revision = "0003_retrieval"
down_revision = "0002_agent_run_state"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "retrieval_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("collection", sa.String(64), nullable=False),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("content", sa.String(20_000), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_retrieval_chunks_tenant_id_id"),
    )
    op.create_index(
        "ix_retrieval_chunks_tenant_collection",
        "retrieval_chunks",
        ["tenant_id", "collection"],
    )
    op.create_index(
        "ix_retrieval_chunks_embedding",
        "retrieval_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.execute("ALTER TABLE retrieval_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE retrieval_chunks FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON retrieval_chunks
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)""")


def downgrade():
    op.drop_table("retrieval_chunks")
