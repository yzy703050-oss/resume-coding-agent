# Live DeepSeek Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trustworthy 12-task DeepSeek Flash microtask evaluator, then run the frozen suite once under the approved CNY 15 operator budget.

**Architecture:** A paid-run coordinator creates an Agent-visible fixture per task and uses the existing baseline LangGraph runtime. It exports the resulting patch to a new evaluator-controlled repository, installs hidden tests only there, runs a trusted pytest or mutation oracle, and writes a sanitized aggregate report. A canary stops the suite only for authentication, transport, or evaluator-infrastructure failure; ordinary task failures remain in the denominator.

**Tech Stack:** Python 3.12+, LangChain, LangGraph, DeepSeek Flash, Pydantic, python-dotenv, pytest, Git

**Spec:** `docs/superpowers/specs/2026-09-16-live-deepseek-evaluation-design.md`

## Global Constraints

- Work directly on `main`; the user explicitly requested no feature worktree.
- Never print, log, serialize, stage or commit `.env` or `DEEPSEEK_API_KEY`.
- The paid command must require `--confirm-paid-run` and must fail before model construction without it.
- Use `deepseek-flash`, non-thinking mode, baseline preset, 8 model decisions, 512 output tokens per request, 8000 reported total tokens per Run, zero auxiliary calls and one repetition.
- Run exactly the frozen 12-task `resume-v1` suite; do not retry a complete Run or replace failures.
- Judge only in fresh evaluator repositories after applying the exported patch and installing hidden oracle files.
- Stop after an authentication, transport or evaluator-infrastructure failure; retain and continue past ordinary Agent task failures.
- Treat CNY 15 as an operator authorization, not a programmatic billing guarantee.
- Report actual successes and failures; do not claim general coding-agent performance from this microtask suite.

---

### Task 1: Local Secret Loading Boundary

**Files:**
- Modify: `pyproject.toml`
- Create: `.env.example`
- Create: `src/coding_agent/evaluation/environment.py`
- Create: `tests/unit/evaluation/test_environment.py`

**Interfaces:**
- Produces: `load_deepseek_key(project_root: Path, environ: Mapping[str, str] | None = None) -> SecretStr`
- Consumes: repository-root ignored `.env`; process `DEEPSEEK_API_KEY` takes precedence.

- [ ] **Step 1: Write failing environment tests**

```python
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
```

- [ ] **Step 2: Run the tests and verify the module is missing**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_environment.py -q
```

Expected: collection fails because `coding_agent.evaluation.environment` does not exist.

- [ ] **Step 3: Add the dependency, template and loader**

Add `"python-dotenv>=1.0,<2"` to project dependencies and create `.env.example` containing exactly:

```dotenv
DEEPSEEK_API_KEY=
```

Implement:

```python
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
```

- [ ] **Step 4: Install the updated editable project and pass the focused tests**

Run:

```powershell
& '.venv/Scripts/python.exe' -m pip install -e '.[dev]'
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_environment.py -q
```

Expected: all environment tests pass without printing a key.

- [ ] **Step 5: Commit the secret-loading boundary**

```powershell
git add pyproject.toml .env.example src/coding_agent/evaluation/environment.py tests/unit/evaluation/test_environment.py
git commit -m "feat: load local DeepSeek evaluation credentials"
```

---

### Task 2: Frozen Resume Evaluation Suite

**Files:**
- Create: `src/coding_agent/evaluation/suite.py`
- Create: `tests/fixtures/live_tasks/resume-v1/suite.json`
- Create: `tests/fixtures/live_tasks/resume-v1/<task-id>/task.json` for all 12 task IDs
- Create: `tests/fixtures/hidden_oracles/resume-v1/<task-id>/oracle.json` for all 12 task IDs
- Create: `tests/fixtures/hidden_oracles/resume-v1/<task-id>/test_hidden.py` for the 11 pytest-oracle tasks
- Create: `tests/unit/evaluation/test_resume_suite.py`

**Interfaces:**
- Produces: `LiveSuite`, `LiveTask`, `OracleSpec`, and `load_live_suite(tasks_root: Path, oracle_root: Path) -> LiveSuite`
- Consumes: existing `TaskManifest` loader and the task IDs frozen in the approved spec.

- [ ] **Step 1: Write failing suite-integrity tests**

```python
from pathlib import Path

