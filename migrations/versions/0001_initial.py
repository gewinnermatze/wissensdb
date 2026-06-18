"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


agent_role = sa.Enum("reader", "contributor", "maintainer", name="agentrole")
knowledge_type = sa.Enum(
    "code_map",
    "architecture",
    "goal",
    "todo",
    "decision",
    "setup",
    "gotcha",
    "note",
    name="knowledgetype",
)
knowledge_status = sa.Enum("active", "needs_review", "stale", "archived", name="knowledgestatus")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_slug"), "projects", ["slug"], unique=True)

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("role", agent_role, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "repos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("default_area", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug", name="uq_repos_project_slug"),
    )
    op.create_index(op.f("ix_repos_project_id"), "repos", ["project_id"], unique=False)
    op.create_index(op.f("ix_repos_slug"), "repos", ["slug"], unique=False)

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("area", sa.String(length=120), nullable=True),
        sa.Column("type", knowledge_type, nullable=False),
        sa.Column("status", knowledge_status, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("source_ref", sa.String(length=1024), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("updated_by", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in [
        "area",
        "commit_sha",
        "content_hash",
        "created_by",
        "repo_id",
        "project_id",
        "status",
        "type",
        "updated_by",
    ]:
        op.create_index(f"ix_knowledge_items_{column}", "knowledge_items", [column], unique=False)

    op.create_table(
        "project_areas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("area", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "repo_id", "area", name="uq_project_area_scope"),
    )
    op.create_index(op.f("ix_project_areas_area"), "project_areas", ["area"], unique=False)
    op.create_index(
        op.f("ix_project_areas_project_id"), "project_areas", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_project_areas_repo_id"), "project_areas", ["repo_id"], unique=False)

    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("changed_by", sa.String(length=120), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_versions_item_id"), "knowledge_versions", ["item_id"], unique=False
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("role", agent_role, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("repo_id", sa.Integer(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["action", "actor", "item_id", "project_id", "repo_id"]:
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column], unique=False)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ingestion_runs_project_id"), "ingestion_runs", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_ingestion_runs_repo_id"), "ingestion_runs", ["repo_id"], unique=False)


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("audit_events")
    op.drop_table("knowledge_versions")
    op.drop_table("project_areas")
    op.drop_table("knowledge_items")
    op.drop_table("repos")
    op.drop_table("agents")
    op.drop_index(op.f("ix_projects_slug"), table_name="projects")
    op.drop_table("projects")
    knowledge_status.drop(op.get_bind(), checkfirst=True)
    knowledge_type.drop(op.get_bind(), checkfirst=True)
    agent_role.drop(op.get_bind(), checkfirst=True)
