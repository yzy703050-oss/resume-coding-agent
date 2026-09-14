from pathlib import Path

from coding_agent.repository.repomap import PythonRepoMap


def test_builds_deterministic_symbols_and_survives_parse_errors(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        "import os\nfrom pathlib import Path\n\n"
        "class Greeter:\n    def hello(self, name: str = 'world') -> str:\n"
        "        return name\n\ndef helper(value: int) -> int:\n    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "broken.py").write_text("def nope(:\n", encoding="utf-8")

    repo_map = PythonRepoMap(tmp_path)
    repo_map.build()

    rendered = repo_map.render(repo_map.select("Greeter hello", limit=10), max_chars=1000)
    assert "good.py: class Greeter" in rendered
    assert "good.py: method Greeter.hello(name: str='world') -> str" in rendered
    assert any(item.path == "broken.py" for item in repo_map.diagnostics)
    assert repo_map.symbols == tuple(sorted(repo_map.symbols, key=lambda item: item.sort_key))


def test_refresh_replaces_only_the_target_files_symbols(tmp_path: Path) -> None:
    target = tmp_path / "target.py"
    stable = tmp_path / "stable.py"
    target.write_text("def before():\n    pass\n", encoding="utf-8")
    stable.write_text("class Stable:\n    pass\n", encoding="utf-8")
    repo_map = PythonRepoMap(tmp_path)
    repo_map.build()
    stable_symbols = tuple(item for item in repo_map.symbols if item.path == "stable.py")

    target.write_text("def after(value: str):\n    pass\n", encoding="utf-8")
    repo_map.invalidate(target)
    repo_map.refresh()

    assert not any(item.name == "before" for item in repo_map.symbols)
    assert any(item.name == "after" for item in repo_map.symbols)
    assert tuple(item for item in repo_map.symbols if item.path == "stable.py") == stable_symbols


def test_confines_refresh_and_budgeted_rendering(tmp_path: Path) -> None:
    (tmp_path / "module.py").write_text(
        "def alpha():\n    pass\n\ndef beta():\n    pass\n", encoding="utf-8"
    )
    repo_map = PythonRepoMap(tmp_path)
    repo_map.build()

    assert len(repo_map.render(repo_map.symbols, max_chars=20)) <= 20
    try:
        repo_map.invalidate(tmp_path.parent / "outside.py")
    except ValueError as error:
        assert "outside repository" in str(error)
    else:
        raise AssertionError("outside paths must be rejected")