from coding_agent.evaluation.suite import RESUME_V1_TASK_IDS, load_live_suite


ROOT = Path(__file__).parents[2] / "fixtures"


def test_resume_v1_has_exact_frozen_order() -> None:
    suite = load_live_suite(
        ROOT / "live_tasks" / "resume-v1",
        ROOT / "hidden_oracles" / "resume-v1",
    )
    assert (
        suite.task_ids
        == RESUME_V1_TASK_IDS
        == (
            "off-by-one",
            "change-contract",
            "add-regression-test",
            "empty-mean",
            "parse-port",
            "normalize-tags",
            "category-totals",
            "optional-display-name",
            "json-omit-none",
            "stable-priority",
            "package-export",
            "recover-failing-test",
        )
    )
    assert len(set(suite.task_ids)) == 12


def test_every_task_has_gold_and_evaluator_owned_oracle() -> None:
    suite = load_live_suite(
        ROOT / "live_tasks" / "resume-v1",
        ROOT / "hidden_oracles" / "resume-v1",
    )
    for task in suite.tasks:
        assert task.manifest.gold_files
        assert task.oracle.task_id == task.manifest.id
        assert task.oracle.kind in {"pytest", "mutation"}
        if task.oracle.kind == "pytest":
            assert task.oracle.hidden_files
        else:
            assert task.oracle.mutation_files
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_resume_suite.py -q
```

Expected: failure because the suite module and data do not exist.

- [ ] **Step 3: Implement typed suite loading**

Create immutable structures with these exact fields:

```python
class OracleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str
    kind: Literal["pytest", "mutation"]
    hidden_files: tuple[str, ...] = ()
    mutation_files: dict[str, str] = Field(default_factory=dict)


@dataclass(frozen=True)
class LiveTask:
    manifest: TaskManifest
    oracle: OracleSpec
    oracle_root: Path


@dataclass(frozen=True)
class LiveSuite:
    name: str
    tasks: tuple[LiveTask, ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.manifest.id for task in self.tasks)
```

`load_live_suite` must load the order from `suite.json`, reject missing/duplicate/extra IDs, ensure every hidden file resolves inside its oracle directory, and ensure `oracle.task_id == manifest.id`.

- [ ] **Step 4: Add all frozen task manifests and hidden oracles**

Use the exact task contracts from the design spec. The nine new initial defects and gold fixes are:

| ID | Initial defect | Gold behavior |
|---|---|---|
| `empty-mean` | `sum(values) / len(values)` crashes with division error | explicitly raise `ValueError("values must not be empty")` before normal mean calculation |
| `parse-port` | blindly calls `int(value)` | accept only integers or decimal strings in `1..65535`; reject bool, float, non-decimal and out-of-range values with `ValueError` |
| `normalize-tags` | returns input unchanged | strip and lowercase strings, omit blank tags, deduplicate while preserving first occurrence order |
| `category-totals` | dict comprehension overwrites duplicate categories | accumulate numeric amounts for repeated category names and return `{}` for empty input |
| `optional-display-name` | checks only `name is None` | return `"Guest"` for `None`, empty or whitespace-only values; return the original nonblank name |
| `json-omit-none` | removes `None` only from the top-level dict | recursively omit dictionary keys whose value is `None`, recurse through nested dicts and lists, and preserve list positions |
| `stable-priority` | uses `(priority, name)` and reorders ties | sort descending by numeric priority using Python's stable sort and preserve input order for ties |
| `package-export` | package has an unimplemented `slugify` and no public export | lowercase, trim, collapse non-alphanumeric runs to one hyphen, strip edge hyphens, and export `slugify` from `textutil.__init__` |
| `recover-failing-test` | `text.split(" ")` counts empty fragments and mishandles tabs | count words with whitespace-aware `split()` while preserving the public signature |

Hidden tests must include at least three cases per contract and must not duplicate only the visible example. `add-regression-test/oracle.json` must use `kind="mutation"` and replace `mathutil.py` with:

```python
def multiply(a, b):
    return a + b
