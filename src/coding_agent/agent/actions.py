"""Structured model actions and observations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class ToolAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["tool"] = "tool"
    tool: str = Field(min_length=1)
    arguments: dict[str, JsonValue]


class FinishAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["finish"] = "finish"
    summary: str = Field(min_length=1)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str = Field(min_length=1)
    ok: bool
    summary: str
    data: dict[str, JsonValue]
    error_code: str | None = None
    truncated: bool = False


class ModelUsage(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: ModelUsage) -> None:
        had_reported_usage = self.total_tokens > 0
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        if other.cost_usd is None:
            self.cost_usd = None
        elif self.cost_usd is None and not had_reported_usage:
            self.cost_usd = other.cost_usd
        elif self.cost_usd is None:
            return
        else:
            self.cost_usd += other.cost_usd
