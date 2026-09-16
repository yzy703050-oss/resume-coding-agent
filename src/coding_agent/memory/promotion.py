"""Mandatory validation boundary between candidates and persistence."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import uuid4

from coding_agent.memory.candidates import ProjectMemoryCandidate, ProjectMemoryType


@dataclass(frozen=True)
class ValidatedProjectMemoryRecord:
    memory_id: str
    project_id: str
    type: ProjectMemoryType
    content: str
    normalized_hash: str
    importance: float
    confidence: float
    source_run_id: str
    source_event_sequences: tuple[int, ...]
    related_paths: tuple[str, ...]
    created_at: datetime
    last_confirmed_at: datetime


@dataclass(frozen=True)
class CandidateSanitizer:
    secrets: tuple[str, ...] = ()
    max_content_chars: int = 2000

    def sanitize(self, candidate: ProjectMemoryCandidate) -> ProjectMemoryCandidate | None:
        content = candidate.content
        for secret in sorted(self.secrets, key=len, reverse=True):
            if secret:
                content = content.replace(secret, "[REDACTED]")
        content = " ".join(content.split())[: self.max_content_chars]
        return replace(candidate, content=content) if content else None


@dataclass(frozen=True)
class ProjectMemoryPolicy:
    minimum_confidence: float = 0.5

    def accepts(self, candidate: ProjectMemoryCandidate) -> bool:
        return (
            bool(candidate.content)
            and candidate.source_event_sequences != ()
            and 0 <= candidate.importance <= 1
            and self.minimum_confidence <= candidate.confidence <= 1
        )


@dataclass(frozen=True)
class ProvenanceValidator:
    run_id: str
    canonical_event_sequences: frozenset[int]
    repository_paths: frozenset[str]

    def accepts(self, candidate: ProjectMemoryCandidate) -> bool:
        return (
            candidate.source_run_id == self.run_id
            and set(candidate.source_event_sequences).issubset(self.canonical_event_sequences)
            and set(candidate.related_paths).issubset(self.repository_paths)
        )


class CandidateNormalizer:
    def normalize(self, content: str) -> tuple[str, str]:
        normalized = re.sub(r"\s+", " ", content.casefold()).strip()
        return content, hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class ProjectMemoryDeduplicator:
    seen: set[tuple[ProjectMemoryType, str]] = field(default_factory=set)

    def accept(self, memory_type: ProjectMemoryType, normalized_hash: str) -> bool:
        key = (memory_type, normalized_hash)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


@dataclass
class ProjectMemoryPromotionPipeline:
    project_id: str
    run_id: str
    canonical_event_sequences: frozenset[int]
    repository_paths: frozenset[str]
    secrets: tuple[str, ...] = ()
    max_content_chars: int = 2000
    minimum_confidence: float = 0.5
    deduplicator: ProjectMemoryDeduplicator = field(default_factory=ProjectMemoryDeduplicator)

    def promote(
        self, candidate: ProjectMemoryCandidate, now: datetime
    ) -> ValidatedProjectMemoryRecord | None:
        sanitized = CandidateSanitizer(self.secrets, self.max_content_chars).sanitize(candidate)
        if sanitized is None or not ProjectMemoryPolicy(self.minimum_confidence).accepts(sanitized):
            return None
        provenance = ProvenanceValidator(
            self.run_id, self.canonical_event_sequences, self.repository_paths
        )
        if not provenance.accepts(sanitized):
            return None
        content, normalized_hash = CandidateNormalizer().normalize(sanitized.content)
        if not self.deduplicator.accept(sanitized.type, normalized_hash):
            return None
        return ValidatedProjectMemoryRecord(
            memory_id=str(uuid4()),
            project_id=self.project_id,
            type=sanitized.type,
            content=content,
            normalized_hash=normalized_hash,
            importance=sanitized.importance,
            confidence=sanitized.confidence,
            source_run_id=sanitized.source_run_id,
            source_event_sequences=sanitized.source_event_sequences,
            related_paths=sanitized.related_paths,
            created_at=now,
            last_confirmed_at=now,
        )