```

- [ ] **Step 5: Pass suite-integrity tests and validate JSON**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_resume_suite.py -q
```

Expected: two suite-integrity tests pass.

- [ ] **Step 6: Commit the frozen suite**

```powershell
git add src/coding_agent/evaluation/suite.py tests/fixtures/live_tasks tests/fixtures/hidden_oracles tests/unit/evaluation/test_resume_suite.py
git commit -m "test: add frozen live evaluation suite"
```

---

### Task 3: Fresh-Copy Patch and Trusted Oracle

**Files:**
- Create: `src/coding_agent/evaluation/trusted_oracle.py`
- Create: `tests/unit/evaluation/test_trusted_oracle.py`
- Modify: `tests/unit/evaluation/test_resume_suite.py`

**Interfaces:**
- Consumes: `LiveTask`, an exported unified patch string, and an evaluator workspace.
- Produces: `TrustedOracleResult`, `judge_patch(task: LiveTask, patch: str, workspace: Path) -> TrustedOracleResult`, and `oracle_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]`.

- [ ] **Step 1: Write failing patch-isolation and oracle tests**

Cover these exact behaviors:

```python
def gold_patch(task: LiveTask, root: Path) -> tuple[Path, str]:
    repo = prepare_fixture(task.manifest, root)
    base = current_head(repo)
    apply_gold(repo, task.manifest.gold_files)
    return repo, git_diff(repo, base).patch


def test_hidden_files_never_exist_in_agent_fixture(tmp_path: Path, off_by_one: LiveTask) -> None:
    agent_repo = prepare_fixture(off_by_one.manifest, tmp_path / "agent")
    assert not any(path.name == "test_hidden.py" for path in agent_repo.rglob("*"))


def test_gold_patch_applies_to_fresh_copy_and_passes_hidden_oracle(
    tmp_path: Path, off_by_one: LiveTask
) -> None:
    agent_repo, patch = gold_patch(off_by_one, tmp_path / "agent")
    result = judge_patch(off_by_one, patch, tmp_path / "evaluation")
    assert result.patch_applied
    assert result.trusted_oracle_passed
    assert result.judge_repository != agent_repo


def test_visible_test_tampering_does_not_remove_hidden_oracle(
    tmp_path: Path, off_by_one: LiveTask
) -> None:
    agent_repo = prepare_fixture(off_by_one.manifest, tmp_path / "agent")
    base = current_head(agent_repo)
    (agent_repo / "test_app.py").write_text("def test_vacuous():\n    assert True\n")
    patch = git_diff(agent_repo, base).patch
    result = judge_patch(off_by_one, patch, tmp_path / "evaluation")
    assert result.patch_applied
    assert not result.trusted_oracle_passed


def test_regression_test_must_kill_mutation(tmp_path: Path, add_regression_test: LiveTask) -> None:
    agent_repo = prepare_fixture(add_regression_test.manifest, tmp_path / "agent")
    base = current_head(agent_repo)
    (agent_repo / "test_mathutil.py").write_text("def test_vacuous():\n    assert True\n")
    patch = git_diff(agent_repo, base).patch
    result = judge_patch(add_regression_test, patch, tmp_path / "evaluation")
    assert not result.trusted_oracle_passed
    assert result.failure_category == "mutation_survived"


def test_key_is_removed_from_oracle_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "never-forward-this")
    monkeypatch.setenv("OPENAI_API_KEY", "nor-this")
    sanitized = oracle_environment()
    assert "DEEPSEEK_API_KEY" not in sanitized
    assert "OPENAI_API_KEY" not in sanitized
```

The test module must define typed `off_by_one` and `add_regression_test` fixtures by loading `resume-v1` and selecting the exact task ID.

