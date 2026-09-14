# Coding Agent with Hierarchical Context and Memory

A small, inspectable Coding Agent that turns a task against a clean local Git repository into a tested patch and an auditable trajectory. The project is deliberately a baseline: its complete control loop fits in one runner, its tools are deterministic, and its claims are checked by tests and independent evaluation rather than model prose.

## Why this repository is useful

In one synchronous loop the agent can explore files, search and read code, apply checked edits, run controlled commands, observe failures, retry, and finish with three artifacts:

- `events.jsonl`: append-only, ordered run evidence;
- `patch.diff`: the repository diff from the starting commit;
- `summary.json`: status, limits, usage, steps, tools, changed files, and latest test evidence.

The current deterministic baseline solves all three included micro-tasks (3/3). This measures runtime and evaluation correctness—not general LLM capability. See [the checked-in report](benchmarks/baseline-scripted.json).

## Architecture

```mermaid
flowchart TD
    CLI["CLI / preset composition"] --> RUNNER["Single-action AgentRunner"]
    RUNNER -->|prepare| CM["ContextManager"]
    CM --> WM["L1 WorkingMemory"]
    CM --> EP["L2 EpisodicMemory"]
    EP --> PIPE["Immutable history processors"]
    PIPE --> COND["L3 condenser"]
    CM --> REPO["PythonRepoMap"]
    CM --> STORE["L4 project-scoped SQLite"]
    ID["Versioned project_id"] --> STORE
    CM --> SELECT["ContextSelector + budgets"]
    SELECT --> BUILD["Formatting-only ContextBuilder"]
    BUILD --> MODEL["ModelClient"]
    MODEL --> RUNNER
    RUNNER --> TOOLS["Fixed six-tool registry"]
    TOOLS --> REC["RunEventRecorder"]
    RUNNER --> REC
    REC --> CANON["Canonical in-memory event"]
    CANON --> HISTORY["History sanitization/projection"]
    HISTORY --> EP
    CANON --> AUDIT["Audit sanitization/truncation"]
    AUDIT --> JSONL["events.jsonl"]
    RUNNER --> FINAL["Finalizer: sole terminal owner"]
    FINAL --> PATCH["patch.diff + summary.json"]
```

`Finalizer` remains the only component that may write `AgentFinished` or `AgentFailed`. Runtime facts are created once, then independently projected to richer secret-free episodic history and stricter audit JSONL. The model-facing history never reads the audit-truncated payload.

The default `baseline` preset preserves the small deterministic runtime. Opt-in presets are `processor`, `condenser`, `repo-map`, `project-memory`, and `full`. `full` enables deterministic processing/condensation, static Python symbols, and validated cross-run project memory; it is not the default and will not become the default without comparative evaluation.

Project memory is stored in `project-memory.sqlite3` under the external artifact root. A versioned SHA-256 `project_id` prefers a credential-free canonical Git origin and otherwise uses the resolved Git common directory. Extractors can only propose typed candidates. Every proposal passes sanitization, policy, canonical-event/path provenance validation, normalization, and deduplication before the SQLite API accepts it. Optional LLM extractors and condensers can call a model only through the auxiliary gateway; their reported tokens/cost count separately and toward the combined Run limits.

## Install

Python 3.12+ and Git are required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Three-minute offline demo

The scripted model makes the run reproducible and requires no API key. It still exercises the real runner, context builder, file tools, subprocess backend, Git diff, events, and finalizer.

```powershell
$demo = Join-Path $env:TEMP ("coding-agent-demo-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $demo | Out-Null
Set-Content -Path (Join-Path $demo "calc.py") -Value "def add(a, b):`n    return a - b" -Encoding utf8
Set-Content -Path (Join-Path $demo "test_calc.py") -Value "from calc import add`n`ndef test_add():`n    assert add(2, 3) == 5" -Encoding utf8
Set-Content -Path (Join-Path $demo ".gitignore") -Value ".pytest_cache/`n__pycache__/" -Encoding utf8
git -C $demo init -b main
git -C $demo -c user.name=Demo -c user.email=demo@example.invalid add .
git -C $demo -c user.name=Demo -c user.email=demo@example.invalid commit -m initial
coding-agent run $demo --task "Fix add and verify it" --script examples/offline-script.json --artifacts-dir runs
```

Expected outcome: `Status: completed`, a non-empty `patch.diff`, one `AgentFinished` event, and a summary whose latest test result reports a passing pytest run.

To rerun the three-task independent baseline:

```powershell
python -m coding_agent.evaluation.baseline --output benchmarks/baseline-scripted.json
```

## Live model run

Only run trusted repositories: commands execute on the host and this MVP is **not a sandbox**.

```powershell
$env:OPENAI_API_KEY = "your-key"
coding-agent run C:\path\to\clean-repo --task "Fix issue #123 and run focused tests" --model gpt-5 --base-url https://api.openai.com/v1 --max-steps 20 --timeout 60
```

Enable all V2 context sources explicitly with `--memory-preset full`. Auxiliary model features remain disabled unless configured with hard limits such as `--auxiliary-max-calls`, `--auxiliary-max-tokens`, and `--auxiliary-max-cost`.

The target must be a Git repository with no staged or unstaged tracked changes. Configuration and artifacts never include the API key value. Use `coding-agent run --help` for all limits.

By default, run artifacts are written to a repository-sibling directory named `.<repository>-coding-agent-runs`. An explicit `--artifacts-dir` must also be outside the target repository so logs cannot enter exploration results or the generated patch.

## Tool surface

The model receives exactly six repository tools:

| Tool | Purpose |
|---|---|
| `list_files` | Deterministically list bounded repository paths |
| `search_code` | Search UTF-8 text with stable file/line ordering |
| `read_file` | Read a bounded line range and pin it into working context |
| `edit_file` | Exclusively create a file or replace one exact unique string |
| `run_command` | Run an allow-listed executable/argument prefix with `shell=False` |
| `git_diff` | Inspect the unified diff against the initial commit |

Expected operational failures become structured observations, so the next model step can repair them. The default command policy permits pytest through `python -m pytest` or `pytest`; startup code may supply additional immutable prefixes.

## Verification

```powershell
python -m pytest -q
ruff check .
ruff format --check .
mypy src/coding_agent
openspec.cmd validate --all --strict
```

Tests cover domain transitions, terminal-event uniqueness, context retention/eviction, path confinement, checked edits, command policy, Windows process-tree cleanup, model parsing/retries, agent recovery and limits, CLI composition, three fixture oracles, and the complete offline loop.

## Reference-driven choices

- **mini-SWE-agent:** one understandable action → environment → observation loop and explicit termination.
- **SWE-agent:** separation between runtime trajectory, model-visible context, execution, and independent evaluation.
- **Aider:** checked edit application and budgeted repository context, simplified to explicit search/read and deterministic recency.
- **SWE-ReX:** a narrow execution protocol, implemented here only as a Windows-local backend.

The implementation borrows the trade-offs, not source code or a framework-sized architecture.

## Current boundaries

Cross-process resumption of run-local working, episodic, or condensed memory remains out of scope. The release also excludes multi-agent orchestration, vector databases, embeddings, Docker/general sandboxing, FastAPI/web UI, and distributed execution. SQLite persists only curated project knowledge, never resumable Run state.

Known limitations: exact-string edits are less flexible than patch/hunk formats; context uses approximate character rather than tokenizer budgets; only UTF-8 text is supported; and the local command policy reduces accidental shell misuse but cannot make untrusted repository tests safe.
