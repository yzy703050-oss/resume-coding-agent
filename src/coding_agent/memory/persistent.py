"""Versioned SQLite persistence for validated project memory."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from coding_agent.memory.candidates import ProjectMemoryType
from coding_agent.memory.promotion import ValidatedProjectMemoryRecord


@dataclass(frozen=True)
class StoredProjectMemoryRecord:
    memory_id: str
    project_id: str
    type: ProjectMemoryType
    content: str
    importance: float
    confidence: float
    source_run_ids: tuple[str, ...]
    source_event_sequences: tuple[int, ...]
    related_paths: tuple[str, ...]
    created_at: datetime
    last_confirmed_at: datetime
    score: float


class ProjectMemoryStore:
    def __init__(
        self,
        path: Path,
        *,
        timeout_seconds: float = 0.2,
        max_active_records: int = 500,
        max_active_per_type: int = 100,
        enable_fts: bool = True,
    ) -> None:
        if max_active_records < 1 or max_active_per_type < 1:
            raise ValueError("project-memory limits must be positive")
        self.path = path
        self.max_active_records = max_active_records
        self.max_active_per_type = max_active_per_type
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=timeout_seconds)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_memory (
                memory_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                normalized_hash TEXT NOT NULL,
                importance REAL NOT NULL,
                confidence REAL NOT NULL,
                source_run_ids TEXT NOT NULL,
                source_event_sequences TEXT NOT NULL,
                related_paths TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_confirmed_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                UNIQUE(project_id, type, normalized_hash)
            )
            """
        )
        self.connection.execute("PRAGMA user_version = 1")
        self.fts_enabled = False
        if enable_fts:
            try:
                self.connection.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS project_memory_fts "
                    "USING fts5(memory_id UNINDEXED, project_id UNINDEXED, content)"
                )
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False
        self.connection.commit()

    @property
    def schema_version(self) -> int:
        row = self.connection.execute("PRAGMA user_version").fetchone()
        return int(row[0])

    def upsert_validated(self, record: ValidatedProjectMemoryRecord) -> None:
        if not isinstance(record, ValidatedProjectMemoryRecord):
            raise TypeError("store accepts only ValidatedProjectMemoryRecord")
        existing = self.connection.execute(
            "SELECT memory_id, source_run_ids FROM project_memory "
            "WHERE project_id=? AND type=? AND normalized_hash=?",
            (record.project_id, record.type.value, record.normalized_hash),
        ).fetchone()
        if existing:
            runs = set(json.loads(existing[1]))
            runs.add(record.source_run_id)
            self.connection.execute(
                "UPDATE project_memory SET source_run_ids=?, last_confirmed_at=?, "
                "importance=max(importance, ?), confidence=max(confidence, ?) "
                "WHERE memory_id=?",
                (
                    json.dumps(sorted(runs)),
                    record.last_confirmed_at.isoformat(),
                    record.importance,
                    record.confidence,
                    existing[0],
                ),
            )
        else:
            self.connection.execute(
                "INSERT INTO project_memory VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')",
                (
                    record.memory_id,
                    record.project_id,
                    record.type.value,
                    record.content,
                    record.normalized_hash,
                    record.importance,
                    record.confidence,
                    json.dumps([record.source_run_id]),
                    json.dumps(record.source_event_sequences),
                    json.dumps(record.related_paths),
                    record.created_at.isoformat(),
                    record.last_confirmed_at.isoformat(),
                ),
            )
            if self.fts_enabled:
                self.connection.execute(
                    "INSERT INTO project_memory_fts(memory_id, project_id, content) "
                    "VALUES (?, ?, ?)",
                    (record.memory_id, record.project_id, record.content),
                )
        self.connection.commit()
        self._enforce_limits(record.project_id, record.type)

    def query(
        self, project_id: str, query: str, *, limit: int
    ) -> tuple[StoredProjectMemoryRecord, ...]:
        terms = {term.casefold() for term in query.split() if term}
        fts_matches: set[str] = set()
        if self.fts_enabled and terms:
            expression = " OR ".join(
                f'"{term}"' for term in sorted(terms) if re.fullmatch(r"[\w.-]+", term)
            )
            if expression:
                try:
                    fts_matches = {
                        row[0]
                        for row in self.connection.execute(
                            "SELECT memory_id FROM project_memory_fts "
                            "WHERE project_memory_fts MATCH ? AND project_id=?",
                            (expression, project_id),
                        ).fetchall()
                    }
                except sqlite3.OperationalError:
                    self.fts_enabled = False
        rows = self.connection.execute(
            "SELECT memory_id, project_id, type, content, importance, confidence, "
            "source_run_ids, source_event_sequences, related_paths, created_at, "
            "last_confirmed_at FROM project_memory WHERE project_id=? AND status='active'",
            (project_id,),
        ).fetchall()
        results: list[StoredProjectMemoryRecord] = []
        for row in rows:
            keyword = sum(term in row[3].casefold() for term in terms)
            score = float(keyword) + float(row[4]) + float(row[5])
            if row[0] in fts_matches:
                score += 1.0
            results.append(
                StoredProjectMemoryRecord(
                    memory_id=row[0],
                    project_id=row[1],
                    type=ProjectMemoryType(row[2]),
                    content=row[3],
                    importance=row[4],
                    confidence=row[5],
                    source_run_ids=tuple(json.loads(row[6])),
                    source_event_sequences=tuple(json.loads(row[7])),
                    related_paths=tuple(json.loads(row[8])),
                    created_at=datetime.fromisoformat(row[9]),
                    last_confirmed_at=datetime.fromisoformat(row[10]),
                    score=score,
                )
            )
        results.sort(key=lambda item: (-item.score, item.memory_id))
        return tuple(results[: max(0, limit)])

    def close(self) -> None:
        self.connection.close()

    def _enforce_limits(self, project_id: str, memory_type: ProjectMemoryType) -> None:
        self._retain_best(
            "project_id=? AND type=? AND status='active'",
            (project_id, memory_type.value),
            self.max_active_per_type,
        )
        self._retain_best(
            "project_id=? AND status='active'", (project_id,), self.max_active_records
        )
        self.connection.commit()

    def _retain_best(self, where: str, parameters: tuple[str, ...], limit: int) -> None:
        rows = self.connection.execute(
            "SELECT memory_id FROM project_memory WHERE "
            + where
            + " ORDER BY importance DESC, confidence DESC, last_confirmed_at DESC, memory_id ASC",
            parameters,
        ).fetchall()
        stale = rows[limit:]
        if stale:
            self.connection.executemany(
                "UPDATE project_memory SET status='superseded' WHERE memory_id=?", stale
            )
