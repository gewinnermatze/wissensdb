from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class VectorHit:
    item_id: int
    score: float


class VectorStore(Protocol):
    def upsert(self, item_id: int, vector: list[float], payload: dict[str, Any]) -> None: ...

    def search(
        self,
        vector: list[float],
        scope_filter: dict[str, Any],
        limit: int,
        include_needs_review: bool = False,
    ) -> list[VectorHit]: ...

    def delete(self, item_id: int) -> None: ...


class NullVectorStore:
    def upsert(self, item_id: int, vector: list[float], payload: dict[str, Any]) -> None:
        return None

    def search(
        self,
        vector: list[float],
        scope_filter: dict[str, Any],
        limit: int,
        include_needs_review: bool = False,
    ) -> list[VectorHit]:
        return []

    def delete(self, item_id: int) -> None:
        return None


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.points: dict[int, tuple[list[float], dict[str, Any]]] = {}

    def upsert(self, item_id: int, vector: list[float], payload: dict[str, Any]) -> None:
        self.points[item_id] = (vector, payload)

    def search(
        self,
        vector: list[float],
        scope_filter: dict[str, Any],
        limit: int,
        include_needs_review: bool = False,
    ) -> list[VectorHit]:
        hits: list[VectorHit] = []
        for item_id, (stored, payload) in self.points.items():
            if not _matches_scope(payload, scope_filter):
                continue
            if payload.get("status") == "needs_review" and not include_needs_review:
                continue
            score = sum(a * b for a, b in zip(vector, stored, strict=False))
            hits.append(VectorHit(item_id=item_id, score=score))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]

    def delete(self, item_id: int) -> None:
        self.points.pop(item_id, None)


def _matches_scope(payload: dict[str, Any], scope_filter: dict[str, Any]) -> bool:
    for key, value in scope_filter.items():
        if value is None:
            continue
        if payload.get(key) != value:
            return False
    return True
