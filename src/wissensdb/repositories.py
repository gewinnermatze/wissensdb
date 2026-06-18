from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wissensdb.enums import KnowledgeStatus
from wissensdb.models import AuditEvent, KnowledgeItem, KnowledgeVersion, Project, Repo
from wissensdb.schemas import KnowledgeSource, KnowledgeWrite, Scope


class ScopeError(ValueError):
    pass


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
                snapshot=item_to_snapshot(item),
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
        "created_by": item.created_by,
        "updated_by": item.updated_by,
        "version": item.version,
    }


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
