from pathlib import Path

import pytest

from coding_agent.evaluation.environment import load_deepseek_key


def test_process_environment_precedes_dotenv(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=file-secret\n", encoding="utf-8")
    key = load_deepseek_key(tmp_path, {"DEEPSEEK_API_KEY": "process-secret"})
    assert key.get_secret_value() == "process-secret"
    assert "process-secret" not in repr(key)


def test_dotenv_is_loaded_without_mutating_process_environment(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=file-secret\n", encoding="utf-8")
    provided: dict[str, str] = {}
    key = load_deepseek_key(tmp_path, provided)
    assert key.get_secret_value() == "file-secret"
    assert provided == {}


@pytest.mark.parametrize("content", ["", "DEEPSEEK_API_KEY=\n"])
def test_missing_key_has_generic_error(tmp_path: Path, content: str) -> None:
    (tmp_path / ".env").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="DeepSeek API key is not configured") as captured:
        load_deepseek_key(tmp_path, {})
    assert "sk-" not in str(captured.value)
