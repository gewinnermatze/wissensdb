from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from wissensdb.enums import KnowledgeStatus
from wissensdb.models import AuditEvent, KnowledgeItem, KnowledgeVersion, Project, Repo
from wissensdb.schemas import KnowledgeSource, KnowledgeWrite, Scope


class ScopeError(ValueError):
    pass


@dataclass(frozen=True)
class KnowledgeSearchHit:
    item: KnowledgeItem
    score: float | None


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_project(self, slug: str, name: str, description: str | None = None) -> Project:
        project = Project(slug=slug, name=name, description=description)
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def create_repo(
        self,
        project_slug: str,
        slug: str,
        name: str,
        path: str | None = None,
        default_area: str | None = None,
    ) -> Repo:
        project = self.get_project(project_slug)
        repo = Repo(
            project_id=project.id,
            slug=slug,
            name=name,
            path=path,
            default_area=default_area,
        )
        self.session.add(repo)
        self.session.commit()
        self.session.refresh(repo)
        return repo

    def get_project(self, slug: str) -> Project:
        project = self.session.scalar(select(Project).where(Project.slug == slug))
        if project is None:
            raise ScopeError(f"unknown project: {slug}")
        return project

    def resolve_scope(self, scope: Scope) -> tuple[Project, Repo]:
        if not scope.project or not scope.repo:
            raise ScopeError("project and repo are required")
        project = self.get_project(scope.project)
        repo = self.session.scalar(
            select(Repo).where(Repo.project_id == project.id, Repo.slug == scope.repo)
        )
        if repo is None:
            raise ScopeError(f"unknown repo in project {scope.project}: {scope.repo}")
        return project, repo

    def get_item(self, item_id: int) -> KnowledgeItem:
        item = self.session.get(KnowledgeItem, item_id)
        if item is None:
            raise KeyError(f"unknown knowledge item: {item_id}")
        return item

    def get_items(self, item_ids: Iterable[int]) -> list[KnowledgeItem]:
        ids = list(item_ids)
        if not ids:
            return []
        items = self.session.scalars(select(KnowledgeItem).where(KnowledgeItem.id.in_(ids))).all()
        order = {item_id: idx for idx, item_id in enumerate(ids)}
        return sorted(items, key=lambda item: order.get(item.id, 999999))

    def list_items_for_scope(
        self,
        project_id: int,
        repo_id: int,
        area: str | None = None,
        include_inactive: bool = False,
    ) -> list[KnowledgeItem]:
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.repo_id == repo_id,
        )
        if area:
            stmt = stmt.where(KnowledgeItem.area == area)
        if not include_inactive:
            stmt = stmt.where(
                KnowledgeItem.status.in_(
                    [KnowledgeStatus.ACTIVE, KnowledgeStatus.NEEDS_REVIEW]
                )
            )
        return list(self.session.scalars(stmt).all())

    def get_scope_slugs(self, project_id: int, repo_id: int) -> tuple[str, str]:
        row = self.session.execute(
            select(Project.slug, Repo.slug).where(
                Project.id == project_id,
                Repo.id == repo_id,
                Repo.project_id == Project.id,
            )
        ).one()
        return row[0], row[1]

    def vector_search(
        self,
        project_id: int,
        repo_id: int,
        area: str | None,
        query_vector: list[float],
        limit: int,
        include_needs_review: bool,
    ) -> list[KnowledgeSearchHit]:
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            return self._postgres_vector_search(
                project_id,
                repo_id,
                area,
                query_vector,
                limit,
                include_needs_review,
            )
        return self._python_vector_search(
            project_id,
            repo_id,
            area,
            query_vector,
            limit,
            include_needs_review,
        )

    def _postgres_vector_search(
        self,
        project_id: int,
        repo_id: int,
        area: str | None,
        query_vector: list[float],
        limit: int,
        include_needs_review: bool,
    ) -> list[KnowledgeSearchHit]:
        statuses = [KnowledgeStatus.ACTIVE.value]
        if include_needs_review:
            statuses.append(KnowledgeStatus.NEEDS_REVIEW.value)

        area_clause = "AND area = :area" if area else ""
        stmt = text(
            f"""
            SELECT id, embedding <=> CAST(:query_vector AS vector) AS score
            FROM knowledge_items
            WHERE project_id = :project_id
              AND repo_id = :repo_id
              AND embedding IS NOT NULL
              AND status IN :statuses
              {area_clause}
            ORDER BY embedding <=> CAST(:query_vector AS vector)
            LIMIT :limit
            """
        ).bindparams(bindparam("statuses", expanding=True))
        rows = self.session.execute(
            stmt,
            {
                "project_id": project_id,
                "repo_id": repo_id,
                "area": area,
                "statuses": statuses,
                "query_vector": vector_literal(query_vector),
                "limit": limit,
            },
        ).all()
        ids = [row.id for row in rows]
        items = {item.id: item for item in self.get_items(ids)}
        return [
            KnowledgeSearchHit(item=items[row.id], score=float(row.score))
            for row in rows
            if row.id in items
        ]

    def _python_vector_search(
        self,
        project_id: int,
        repo_id: int,
        area: str | None,
        query_vector: list[float],
        limit: int,
        include_needs_review: bool,
    ) -> list[KnowledgeSearchHit]:
        statuses = [KnowledgeStatus.ACTIVE]
        if include_needs_review:
            statuses.append(KnowledgeStatus.NEEDS_REVIEW)
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.repo_id == repo_id,
            KnowledgeItem.status.in_(statuses),
            KnowledgeItem.embedding.is_not(None),
        )
        if area:
            stmt = stmt.where(KnowledgeItem.area == area)
        scored = []
        for item in self.session.scalars(stmt).all():
            score = cosine_distance(query_vector, item.embedding or [])
            scored.append(KnowledgeSearchHit(item=item, score=score))
        return sorted(scored, key=lambda hit: hit.score if hit.score is not None else 999)[:limit]

    def fallback_search(
        self,
        project_id: int,
        repo_id: int,
        area: str | None,
        query: str,
        limit: int,
        include_needs_review: bool,
    ) -> list[KnowledgeItem]:
        statuses = [KnowledgeStatus.ACTIVE]
        if include_needs_review:
            statuses.append(KnowledgeStatus.NEEDS_REVIEW)
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.repo_id == repo_id,
            KnowledgeItem.status.in_(statuses),
        )
        if area:
            stmt = stmt.where(KnowledgeItem.area == area)
        terms = [term for term in query.lower().split() if len(term) > 2]
        items = self.session.scalars(stmt).all()
        ranked = sorted(
            items,
            key=lambda item: sum(term in f"{item.title} {item.content}".lower() for term in terms),
            reverse=True,
        )
        return ranked[:limit]

    def upsert_item(
        self,
        write: KnowledgeWrite,
        status: KnowledgeStatus,
        actor: str,
        embedding: list[float] | None = None,
    ) -> KnowledgeItem:
        project, repo = self.resolve_scope(write.scope)
        if write.item_id is None:
            item = KnowledgeItem(
                project_id=project.id,
                repo_id=repo.id,
                area=write.scope.area,
                type=write.type,
                status=status,
                title=write.title,
                content=write.content,
                confidence=write.confidence,
                source_type=write.source.source_type,
                source_ref=write.source.source_ref,
                path=write.source.path,
                line_start=write.source.line_start,
                line_end=write.source.line_end,
                commit_sha=write.source.commit_sha,
                content_hash=write.source.content_hash,
                embedding=embedding,
                created_by=actor,
                updated_by=actor,
                version=1,
            )
            self.session.add(item)
            self.session.flush()
        else:
            item = self.get_item(write.item_id)
            self._save_version(item, actor)
            item.area = write.scope.area
            item.type = write.type
            item.status = status
            item.title = write.title
            item.content = write.content
            item.confidence = write.confidence
            item.source_type = write.source.source_type
            item.source_ref = write.source.source_ref
            item.path = write.source.path
            item.line_start = write.source.line_start
            item.line_end = write.source.line_end
            item.commit_sha = write.source.commit_sha
            item.content_hash = write.source.content_hash
            item.embedding = embedding
            item.updated_by = actor
            item.version += 1
        self.session.flush()
        return item

    def set_status(self, item_id: int, status: KnowledgeStatus, actor: str) -> KnowledgeItem:
        item = self.get_item(item_id)
        self._save_version(item, actor)
        item.status = status
        item.updated_by = actor
        item.version += 1
        self.session.flush()
        return item

    def update_embedding(self, item: KnowledgeItem, embedding: list[float], actor: str) -> None:
        self._save_version(item, actor)
        item.embedding = embedding
        item.updated_by = actor
        item.version += 1
        self.session.flush()

    def audit(
        self,
        action: str,
        actor: str,
        role,
        project_id: int | None = None,
        repo_id: int | None = None,
        item_id: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            AuditEvent(
                action=action,
                actor=actor,
                role=role,
                project_id=project_id,
                repo_id=repo_id,
                item_id=item_id,
                detail=detail,
            )
        )
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    def _save_version(self, item: KnowledgeItem, actor: str) -> None:
        self.session.add(
            KnowledgeVersion(
                item_id=item.id,
                version=item.version,
                snapshot=json_safe(item_to_snapshot(item)),
                changed_by=actor,
            )
        )


