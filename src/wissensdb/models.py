from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from wissensdb.database import Base
from wissensdb.enums import AgentRole, KnowledgeStatus, KnowledgeType


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    repos: Mapped[list["Repo"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Repo(TimestampMixin, Base):
    __tablename__ = "repos"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_repos_project_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str | None] = mapped_column(String(1024))
    default_area: Mapped[str | None] = mapped_column(String(120))

    project: Mapped[Project] = relationship(back_populates="repos")


class ProjectArea(TimestampMixin, Base):
    __tablename__ = "project_areas"
    __table_args__ = (
        UniqueConstraint("project_id", "repo_id", "area", name="uq_project_area_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"), nullable=False, index=True)
    area: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, values_callable=enum_values), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)


class KnowledgeItem(TimestampMixin, Base):
    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"), nullable=False, index=True)
    area: Mapped[str | None] = mapped_column(String(120), index=True)
    type: Mapped[KnowledgeType] = mapped_column(
        Enum(KnowledgeType, values_callable=enum_values), nullable=False, index=True
    )
    status: Mapped[KnowledgeStatus] = mapped_column(
        Enum(KnowledgeStatus, values_callable=enum_values),
        nullable=False,
        default=KnowledgeStatus.ACTIVE,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(1024), nullable=False)
    path: Mapped[str | None] = mapped_column(String(1024))
    line_start: Mapped[int | None] = mapped_column(Integer)
    line_end: Mapped[int | None] = mapped_column(Integer)
    commit_sha: Mapped[str | None] = mapped_column(String(64), index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    updated_by: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_items.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(120), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, values_callable=enum_values), nullable=False
    )
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    repo_id: Mapped[int | None] = mapped_column(ForeignKey("repos.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_items.id"), index=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"), nullable=False, index=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running")
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
