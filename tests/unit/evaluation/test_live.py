from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

import coding_agent.evaluation.live as live
from coding_agent.evaluation.live import (
    LiveEvaluationReport,
    LiveTaskResult,
    run_live_suite,
)
from coding_agent.evaluation.suite import (
    RESUME_V1_TASK_IDS,
    LiveSuite,
    LiveTask,
    load_live_suite,
)
from coding_agent.models.openai_compatible import ModelTransportError

FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.fixture
def supplied_secret() -> str:
    return "unit-test-secret-that-must-not-leak"


@pytest.fixture
def fake_key(supplied_secret: str) -> SecretStr:
    return SecretStr(supplied_secret)


@pytest.fixture(scope="module")
def resume_suite() -> LiveSuite:
    return load_live_suite(
        FIXTURES / "live_tasks" / "resume-v1",
        FIXTURES / "hidden_oracles" / "resume-v1",
    )


@pytest.fixture
def failed_task_result_factory() -> Callable[[str], LiveTaskResult]:
    def build(task_id: str) -> LiveTaskResult:
        return LiveTaskResult(
            task_id=task_id,
            protocol_completed=True,
            patch_applied=True,
            trusted_oracle_passed=False,
            task_success=False,
            agent_status="completed",
            termination_reason="model finished",
            failure_category="hidden_oracle_failed",
            visible_test_result=True,
            steps=3,
            tool_counts={"edit_file": 1},
            elapsed_ms=25,
            input_tokens=10,
            output_tokens=5,
            auxiliary_tokens=0,
            cost_usd=None,
            patch_sha256="0" * 64,
            artifact_directory="runs/task/artifacts/run-id",
        )

    return build


@pytest.fixture
def fake_report(
    failed_task_result_factory: Callable[[str], LiveTaskResult],
) -> LiveEvaluationReport:
    now = datetime(2026, 9, 16, tzinfo=UTC)
    result = failed_task_result_factory("off-by-one")
    return LiveEvaluationReport(
        schema_version="1",
        evaluation_kind="live_model_microtask_suite",
        evaluator_version="resume-v1.0",
        suite_name="resume-v1",
        sample_size=12,
        manifest_sha256="1" * 64,
        provider="deepseek",
        model="deepseek-flash",
        limits=live.LIVE_LIMITS,
        started_at=now,
        finished_at=now,
        attempted_tasks=1,
        successes=0,
        stopped_early=False,
        stop_reason=None,
        input_tokens=10,
        output_tokens=5,
        auxiliary_tokens=0,
        cost_usd=None,
        results=(result,),
    )


def test_confirmation_is_required_before_key_or_model_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    touched = False

    def forbidden(*args: object, **kwargs: object) -> None:
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
        tmp_path,
        resume_suite,
        tmp_path / "runs",
        fake_key,
        task_executor=transport_failure,
    )
    assert called_task_ids == ["off-by-one"]
    assert report.attempted_tasks == 1
    assert report.stopped_early
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
        tmp_path,
        resume_suite,
        tmp_path / "runs",
        fake_key,
        task_executor=ordinary_failure,
    )
    assert called_task_ids == list(RESUME_V1_TASK_IDS)
    assert report.attempted_tasks == 12
    assert not report.stopped_early
    assert report.results[0].task_success is False
    assert report.input_tokens == 120
    assert report.output_tokens == 60


def test_cli_writes_report_atomically_without_printing_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_key: SecretStr,
    fake_report: LiveEvaluationReport,
    supplied_secret: str,
    resume_suite: LiveSuite,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "benchmarks" / "report.json"
    monkeypatch.setattr(live, "load_deepseek_key", lambda root: fake_key)
    monkeypatch.setattr(live, "load_live_suite", lambda *args: resume_suite)
    monkeypatch.setattr(live, "run_live_suite", lambda *args, **kwargs: fake_report)

    exit_code = live.main(
        [
            "--project-root",
            str(tmp_path),
            "--workspace",
            str(tmp_path / "runs"),
            "--output",
            str(output),
            "--confirm-paid-run",
        ]
    )

    assert exit_code == 0
    assert LiveEvaluationReport.model_validate_json(output.read_text("utf-8")) == fake_report
    assert not output.with_suffix(output.suffix + ".tmp").exists()
    assert supplied_secret not in capsys.readouterr().out


def test_fixed_live_limits_match_approved_budget_semantics() -> None:
    assert live.LIVE_LIMITS == {
        "max_steps": 8,
        "max_output_tokens": 512,
        "max_tokens": 8000,
        "memory_preset": "baseline",
        "auxiliary_max_calls": 0,
        "auxiliary_max_tokens": 0,
        "repeats": 1,
        "thinking_enabled": False,
    }


def test_evaluator_failure_stops_without_becoming_an_ordinary_task_failure(
    tmp_path: Path, resume_suite: LiveSuite, fake_key: SecretStr
) -> None:
    called_task_ids: list[str] = []

    def broken_evaluator(task: LiveTask, *args: object) -> LiveTaskResult:
        called_task_ids.append(task.manifest.id)
        raise ValueError("broken evaluator fixture")

    report = run_live_suite(
        tmp_path,
        resume_suite,
        tmp_path / "runs",
        fake_key,
        task_executor=broken_evaluator,
    )
    assert called_task_ids == ["off-by-one"]
    assert report.stop_reason == "canary_infrastructure_failure"
    assert report.results == ()
