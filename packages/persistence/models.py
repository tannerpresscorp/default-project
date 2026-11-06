from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from packages.domain.runs import TERMINAL_STATUSES, RunStatus

RUN_STATUS_SQL = ", ".join(f"'{status.value}'" for status in RunStatus)
TERMINAL_STATUS_SQL = ", ".join(sorted(f"'{status.value}'" for status in TERMINAL_STATUSES))


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
