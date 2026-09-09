"""Validated runtime configuration."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Path
    task: str
    model: str = "gpt-5"
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    max_steps: int = Field(default=20, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, gt=0)
    command_timeout_seconds: float = Field(default=60, gt=0, le=600)
    context_max_chars: int = Field(default=24_000, ge=400)
    pinned_max_chars: int = Field(default=12_000, ge=0)
    artifacts_dir: Path = Path("runs")
    script: Path | None = None

    @field_validator("task")
    @classmethod
    def validate_task(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task must not be empty")
        return value.strip()
