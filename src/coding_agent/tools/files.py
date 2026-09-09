"""Bounded, deterministic file inspection."""

from __future__ import annotations

import os
import tempfile
from fnmatch import fnmatch
from pathlib import Path
from typing import cast

from coding_agent.agent.actions import JsonValue, Observation
from coding_agent.tools.paths import PathPolicyError, resolve_confined


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root.resolve()).as_posix()


def _files(root: Path, start: Path, pattern: str | None = None) -> list[Path]:
    if start.is_file():
        candidates = [start]
    elif start.is_dir():
        candidates = [item for item in start.rglob("*") if item.is_file()]
    else:
        return []
    result = []
    for candidate in candidates:
        relative = candidate.relative_to(root.resolve())
        if ".git" in relative.parts:
            continue
        if pattern is not None and not fnmatch(candidate.name, pattern):
            continue
        result.append(candidate)
    return sorted(result, key=lambda item: _relative(root, item))


def list_files(
    repo_root: Path,
    path: str = ".",
    pattern: str | None = None,
    max_results: int = 200,
) -> Observation:
    if max_results < 1:
        return Observation(
            tool="list_files",
            ok=False,
            summary="invalid result limit",
            data={},
            error_code="invalid_arguments",
        )
    try:
        start = resolve_confined(repo_root, path)
        paths = [_relative(repo_root, item) for item in _files(repo_root, start, pattern)]
    except PathPolicyError as error:
        return Observation(
            tool="list_files", ok=False, summary=str(error), data={}, error_code="path_policy"
        )
    selected = paths[:max_results]
    omitted = len(paths) - len(selected)
    data: dict[str, JsonValue] = {
        "paths": cast(list[JsonValue], selected),
        "omitted": omitted,
    }
    return Observation(
        tool="list_files",
        ok=True,
        summary=f"listed {len(selected)} files",
        data=data,
        truncated=omitted > 0,
    )


def search_code(
    repo_root: Path,
    query: str,
    path: str = ".",
    glob: str | None = None,
    max_results: int = 100,
) -> Observation:
    if not query or max_results < 1:
        return Observation(
            tool="search_code",
            ok=False,
            summary="invalid search arguments",
            data={},
            error_code="invalid_arguments",
        )
    try:
        start = resolve_confined(repo_root, path)
        files = _files(repo_root, start, glob)
    except PathPolicyError as error:
        return Observation(
            tool="search_code", ok=False, summary=str(error), data={}, error_code="path_policy"
        )
    matches: list[JsonValue] = []
    for file_path in files:
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, start=1):
            if query in line:
                matches.append(
                    {"path": _relative(repo_root, file_path), "line": number, "text": line[:500]}
                )
    selected = matches[:max_results]
    omitted = len(matches) - len(selected)
    return Observation(
        tool="search_code",
        ok=True,
        summary=f"found {len(selected)} matches",
        data={"matches": selected, "omitted": omitted},
        truncated=omitted > 0,
    )


def read_file(
    repo_root: Path,
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    max_chars: int = 20_000,
) -> Observation:
    if start_line < 1 or (end_line is not None and end_line < start_line) or max_chars < 1:
        return Observation(
            tool="read_file",
            ok=False,
            summary="invalid read arguments",
            data={},
            error_code="invalid_arguments",
        )
    try:
        file_path = resolve_confined(repo_root, path)
        text = file_path.read_text(encoding="utf-8")
    except PathPolicyError as error:
        return Observation(
            tool="read_file", ok=False, summary=str(error), data={}, error_code="path_policy"
        )
    except UnicodeDecodeError:
        return Observation(
            tool="read_file",
            ok=False,
            summary="file is not UTF-8",
            data={},
            error_code="decode_error",
        )
    except OSError as error:
        return Observation(
            tool="read_file", ok=False, summary=str(error), data={}, error_code="file_error"
        )

    lines = text.splitlines(keepends=True)[start_line - 1 : end_line]
    selected: list[str] = []
    used = 0
    truncated = False
    for line in lines:
        if used + len(line) > max_chars:
            truncated = True
            break
        selected.append(line)
        used += len(line)
    if len(selected) < len(lines):
        truncated = True
    content = "".join(selected)
    return Observation(
        tool="read_file",
        ok=True,
        summary=f"read {_relative(repo_root, file_path)}",
        data={
            "path": _relative(repo_root, file_path),
            "content": content,
            "start_line": start_line,
            "end_line": start_line + len(selected) - 1,
        },
        truncated=truncated,
    )


def edit_file(
    repo_root: Path,
    path: str,
    operation: str,
    new_text: str,
    expected_text: str | None = None,
) -> Observation:
    try:
        file_path = resolve_confined(repo_root, path)
    except PathPolicyError as error:
        return Observation(
            tool="edit_file", ok=False, summary=str(error), data={}, error_code="path_policy"
        )
    if operation == "create":
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(new_text)
        except FileExistsError:
            return Observation(
                tool="edit_file",
                ok=False,
                summary="target already exists",
                data={},
                error_code="edit_conflict",
            )
        except OSError as error:
            return Observation(
                tool="edit_file", ok=False, summary=str(error), data={}, error_code="file_error"
            )
    elif operation == "replace":
        if not expected_text:
            return Observation(
                tool="edit_file",
                ok=False,
                summary="replace requires expected_text",
                data={},
                error_code="invalid_arguments",
            )
        try:
            original = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return Observation(
                tool="edit_file", ok=False, summary=str(error), data={}, error_code="file_error"
            )
        if original.count(expected_text) != 1:
            return Observation(
                tool="edit_file",
                ok=False,
                summary="expected_text must match exactly once",
                data={},
                error_code="edit_conflict",
            )
        replacement = original.replace(expected_text, new_text, 1)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", dir=file_path.parent, delete=False
            ) as temporary:
                temporary.write(replacement)
                temporary_name = temporary.name
            os.replace(temporary_name, file_path)
        except OSError as error:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
            return Observation(
                tool="edit_file", ok=False, summary=str(error), data={}, error_code="file_error"
            )
    else:
        return Observation(
            tool="edit_file",
            ok=False,
            summary="operation must be replace or create",
            data={},
            error_code="invalid_arguments",
        )
    relative = _relative(repo_root, file_path)
    return Observation(
        tool="edit_file", ok=True, summary=f"edited {relative}", data={"path": relative}
    )