- [ ] **Step 2: Run the tests and verify the oracle module is missing**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_trusted_oracle.py -q
```

Expected: collection failure for the missing module.

- [ ] **Step 3: Implement patch application and result types**

Use:

```python
@dataclass(frozen=True)
class TrustedOracleResult:
    patch_applied: bool
    trusted_oracle_passed: bool
    failure_category: str | None
    oracle_exit_code: int | None
    oracle_stdout: str
    oracle_stderr: str
    judge_repository: Path
```

`judge_patch` must:

1. call `prepare_fixture` into `workspace / "judge"`;
2. write the patch outside that repository;
3. run `git apply --check` then `git apply` with captured UTF-8 output;
4. copy only paths declared by `OracleSpec.hidden_files`, resolving both source and destination with `resolve_confined`;
5. build a subprocess environment without `DEEPSEEK_API_KEY` or `OPENAI_API_KEY`;
6. run `python -m pytest -q` with a 120-second timeout;
7. for mutation tasks, first require the submitted suite to pass, then overwrite only declared mutation files and require pytest to return nonzero;
8. return a typed failure category instead of raising for patch rejection or test failure.

- [ ] **Step 4: Validate every initial and gold implementation**

Extend the suite test so each initial fixture fails its trusted oracle and each gold patch passes. For mutation tasks, the gold-added regression test must pass correct code and fail the mutated code.

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_trusted_oracle.py tests/unit/evaluation/test_resume_suite.py -q
```

Expected: all patch, isolation and oracle tests pass for all 12 tasks.

- [ ] **Step 5: Commit the trusted evaluator**

```powershell
git add src/coding_agent/evaluation/trusted_oracle.py tests/unit/evaluation/test_trusted_oracle.py tests/unit/evaluation/test_resume_suite.py
git commit -m "feat: add trusted fresh-copy evaluation oracle"
```

---

### Task 4: Live Coordinator, Paid Gate and Sanitized Report

**Files:**
- Create: `src/coding_agent/evaluation/live.py`
- Create: `tests/unit/evaluation/test_live.py`
- Create: `tests/integration/test_live_evaluation.py`

**Interfaces:**
- Consumes: `LiveSuite`, `SecretStr`, existing `build_runner`, DeepSeek model factory and `judge_patch`.
- Produces: `LiveTaskResult`, `LiveEvaluationReport`, `TaskExecutor` protocol, `run_live_suite(project_root: Path, suite: LiveSuite, workspace: Path, key: SecretStr, model_factory: Callable[[RunConfig], ModelClient] = create_langchain_model, task_executor: TaskExecutor | None = None) -> LiveEvaluationReport`, `main(argv: Sequence[str] | None = None) -> int`, and CLI module `python -m coding_agent.evaluation.live`.

- [ ] **Step 1: Write failing paid-gate tests**

```python
def test_confirmation_is_required_before_key_or_model_loading(monkeypatch, tmp_path):
    touched = False

    def forbidden(*args, **kwargs):
        nonlocal touched
        touched = True
        raise AssertionError("must not construct live dependencies")

    monkeypatch.setattr(live, "load_deepseek_key", forbidden)
    exit_code = live.main(["--project-root", str(tmp_path)])
    assert exit_code == 2
    assert not touched


def test_report_serialization_never_contains_key(
    fake_report: LiveEvaluationReport, supplied_secret: str
) -> None:
    rendered = fake_report.model_dump_json()
    assert supplied_secret not in rendered
    assert "DEEPSEEK_API_KEY" not in rendered


def test_canary_transport_failure_stops_before_second_task(
    tmp_path: Path, resume_suite: LiveSuite, fake_key: SecretStr
) -> None:
    called_task_ids: list[str] = []

    def transport_failure(task: LiveTask, *args: object) -> LiveTaskResult:
        called_task_ids.append(task.manifest.id)
        raise ModelTransportError("model request failed")

    report = run_live_suite(
        tmp_path, resume_suite, tmp_path / "runs", fake_key, task_executor=transport_failure
    )
    assert called_task_ids == ["off-by-one"]
    assert report.stop_reason == "canary_infrastructure_failure"


def test_ordinary_canary_task_failure_remains_and_suite_continues(
    tmp_path: Path,
    resume_suite: LiveSuite,
    fake_key: SecretStr,
    failed_task_result_factory: Callable[[str], LiveTaskResult],
) -> None:
    called_task_ids: list[str] = []

    def ordinary_failure(task: LiveTask, *args: object) -> LiveTaskResult:
        called_task_ids.append(task.manifest.id)
        return failed_task_result_factory(task.manifest.id)

    report = run_live_suite(
        tmp_path, resume_suite, tmp_path / "runs", fake_key, task_executor=ordinary_failure
    )
    assert called_task_ids == list(RESUME_V1_TASK_IDS)
    assert report.results[0].task_success is False
```

