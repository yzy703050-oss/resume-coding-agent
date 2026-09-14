import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from coding_agent.memory.candidates import ProjectMemoryType
from coding_agent.memory.persistent import ProjectMemoryStore, StoredProjectMemoryRecord
from coding_agent.memory.promotion import ValidatedProjectMemoryRecord
from coding_agent.memory.retrieval import ProjectMemoryRetriever


def record(
    project: str, run: str = "run-1", normalized_hash: str = "hash-1", content: str = "Use pytest"
) -> ValidatedProjectMemoryRecord:
    now = datetime.now(UTC)
    return ValidatedProjectMemoryRecord(
        memory_id=f"{project}-{run}-{normalized_hash}",
        project_id=project,
        type=ProjectMemoryType.CONVENTION,
        content=content,
        normalized_hash=normalized_hash,
        importance=0.8,
        confidence=0.9,
        source_run_id=run,
        source_event_sequences=(2,),
        related_paths=("tests/test_app.py",),
        created_at=now,
        last_confirmed_at=now,
    )


def test_store_is_versioned_isolated_and_reconfirms_duplicates(tmp_path: Path) -> None:
    store = ProjectMemoryStore(tmp_path / "memory.sqlite3")
    store.upsert_validated(record("project-a"))
    store.upsert_validated(record("project-a", "run-2"))
    store.upsert_validated(record("project-b"))

    results = store.query("project-a", "pytest", limit=10)
    assert store.schema_version == 1
    assert len(results) == 1
    assert set(results[0].source_run_ids) == {"run-1", "run-2"}
    assert all(item.project_id == "project-a" for item in results)


def test_store_rejects_raw_values(tmp_path: Path) -> None:
    store = ProjectMemoryStore(tmp_path / "memory.sqlite3")
    with pytest.raises(TypeError):
        store.upsert_validated("raw candidate")  # type: ignore[arg-type]


def test_store_enforces_limits_and_retriever_has_semantic_extension_seam(tmp_path: Path) -> None:
    store = ProjectMemoryStore(tmp_path / "memory.sqlite3", max_active_per_type=2)
    store.upsert_validated(record("project", normalized_hash="one", content="alpha"))
    store.upsert_validated(record("project", normalized_hash="two", content="beta"))
    store.upsert_validated(record("project", normalized_hash="three", content="gamma"))

    class PreferBeta:
        def score(self, query: str, value: StoredProjectMemoryRecord) -> float:
            del query
            return 100.0 if value.content == "beta" else 0.0

    assert len(store.query("project", "", limit=5)) == 2
    results = ProjectMemoryRetriever(store, PreferBeta()).retrieve("project", "", limit=1)
    assert results[0].content == "beta"


def test_keyword_fallback_works_when_fts_is_disabled(tmp_path: Path) -> None:
    store = ProjectMemoryStore(tmp_path / "memory.sqlite3", enable_fts=False)
    store.upsert_validated(record("project", content="pytest convention"))

    assert not store.fts_enabled
    assert store.query("project", "pytest", limit=1)[0].content == "pytest convention"


def test_locked_store_fails_quickly_for_runtime_degradation(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    ProjectMemoryStore(path).close()
    locker = sqlite3.connect(path)
    locker.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            ProjectMemoryStore(path, timeout_seconds=0.01)
    finally:
        locker.rollback()
        locker.close()