def item_to_snapshot(item: KnowledgeItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "repo_id": item.repo_id,
        "area": item.area,
        "type": item.type.value,
        "status": item.status.value,
        "title": item.title,
        "content": item.content,
        "confidence": item.confidence,
        "source_type": item.source_type,
        "source_ref": item.source_ref,
        "path": item.path,
        "line_start": item.line_start,
        "line_end": item.line_end,
        "commit_sha": item.commit_sha,
        "content_hash": item.content_hash,
        "embedding": item.embedding,
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "version": item.version,
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(child) for child in value]
    if hasattr(value, "to_list"):
        return json_safe(value.to_list())
    if hasattr(value, "tolist"):
        return json_safe(value.tolist())
    if hasattr(value, "item") and value.__class__.__module__.startswith("numpy"):
        return json_safe(value.item())
    return value


def source_from_item(item: KnowledgeItem) -> KnowledgeSource:
    return KnowledgeSource(
        source_type=item.source_type,
        source_ref=item.source_ref,
        path=item.path,
        line_start=item.line_start,
        line_end=item.line_end,
        commit_sha=item.commit_sha,
        content_hash=item.content_hash,
    )


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.12g}" for value in vector) + "]"


def cosine_distance(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 1.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if not left_norm or not right_norm:
        return 1.0
    return 1.0 - (dot / (left_norm * right_norm))
