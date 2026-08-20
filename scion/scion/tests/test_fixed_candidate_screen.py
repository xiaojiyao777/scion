from __future__ import annotations

from types import SimpleNamespace

import pytest
import run_fixed_candidate_screen as driver
from scion.core.models import CanaryResult, Decision, ExperimentStage


def _prepared(tmp_path, *, failed_pairs=0):
    config = {
        "label": "test-confirmation",
        "selected_surface": "solver_design",
        "population": {
            "cases": [
                {"path": "one.vrp", "time_limit_sec": 10},
                {"path": "two.vrp", "time_limit_sec": 20},
            ],
            "seeds": [7, 11],
            "canary": {"path": "canary.json", "seed": 13, "time_limit_sec": 5},
        },
        "budgets": {
            "max_solver_subprocesses": 10,
            "nominal_subject_seconds": 130,
            "positive_hard_timeout_seconds": 280,
        },
        "claim_boundary": {"scope": "test"},
    }
    return driver.Prepared(
        config=config,
        b0=tmp_path / "b0",
        candidate=tmp_path / "candidate",
        data_root=tmp_path / "data",
        protocol_config=SimpleNamespace(),
        bridge=None,
        adapter=None,
    )


def _stats(failed_pairs=0):
    values = {name: 0 for name in driver.SUMMARY_FIELDS}
    values.update(
        n_cases=2,
        wins=2,
        win_rate=1.0,
        median_delta=3.0,
        ci_low=1.0,
        ci_high=4.0,
        attempted_pairs=4,
        valid_pairs=4 - failed_pairs,
        failed_pairs=failed_pairs,
    )
    return SimpleNamespace(**values)


class _Runner:
    def __init__(self, counters):
        self._counters = counters

    def counters(self):
        return dict(self._counters)


class _Protocol:
    def __init__(self, *, gate="pass", failed_pairs=0):
        self.gate = gate
        self.failed_pairs = failed_pairs
        self.calls = []

    def run_experiment(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        assert args[0] is ExperimentStage.SCREENING
        assert kwargs["expand"] is True
        assert kwargs["selected_surface"] == "solver_design"
        assert kwargs["paired_execution"].block_id == "fixed_candidate_confirmation"
        return SimpleNamespace(
            stage=ExperimentStage.SCREENING,
            gate_outcome=self.gate,
            reason_codes=(),
            case_ids=("one.vrp", "two.vrp"),
            seed_set=(7, 11),
            raw_metrics_ref="metrics/test.json",
            stats=_stats(self.failed_pairs),
        )


def _install_fakes(monkeypatch, protocol, decision):
    monkeypatch.setattr(driver, "_make_protocol", lambda *_args: protocol)
    monkeypatch.setattr(
        driver,
        "_strict_canary",
        lambda *_args: CanaryResult(True, details={"order": "b0_then_candidate"}),
    )
    monkeypatch.setattr(
        driver,
        "SafeFeatureExtractor",
        lambda: SimpleNamespace(extract=lambda **_kwargs: object()),
    )
    monkeypatch.setattr(
        driver,
        "DecisionEngine",
        lambda _config: SimpleNamespace(
            decide=lambda _features: SimpleNamespace(
                decision=decision,
                reason_codes=(),
            )
        ),
    )


def test_source_summary_is_content_and_path_bound(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.py").write_text("a = 1\n")
    first = driver.source_summary(source)
    assert first["file_count"] == 1
    assert first["total_bytes"] == 6
    (source / "a.py").write_text("a = 2\n")
    assert driver.source_summary(source)["sha256"] != first["sha256"]


def test_source_summary_rejects_symlink(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("secret\n")
    (source / "alias.py").symlink_to(outside)
    with pytest.raises(driver.PrepError, match="symlink"):
        driver.source_summary(source)


def test_execute_reports_supported_only_after_pass_and_queue_validate(
    tmp_path, monkeypatch
):
    prepared = _prepared(tmp_path)
    counters = {
        "solver_subprocesses": 10,
        "nominal_subject_seconds": 130,
        "positive_hard_timeout_seconds": 280,
    }
    protocol = _Protocol()
    _install_fakes(monkeypatch, protocol, Decision.QUEUE_VALIDATE)
    result = driver.execute(prepared, tmp_path, _Runner(counters))
    assert result["terminal_type"] == "CONFIRMATION_SUPPORTED"
    assert result["decision"] == "queue_validate"
    assert len(protocol.calls) == 1


@pytest.mark.parametrize(
    ("gate", "failed_pairs", "decision"),
    [
        ("fail", 0, Decision.CONTINUE_EXPLORE),
        ("pass", 1, Decision.QUEUE_VALIDATE),
        ("pass", 0, Decision.CONTINUE_EXPLORE),
    ],
)
def test_execute_reports_completed_negative_without_upgrading_claim(
    tmp_path, monkeypatch, gate, failed_pairs, decision
):
    prepared = _prepared(tmp_path)
    counters = {
        "solver_subprocesses": 10,
        "nominal_subject_seconds": 130,
        "positive_hard_timeout_seconds": 280,
    }
    _install_fakes(
        monkeypatch, _Protocol(gate=gate, failed_pairs=failed_pairs), decision
    )
    result = driver.execute(prepared, tmp_path, _Runner(counters))
    assert result["status"] == "completed"
    assert result["terminal_type"] == "CONFIRMATION_NOT_SUPPORTED"


def test_execute_fails_closed_on_incomplete_resource_matrix(tmp_path, monkeypatch):
    prepared = _prepared(tmp_path)
    _install_fakes(monkeypatch, _Protocol(), Decision.QUEUE_VALIDATE)
    runner = _Runner(
        {
            "solver_subprocesses": 9,
            "nominal_subject_seconds": 120,
            "positive_hard_timeout_seconds": 255,
        }
    )
    with pytest.raises(driver.ScientificTerminal, match="execution matrix"):
        driver.execute(prepared, tmp_path, runner)
