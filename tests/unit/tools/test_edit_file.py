from pathlib import Path

from coding_agent.tools.files import edit_file


def test_replace_requires_one_exact_match(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("x = 1\nx = 1\n", encoding="utf-8")
    result = edit_file(
        tmp_path,
        "app.py",
        operation="replace",
        expected_text="x = 1",
        new_text="x = 2",
    )
    assert not result.ok
    assert result.error_code == "edit_conflict"
    assert path.read_text(encoding="utf-8") == "x = 1\nx = 1\n"


def test_replace_writes_unique_utf8_match(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text("message = '旧'\n", encoding="utf-8")
    result = edit_file(
        tmp_path,
        "app.py",
        operation="replace",
        expected_text="旧",
        new_text="新",
    )
    assert result.ok
    assert result.data["path"] == "app.py"
    assert path.read_text(encoding="utf-8") == "message = '新'\n"


def test_create_refuses_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "new.py"
    path.write_text("old", encoding="utf-8")
    result = edit_file(tmp_path, "new.py", operation="create", new_text="new")
    assert not result.ok
    assert result.error_code == "edit_conflict"
    assert path.read_text(encoding="utf-8") == "old"


def test_create_makes_parent_directories(tmp_path: Path) -> None:
    result = edit_file(tmp_path, "pkg/new.py", operation="create", new_text="answer = 42\n")
    assert result.ok
    assert (tmp_path / "pkg" / "new.py").read_text(encoding="utf-8") == "answer = 42\n"