The test module must define `fake_report`, `supplied_secret`, `resume_suite`, `fake_key` and `failed_task_result_factory` fixtures with every required report field populated. It must not instantiate `LangChainModelClient` or perform HTTP requests.

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_live.py tests/integration/test_live_evaluation.py -q
```

Expected: failure because `evaluation.live` does not exist.

- [ ] **Step 3: Implement report models**

Use Pydantic models with `extra="forbid"` and these required task fields:

```python
task_id: str
protocol_completed: bool
patch_applied: bool
trusted_oracle_passed: bool
task_success: bool
agent_status: str
termination_reason: str | None
failure_category: str | None
steps: int
tool_counts: dict[str, int]
elapsed_ms: int
input_tokens: int
output_tokens: int
auxiliary_tokens: int
cost_usd: None
patch_sha256: str
artifact_directory: str
```

The aggregate report must contain schema version, `evaluation_kind="live_model_microtask_suite"`, suite name, manifest hash, provider, model, limits, start/end timestamps, attempted task count, successes, stopped-early flag, stop reason and ordered results. `cost_usd` remains `None`.

- [ ] **Step 4: Implement one-Run evaluation and suite control**

For every task:

1. create `workspace / task_id / "agent"` with `prepare_fixture`;
2. build `RunConfig` with the exact global limits and artifacts outside the repo;
3. create a new DeepSeek LangChain client for the Run using the supplied `SecretStr`;
4. run the existing `AgentRunner` once;
5. read `patch.diff`, compute SHA-256, and call `judge_patch` in `workspace / task_id / "evaluation"`;
6. classify task success as protocol completed AND patch applied AND trusted oracle passed;
7. preserve task failure and continue unless the failure is authentication, transport, or evaluator infrastructure.

Use dependency injection for `model_factory` and `task_runner` so unit/integration tests never call the network.

- [ ] **Step 5: Implement the CLI and atomic report writing**

The CLI accepts:

```text
--project-root PATH
--suite resume-v1
--workspace PATH (default runs/live-deepseek-resume-v1)
--output PATH (default benchmarks/deepseek-live-resume-v1.json)
--confirm-paid-run
```

Reject any suite other than `resume-v1`. Load `.env` only after confirmation. Write the report to a sibling `.tmp` and replace the final JSON atomically. Print only task IDs, statuses, token totals and artifact/report paths.

- [ ] **Step 6: Pass paid-gate, coordinator and sanitizer tests**

Run:

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation/test_live.py tests/integration/test_live_evaluation.py -q
```

Expected: all tests pass with fake clients and no network calls.

- [ ] **Step 7: Commit the live coordinator**

```powershell
git add src/coding_agent/evaluation/live.py tests/unit/evaluation/test_live.py tests/integration/test_live_evaluation.py
git commit -m "feat: add gated live DeepSeek evaluator"
```

---

### Task 5: Documentation and Full Offline Verification

**Files:**
- Modify: `docs/EVALUATION.md`
- Modify: `README.md`
- Modify: `TASK_STATE.md`
- Modify: `.github/workflows/offline.yml` if its install command does not include updated project dependencies

**Interfaces:**
- Consumes: final CLI and report schema.
- Produces: copyable paid command, interpretation rules and up-to-date project state.

- [ ] **Step 1: Document the exact paid command and safety boundary**

Add:

```powershell
$env:PYTHONPATH = 'src'
& '.venv/Scripts/python.exe' -m coding_agent.evaluation.live `
  --project-root . `
  --suite resume-v1 `
  --confirm-paid-run
