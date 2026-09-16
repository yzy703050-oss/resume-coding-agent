"""Validated runtime configuration."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    repository: Path
    task: str
    provider: Literal["openai-compatible", "deepseek"] = "openai-compatible"
    model: str = "gpt-5"
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    max_output_tokens: int = Field(default=1024, ge=1, le=8192)
    thinking_enabled: bool | None = None
    max_steps: int = Field(default=20, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, gt=0)
    command_timeout_seconds: float = Field(default=60, gt=0, le=600)
    context_max_chars: int = Field(default=24_000, ge=400)
    pinned_max_chars: int = Field(default=12_000, ge=0)
    memory_preset: Literal[
        "baseline", "processor", "condenser", "repo-map", "project-memory", "full"
    ] = "baseline"
    auxiliary_max_calls: int = Field(default=0, ge=0)
    auxiliary_max_tokens: int = Field(default=0, ge=0)
    auxiliary_max_cost_usd: float | None = Field(default=None, ge=0)
    artifacts_dir: Path | None = None
    script: Path | None = None

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task must not be empty")
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base URL must not contain credentials, query, or fragment")
        return value.rstrip("/")
