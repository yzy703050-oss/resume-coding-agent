from datetime import UTC, datetime

import pytest

from coding_agent.agent.actions import ModelUsage
from coding_agent.context.budget import AuxiliaryBudget
from coding_agent.memory.auxiliary import AuxiliaryModelGateway, RunUsageLedger
from coding_agent.memory.candidates import (
    DeterministicExtractionInput,
    DeterministicProjectMemoryCandidateExtractor,
    LLMStructuredProjectMemoryCandidateExtractor,
    ProjectMemoryCandidate,
    ProjectMemoryType,
)
from coding_agent.memory.promotion import ProjectMemoryPromotionPipeline


def candidate(**changes: object) -> ProjectMemoryCandidate:
    values: dict[str, object] = {
        "candidate_id": "candidate-1",
        "type": ProjectMemoryType.CONVENTION,
        "content": "Use pytest for tests",
        "importance": 0.8,
        "confidence": 0.9,
        "source_run_id": "run-1",
        "source_event_sequences": (2,),
        "related_paths": ("tests/test_app.py",),
        "extraction_method": "deterministic",
    }
    values.update(changes)
    return ProjectMemoryCandidate(**values)  # type: ignore[arg-type]


def test_deterministic_extractor_emits_typed_evidence_candidates_without_store() -> None:
    extractor = DeterministicProjectMemoryCandidateExtractor()
    assert not hasattr(extractor, "store")
    result = extractor.extract(
        DeterministicExtractionInput(
            run_id="run-1",
            summary="Implemented parser",
            summary_event_sequence=4,
            changed_paths=("src/parser.py",),
        )
    )
    assert result[0].type is ProjectMemoryType.RUN_SUMMARY
    assert result[0].source_event_sequences == (4,)


def test_promotion_sanitizes_and_validates_provenance_before_record() -> None:
    pipeline = ProjectMemoryPromotionPipeline(
        project_id="sha256:abc",
        run_id="run-1",
        canonical_event_sequences=frozenset({1, 2}),
        repository_paths=frozenset({"tests/test_app.py"}),
        secrets=("SECRET",),
    )
    record = pipeline.promote(candidate(content="Use SECRET pytest"), datetime.now(UTC))
    assert record is not None
    assert "SECRET" not in record.content
    assert record.normalized_hash

    assert pipeline.promote(candidate(source_event_sequences=(99,)), datetime.now(UTC)) is None
    assert pipeline.promote(candidate(related_paths=("../outside",)), datetime.now(UTC)) is None


def test_store_type_cannot_be_constructed_from_unvalidated_candidate() -> None:
    with pytest.raises(TypeError):
        ProjectMemoryPromotionPipeline.promote(candidate())  # type: ignore[call-arg]


class CandidateClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0

    def complete_json(self, prompt: str) -> tuple[dict[str, object], ModelUsage]:
        del prompt
        self.calls += 1
        return self.payload, ModelUsage(input_tokens=1)


def test_llm_extractor_never_calls_client_when_auxiliary_budget_denies() -> None:
    client = CandidateClient({"candidates": []})
    extractor = LLMStructuredProjectMemoryCandidateExtractor(
        AuxiliaryModelGateway(client, AuxiliaryBudget(0, 0), RunUsageLedger())  # type: ignore[arg-type]
    )
    source = DeterministicExtractionInput("run-1", "summary", 1)

    assert extractor.extract(source) == ()
    assert client.calls == 0


def test_llm_extractor_rejects_malformed_structured_output() -> None:
    client = CandidateClient({"candidates": [{"type": "convention"}]})
    extractor = LLMStructuredProjectMemoryCandidateExtractor(
        AuxiliaryModelGateway(client, AuxiliaryBudget(1, 100), RunUsageLedger())  # type: ignore[arg-type]
    )
    assert extractor.extract(DeterministicExtractionInput("run-1", "summary", 1)) == ()