```

State that `.env` is ignored, the suite contains 12 microtasks, hidden tests run only in fresh judge copies, a canary infrastructure failure stops the suite, normal task failures remain in the denominator, no full-Run retries occur, and CNY 15 is not a billing hard limit.

- [ ] **Step 2: Run focused evaluation tests**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest tests/unit/evaluation tests/integration/test_live_evaluation.py tests/e2e/test_fixture_manifests.py -q
```

Expected: all focused tests pass with no API calls.

- [ ] **Step 3: Run the complete offline verification gate**

```powershell
$env:PYTHONPATH='src'
& '.venv/Scripts/python.exe' -m pytest -q
& '.venv/Scripts/ruff.exe' check .
& '.venv/Scripts/ruff.exe' format --check .
& '.venv/Scripts/mypy.exe' src
openspec validate --all --strict
git diff --check
```

Expected: pytest has zero failures; Ruff, formatting, mypy, OpenSpec and diff checks exit zero.

- [ ] **Step 4: Programmatically verify the configured key is absent from tracked and generated pre-run files**

Read the key into memory without printing it, scan tracked files and the planned report/workspace locations, and output only `SECRET_LEAK_FOUND=False`. Abort before paid execution if true.

- [ ] **Step 5: Commit documentation and verification updates**

```powershell
git add README.md TASK_STATE.md docs/EVALUATION.md .github/workflows/offline.yml
git commit -m "docs: document trusted live evaluation"
```

---

### Task 6: Run the Authorized Suite and Publish Honest Results

**Files:**
- Generate ignored: `runs/live-deepseek-resume-v1/**`
- Generate and inspect: `benchmarks/deepseek-live-resume-v1.json`
- Modify after observing results: `docs/EVALUATION.md`
- Modify after observing results: `docs/RESUME.md`
- Modify after observing results: `TASK_STATE.md`

**Interfaces:**
- Consumes: approved CNY 15 operator authorization, populated ignored `.env`, green offline gate and frozen suite.
- Produces: one immutable 12-task attempt report and evidence-based resume wording.

- [ ] **Step 1: Record the pre-run Git and suite identity**

Capture `git rev-parse HEAD`, suite manifest hash, Python/package versions and UTC start time into the report metadata. Require a clean tracked working tree; ignored `.env` is allowed.

- [ ] **Step 2: Execute exactly one paid suite**

```powershell
$env:PYTHONPATH = 'src'
& '.venv/Scripts/python.exe' -m coding_agent.evaluation.live `
  --project-root . `
  --suite resume-v1 `
  --confirm-paid-run
```

Do not restart the command after an ordinary task failure. If the canary stops on authentication/transport/infrastructure, diagnose without issuing another paid call until the user approves a retry.

- [ ] **Step 3: Inspect the complete report and every task artifact**

Verify attempted-task count, ordered IDs, status, patch hash, hidden-oracle outcome, tokens and stop reason. Scan the report and generated artifacts for the exact key in memory and output only a boolean. Abort publication if any leak is found.

- [ ] **Step 4: Update documentation with observed facts only**

Record the exact numerator/denominator, model, date, total reported tokens, median steps/latency and failure categories. Keep the labels “12-task Python microtask evaluation” and “single run per task.” Do not write a general success-rate claim, token-saving percentage, SWE-bench result or cost when provider billing is unavailable.

Resume wording must follow this pattern with observed values substituted:

```text
构建 12 任务 DeepSeek 真实模型评测，使用隔离仓库、外部 hidden tests 与干净副本判题验证代码补丁；单次评测通过 X/12，保留失败轨迹、token 与工具调用证据。
```

- [ ] **Step 5: Re-run offline verification after result documentation**

Run the full commands from Task 5 Step 3. Expected: all commands exit zero.

- [ ] **Step 6: Commit the sanitized report and factual documentation**

```powershell
git add benchmarks/deepseek-live-resume-v1.json docs/EVALUATION.md docs/RESUME.md TASK_STATE.md
git commit -m "eval: record live DeepSeek microtask results"
```

Do not add `runs/` or `.env`.
