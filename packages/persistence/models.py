from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from packages.domain.retrieval import EMBEDDING_DIMENSIONS
from packages.domain.runs import TERMINAL_STATUSES, RunStatus
from packages.domain.tools import ApprovalStatus, InvocationStatus

RUN_STATUS_SQL = ", ".join(f"'{status.value}'" for status in RunStatus)
TERMINAL_STATUS_SQL = ", ".join(sorted(f"'{status.value}'" for status in TERMINAL_STATUSES))
INVOCATION_STATUS_SQL = ", ".join(f"'{status.value}'" for status in InvocationStatus)
APPROVAL_STATUS_SQL = ", ".join(f"'{status.value}'" for status in ApprovalStatus)
TENANT_TABLES = (
    "tenants",
    "agents",
    "agent_versions",
    "conversations",
    "agent_runs",
    "retrieval_chunks",
    "tool_invocations",
    "tool_approvals",
    "usage_records",
    "tenant_budgets",
)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_agents_tenant_id_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "agent_id"], ["agents.tenant_id", "agents.id"]),
        UniqueConstraint("tenant_id", "agent_id", "id", name="uq_versions_tenant_agent_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    code: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt: Mapped[str] = mapped_column(String(200), nullable=False)
    model_policy: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_policy: Mapped[str] = mapped_column(String(200), nullable=False)
    retrieval_config: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_conversations_tenant_id_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "agent_id", "agent_version_id"],
            ["agent_versions.tenant_id", "agent_versions.agent_id", "agent_versions.id"],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "conversation_id"], ["conversations.tenant_id", "conversations.id"]
        ),
        CheckConstraint(f"status IN ({RUN_STATUS_SQL})", name="ck_agent_runs_status"),
        CheckConstraint(
            f"(status IN ({TERMINAL_STATUS_SQL})) = (finished_at IS NOT NULL)",
            name="ck_agent_runs_terminal_finished_at",
        ),
        Index("ix_agent_runs_tenant_id_status", "tenant_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    agent_version_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RetrievalChunk(Base):
    __tablename__ = "retrieval_chunks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_retrieval_chunks_tenant_id_id"),
        Index("ix_retrieval_chunks_tenant_collection", "tenant_id", "collection"),
        Index(
            "ix_retrieval_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    collection: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(String(20_000), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tool_invocations_tenant_id_id"),
        CheckConstraint(f"status IN ({INVOCATION_STATUS_SQL})", name="ck_tool_invocations_status"),
        Index(
            "uq_tool_invocations_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_tool_invocations_tenant_tool", "tenant_id", "tool_name"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    arguments_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolApproval(Base):
    __tablename__ = "tool_approvals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_tool_approvals_tenant_id_id"),
        CheckConstraint(f"status IN ({APPROVAL_STATUS_SQL})", name="ck_tool_approvals_status"),
        Index(
            "ix_tool_approvals_lookup",
            "tenant_id",
            "tool_name",
            "arguments_digest",
            "status",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_usage_records_tenant_id_id"),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cost_micros >= 0",
            name="ck_usage_records_nonnegative",
        ),
        Index("ix_usage_records_tenant_created", "tenant_id", "created_at"),
        Index("ix_usage_records_tenant_model", "tenant_id", "logical_model"),
        Index(
            "uq_usage_records_tenant_idempotency",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    logical_model: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantBudget(Base):
    """Optional monthly admission limits. Absent columns mean unlimited."""

    __tablename__ = "tenant_budgets"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_budgets_tenant_id"),
        CheckConstraint(
            "(monthly_cost_micros IS NULL OR monthly_cost_micros >= 0) AND "
            "(monthly_tokens IS NULL OR monthly_tokens >= 0)",
            name="ck_tenant_budgets_nonnegative",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    monthly_cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    monthly_tokens: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
