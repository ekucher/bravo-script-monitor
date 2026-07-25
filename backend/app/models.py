from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentStatus(str, enum.Enum):
    pending = "pending"
    online = "online"
    offline = "offline"
    disabled = "disabled"


class JobStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class EventSeverity(str, enum.Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    installations: Mapped[list[Installation]] = relationship(back_populates="organization")
    products: Mapped[list[Product]] = relationship(back_populates="organization")
    scripts: Mapped[list[Script]] = relationship(back_populates="organization")


class Installation(TimestampMixin, Base):
    __tablename__ = "installations"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="installations")
    servers: Mapped[list[Server]] = relationship(back_populates="installation")


class Server(TimestampMixin, Base):
    __tablename__ = "servers"
    __table_args__ = (UniqueConstraint("installation_id", "hostname"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    installation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("installations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    operating_system: Mapped[str | None] = mapped_column(String(255))
    inventory: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    installation: Mapped[Installation] = relationship(back_populates="servers")
    agents: Mapped[list[Agent]] = relationship(back_populates="server")


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (UniqueConstraint("server_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("servers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), default="default", nullable=False)
    version: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, name="agent_status"), default=AgentStatus.pending, nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    token_hash: Mapped[str | None] = mapped_column(String(255))

    server: Mapped[Server] = relationship(back_populates="agents")
    jobs: Mapped[list[Job]] = relationship(back_populates="agent")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("organization_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="products")
    modules: Mapped[list[ProductModule]] = relationship(back_populates="product")


class ProductModule(TimestampMixin, Base):
    __tablename__ = "product_modules"
    __table_args__ = (UniqueConstraint("product_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)

    product: Mapped[Product] = relationship(back_populates="modules")


class Script(TimestampMixin, Base):
    __tablename__ = "scripts"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[Organization] = relationship(back_populates="scripts")
    versions: Mapped[list[ScriptVersion]] = relationship(back_populates="script")


class ScriptVersion(TimestampMixin, Base):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("script_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    script_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parameter_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    script: Mapped[Script] = relationship(back_populates="versions")
    jobs: Mapped[list[Job]] = relationship(back_populates="script_version")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    script_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("script_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.pending, nullable=False, index=True
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    agent: Mapped[Agent] = relationship(back_populates="jobs")
    script_version: Mapped[ScriptVersion] = relationship(back_populates="jobs")
    executions: Mapped[list[Execution]] = relationship(back_populates="job")


class Execution(TimestampMixin, Base):
    __tablename__ = "executions"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt"),
        Index("ix_executions_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="execution_status"), default=JobStatus.pending, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)

    job: Mapped[Job] = relationship(back_populates="executions")


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_severity_created_at", "severity", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), index=True
    )
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity, name="event_severity"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (Index("ix_audit_records_org_created_at", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
