from pathlib import Path

import pytest

from coding_agent.tools.files import list_files, read_file, search_code


def test_list_files_is_sorted_limited_and_excludes_git(tmp_path: Path) -> None:
    (tmp_path / "b.py").write_text("b", encoding="utf-8")
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("hidden", encoding="utf-8")
    result = list_files(tmp_path, max_results=1)
    assert result.ok
    assert result.data == {"paths": ["a.py"], "omitted": 1}
    assert result.truncated


def test_search_is_sorted_limited_and_reports_truncation(tmp_path: Path) -> None:
    (tmp_path / "b.py").write_text("needle = 2\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("needle = 1\n", encoding="utf-8")
    result = search_code(tmp_path, query="needle", max_results=1)
    assert result.ok
    matches = result.data["matches"]
    assert isinstance(matches, list)
    assert matches[0] == {"path": "a.py", "line": 1, "text": "needle = 1"}
    assert result.data["omitted"] == 1
    assert result.truncated


def test_search_honors_path_and_glob(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("needle\n", encoding="utf-8")
    (tmp_path / "src" / "a.txt").write_text("needle\n", encoding="utf-8")
    result = search_code(tmp_path, "needle", path="src", glob="*.py")
    assert result.data["matches"] == [{"path": "src/a.py", "line": 1, "text": "needle"}]


def test_read_file_slices_lines_and_truncates(tmp_path: Path) -> None:
    (tmp_path / "hello.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    result = read_file(tmp_path, "hello.py", start_line=2, end_line=3, max_chars=5)
    assert result.ok
    assert result.data["content"] == "two\n"
    assert result.data["start_line"] == 2
    assert result.truncated


def test_read_file_normalizes_utf8_error(tmp_path: Path) -> None:
    (tmp_path / "binary.bin").write_bytes(b"\xff\xfe")
    result = read_file(tmp_path, "binary.bin")
    assert not result.ok
    assert result.error_code == "decode_error"


def test_search_rejects_symlinked_file_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.py"
    outside.write_text("secret_marker = 1\n", encoding="utf-8")
    try:
        (tmp_path / "linked.py").symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    result = search_code(tmp_path, "secret_marker")

    assert not result.ok
    assert result.error_code == "path_policy"
    assert "secret_marker" not in str(result.data)
