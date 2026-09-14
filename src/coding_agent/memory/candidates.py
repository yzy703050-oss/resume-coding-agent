"""Store-independent project-memory candidate extraction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol
from uuid import uuid4

from coding_agent.memory.auxiliary import AuxiliaryBudgetExceeded, AuxiliaryModelGateway


class ProjectMemoryType(StrEnum):
    ARCHITECTURE = "architecture"
    CONVENTION = "convention"
    IMPORTANT_MODULE = "important_module"
    TESTING = "testing"
    KNOWN_FAILURE = "known_failure"
    PAST_ATTEMPT = "past_attempt"
    DECISION = "decision"
    USEFUL_COMMAND = "useful_command"
    RUN_SUMMARY = "run_summary"


@dataclass(frozen=True)
class ProjectMemoryCandidate:
    candidate_id: str
    type: ProjectMemoryType
    content: str
    importance: float
    confidence: float
    source_run_id: str
    source_event_sequences: tuple[int, ...]
    related_paths: tuple[str, ...]
    extraction_method: Literal["deterministic", "llm_structured"]


@dataclass(frozen=True)
class DeterministicExtractionInput:
    run_id: str
    summary: str
    summary_event_sequence: int
    changed_paths: tuple[str, ...] = ()


class ProjectMemoryCandidateExtractor(Protocol):
    def extract(
        self, source: DeterministicExtractionInput
    ) -> tuple[ProjectMemoryCandidate, ...]: ...


class NoOpProjectMemoryCandidateExtractor:
    def extract(self, source: DeterministicExtractionInput) -> tuple[ProjectMemoryCandidate, ...]:
        del source
        return ()


class DeterministicProjectMemoryCandidateExtractor:
    def extract(self, source: DeterministicExtractionInput) -> tuple[ProjectMemoryCandidate, ...]:
        if not source.summary.strip():
            return ()
        return (
            ProjectMemoryCandidate(
                candidate_id=str(uuid4()),
                type=ProjectMemoryType.RUN_SUMMARY,
                content=source.summary.strip(),
                importance=0.5,
                confidence=1.0,
                source_run_id=source.run_id,
                source_event_sequences=(source.summary_event_sequence,),
                related_paths=source.changed_paths,
                extraction_method="deterministic",
            ),
        )


@dataclass(frozen=True)
class LLMStructuredProjectMemoryCandidateExtractor:
    gateway: AuxiliaryModelGateway

    def extract(self, source: DeterministicExtractionInput) -> tuple[ProjectMemoryCandidate, ...]:
        prompt = (
            "Return JSON candidates with type, content, importance, confidence, "
            "source_event_sequences, and related_paths for this run:\n" + source.summary
        )
        try:
            payload = self.gateway.complete_json(
                "memory_candidate_extractor",
                prompt,
                estimated_tokens=max(1, len(prompt) // 4),
            )
            raw_candidates = payload.get("candidates")
            if not isinstance(raw_candidates, list):
                return ()
            result: list[ProjectMemoryCandidate] = []
            for item in raw_candidates:
                if not isinstance(item, dict):
                    return ()
                sequences = item.get("source_event_sequences")
                paths = item.get("related_paths", [])
                if not isinstance(sequences, list) or not isinstance(paths, list):
                    return ()
                importance = item["importance"]
                confidence = item["confidence"]
                if not isinstance(importance, int | float) or isinstance(importance, bool):
                    return ()
                if not isinstance(confidence, int | float) or isinstance(confidence, bool):
                    return ()
                typed_sequences: list[int] = []
                for value in sequences:
                    if not isinstance(value, int) or isinstance(value, bool):
                        return ()
                    typed_sequences.append(value)
                result.append(
                    ProjectMemoryCandidate(
                        candidate_id=str(uuid4()),
                        type=ProjectMemoryType(str(item["type"])),
                        content=str(item["content"]),
                        importance=float(importance),
                        confidence=float(confidence),
                        source_run_id=source.run_id,
                        source_event_sequences=tuple(typed_sequences),
                        related_paths=tuple(str(value) for value in paths),
                        extraction_method="llm_structured",
                    )
                )
            return tuple(result)
        except (AuxiliaryBudgetExceeded, KeyError, TypeError, ValueError, RuntimeError):
            return ()
