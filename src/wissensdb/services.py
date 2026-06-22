from sqlalchemy.exc import IntegrityError

from wissensdb.auth import AgentIdentity
from wissensdb.embeddings import EmbeddingProvider
from wissensdb.enums import HIGH_RISK_TYPES, AgentRole, KnowledgeStatus
from wissensdb.models import KnowledgeItem
from wissensdb.repositories import KnowledgeRepository, source_from_item
from wissensdb.schemas import KnowledgeOut, KnowledgeWrite, QueryRequest, QueryResponse, Scope


class GuardrailError(ValueError):
    pass


class KnowledgeService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embeddings: EmbeddingProvider,
    ) -> None:
        self.repository = repository
        self.embeddings = embeddings

    def create_project(self, slug: str, name: str, description: str | None = None):
        try:
            return self.repository.create_project(slug, name, description)
        except IntegrityError as exc:
            raise GuardrailError(f"project already exists: {slug}") from exc

    def create_repo(
        self,
        project_slug: str,
        slug: str,
        name: str,
        path: str | None = None,
        default_area: str | None = None,
    ):
        try:
            return self.repository.create_repo(project_slug, slug, name, path, default_area)
        except IntegrityError as exc:
            raise GuardrailError(f"repo already exists in project {project_slug}: {slug}") from exc

    def query(self, request: QueryRequest, agent: AgentIdentity) -> QueryResponse:
        agent.require(AgentRole.READER)
        scope = Scope(project=request.project, repo=request.repo, area=request.area)
        project, repo = self.repository.resolve_scope(scope)
        query_vector = self.embeddings.embed(request.query)
        vector_hits = self.repository.vector_search(
            project.id,
            repo.id,
            request.area,
            query_vector,
            request.limit,
            include_needs_review=request.include_needs_review,
        )
        if vector_hits:
            items = [hit.item for hit in vector_hits]
            score_by_id = {hit.item.id: hit.score for hit in vector_hits}
        else:
            items = self.repository.fallback_search(
                project.id,
                repo.id,
                request.area,
                request.query,
                request.limit,
                request.include_needs_review,
            )
            score_by_id = {}
        knowledge = [item_to_out(item, request.project, request.repo) for item in items]
        self.repository.audit(
            "knowledge.query",
            agent.agent_id,
            agent.role,
            project_id=project.id,
            repo_id=repo.id,
            detail={"query": request.query, "hits": len(knowledge)},
        )
        self.repository.commit()
        return QueryResponse(
            scope=scope,
            hits=[{"item": item, "score": score_by_id.get(item.id)} for item in knowledge],
            context=render_context(knowledge, request.token_budget),
        )

    def write(self, write: KnowledgeWrite, agent: AgentIdentity) -> KnowledgeOut:
        agent.require(AgentRole.CONTRIBUTOR)
        status = choose_status(write, agent)
        project, repo = self.repository.resolve_scope(write.scope)
        embedding = self.embeddings.embed(f"{write.title}\n\n{write.content}")
        item = self.repository.upsert_item(write, status, actor=agent.agent_id, embedding=embedding)
        self.repository.audit(
            "knowledge.upsert",
            agent.agent_id,
            agent.role,
            project_id=project.id,
            repo_id=repo.id,
            item_id=item.id,
            detail={"status": status.value, "confidence": write.confidence},
        )
        self.repository.commit()
        return item_to_out(item, write.scope.project, write.scope.repo)

    def mark_stale(self, item_id: int, agent: AgentIdentity) -> KnowledgeOut:
        agent.require(AgentRole.CONTRIBUTOR)
        item = self.repository.set_status(item_id, KnowledgeStatus.STALE, agent.agent_id)
        project_slug, repo_slug = self.repository.get_scope_slugs(item.project_id, item.repo_id)
        self.repository.audit(
            "knowledge.mark_stale",
            agent.agent_id,
            agent.role,
            project_id=item.project_id,
            repo_id=item.repo_id,
            item_id=item.id,
        )
        self.repository.commit()
        return item_to_out(item, project_slug=project_slug, repo_slug=repo_slug)

    def archive(self, item_id: int, agent: AgentIdentity) -> KnowledgeOut:
        agent.require(AgentRole.MAINTAINER)
        item = self.repository.set_status(item_id, KnowledgeStatus.ARCHIVED, agent.agent_id)
        project_slug, repo_slug = self.repository.get_scope_slugs(item.project_id, item.repo_id)
        self.repository.audit(
            "knowledge.archive",
            agent.agent_id,
            agent.role,
            project_id=item.project_id,
            repo_id=item.repo_id,
            item_id=item.id,
        )
        self.repository.commit()
        return item_to_out(item, project_slug=project_slug, repo_slug=repo_slug)


def choose_status(write: KnowledgeWrite, agent: AgentIdentity) -> KnowledgeStatus:
    if not write.scope.project or not write.scope.repo:
        raise GuardrailError("writes require explicit project and repo scope")
    if not write.source.source_type or not write.source.source_ref:
        raise GuardrailError("writes require source_type and source_ref")
    if write.confidence < 0.45:
        return KnowledgeStatus.NEEDS_REVIEW
    if write.type in HIGH_RISK_TYPES and agent.role != AgentRole.MAINTAINER:
        return KnowledgeStatus.NEEDS_REVIEW
    return KnowledgeStatus.ACTIVE


def item_to_out(item: KnowledgeItem, project_slug: str, repo_slug: str) -> KnowledgeOut:
    return KnowledgeOut(
        id=item.id,
        scope=Scope(
            project=project_slug or str(item.project_id),
            repo=repo_slug or str(item.repo_id),
            area=item.area,
        ),
        type=item.type,
        status=item.status,
        title=item.title,
        content=item.content,
        confidence=item.confidence,
        source=source_from_item(item),
        created_by=item.created_by,
        updated_by=item.updated_by,
        version=item.version,
    )


def render_context(items: list[KnowledgeOut], token_budget: int) -> str:
    char_budget = token_budget * 4
    blocks: list[str] = []
    used = 0
    for item in items:
        source = item.source.path or item.source.source_ref
        lines = ""
        if item.source.line_start:
            lines = f":{item.source.line_start}"
            if item.source.line_end and item.source.line_end != item.source.line_start:
                lines += f"-{item.source.line_end}"
        block = (
            f"[{item.type.value} #{item.id} {item.status.value} confidence={item.confidence:.2f}]\n"
            f"Title: {item.title}\n"
            f"Source: {source}{lines}\n"
            f"{item.content.strip()}\n"
        )
        if used + len(block) > char_budget:
            break
        blocks.append(block)
        used += len(block)
    return "\n---\n".join(blocks)
