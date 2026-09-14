"""Inspectable retrieval facade with an optional semantic-scoring extension seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from coding_agent.memory.persistent import ProjectMemoryStore, StoredProjectMemoryRecord


class SemanticMemoryScorer(Protocol):
    def score(self, query: str, record: StoredProjectMemoryRecord) -> float: ...


@dataclass(frozen=True)
class ProjectMemoryRetriever:
    store: ProjectMemoryStore
    semantic_scorer: SemanticMemoryScorer | None = None

    def retrieve(
        self, project_id: str, query: str, *, limit: int
    ) -> tuple[StoredProjectMemoryRecord, ...]:
        candidates = list(self.store.query(project_id, query, limit=max(limit * 3, limit)))
        scorer = self.semantic_scorer
        if scorer is not None:
            candidates.sort(
                key=lambda item: (
                    -(item.score + scorer.score(query, item)),
                    item.memory_id,
                )
            )
        return tuple(candidates[: max(0, limit)])
