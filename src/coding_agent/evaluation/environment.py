"""Local secret loading for explicitly approved live evaluations."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values
from pydantic import SecretStr


def load_deepseek_key(project_root: Path, environ: Mapping[str, str] | None = None) -> SecretStr:
    source = os.environ if environ is None else environ
    raw = source.get("DEEPSEEK_API_KEY")
    if not raw:
        value = dotenv_values(project_root / ".env").get("DEEPSEEK_API_KEY")
        raw = value if isinstance(value, str) else None
    if raw is None or not raw.strip():
        raise ValueError("DeepSeek API key is not configured")
    return SecretStr(raw.strip())
