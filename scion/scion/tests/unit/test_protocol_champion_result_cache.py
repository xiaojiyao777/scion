from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.config.protocol_config import ScreeningConfig
from scion.core.evidence_recording.artifact_refs import _read_partial_metrics_snapshot
from scion.core.models import ExperimentStage, RunResult, SolverOutput
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.protocol.experiment.cache import ChampionResultCache
from scion.runtime.subprocess_runner import LocalSubprocessRunner


def test_repeated_champion_result_is_reused_and_candidate_still_runs(tmp_path):
    case_path = tmp_path / "cases" / "case.json"
    case_path.parent.mkdir()
    case_path.write_text('{"input": 1}\n', encoding="utf-8")
    champion_ws = _workspace(tmp_path, "champion")
    candidate_ws = _workspace(tmp_path, "candidate")
    runner = _CountingRunner(champion_ws=champion_ws)
    protocol = _protocol(tmp_path, runner, case_path)

    first = protocol.run_experiment(
        ExperimentStage.SCREENING,
        str(candidate_ws),
        str(champion_ws),
        "modify",
    )
    second = protocol.run_experiment(
        ExperimentStage.SCREENING,
        str(candidate_ws),
        str(champion_ws),
        "modify",
    )

    assert first.champion_cache_hits == 0
    assert first.champion_cache_misses == 1
    assert second.champion_cache_hits == 1
    assert second.champion_cache_misses == 0
    assert runner.call_count(str(champion_ws)) == 1
    assert runner.call_count(str(candidate_ws)) == 2
    assert second.stats.runtime_pairs == 0
    assert second.runtime_confidence == "low_cached_champion"
    assert "runtime_confidence=low_cached_champion" in second.exposed_summary

    raw = json.loads(Path(second.raw_metrics_ref).read_text(encoding="utf-8"))
    assert raw["champion_cache_hits"] == 1
    assert raw["champion_cache_misses"] == 0
    assert raw["champion_cached_runtime_pairs"] == 1
    assert raw["runtime_confidence"] == "low_cached_champion"
    assert raw["runtime_stats"]["runtime_pairs"] == 0
    assert raw["pairs"][0]["champion_result_source"] == "cached"
    assert raw["pairs"][0]["runtime_ratio_high_confidence"] is False


def test_cached_champion_runtime_tie_requires_fresh_runtime(tmp_path):
    case_path = tmp_path / "cases" / "case.json"
    case_path.parent.mkdir()
    case_path.write_text('{"input": 1}\n', encoding="utf-8")
    champion_ws = _workspace(tmp_path, "champion")
    candidate_ws = _workspace(tmp_path, "candidate")
    runner = _TieRuntimeRunner(champion_ws=champion_ws)
    protocol = _protocol(tmp_path, runner, case_path)

    first = protocol.run_experiment(
        ExperimentStage.SCREENING,
        str(candidate_ws),
        str(champion_ws),
        "modify",
    )
    second = protocol.run_experiment(
        ExperimentStage.SCREENING,
        str(candidate_ws),
        str(champion_ws),
        "modify",
    )

    assert first.gate_outcome == "pass"
    assert first.reason_codes == ("SCREENING_PASS_RUNTIME_TIE_IMPROVEMENT",)
    assert first.stats.runtime_pairs == 1
    assert second.gate_outcome == "unclear"
    assert second.reason_codes == ("RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",)
    assert second.stats.runtime_pairs == 0
    assert second.stats.champion_cached_runtime_pairs == 1
    assert second.stats.runtime_evidence_status == "fresh_champion_required"
    assert second.runtime_evidence_status == "fresh_champion_required"
    assert "runtime_evidence_status=fresh_champion_required" in (
        second.exposed_summary
    )
    assert "runtime_signal_role=audit_or_proposal_guidance_only" in (
        second.exposed_summary
    )
    assert "runtime_standalone_optimization_signal=false" in (
        second.exposed_summary
    )
    assert "fresh_champion_required=true" in second.exposed_summary
    assert (
        "runtime_gate_reason_semantics=runtime_fresh_champion_required"
        in second.exposed_summary
    )
    assert (
        "runtime_rerun_recommendation=fresh_champion_re_evaluation_required"
        in second.exposed_summary
    )
    assert runner.call_count(str(champion_ws)) == 1

    raw = json.loads(Path(second.raw_metrics_ref).read_text(encoding="utf-8"))
    assert raw["runtime_evidence_status"] == "fresh_champion_required"
    assert raw["runtime_stats"]["runtime_pairs"] == 0
    assert raw["pairs"][0]["champion_result_source"] == "cached"
    policy = raw["runtime_evidence_policy"]
    assert policy["schema_version"] == "runtime_evidence_policy.v1"
    assert policy["runtime_evidence_confidence"] == "low_cached_champion"
    assert policy["runtime_evidence_status"] == "fresh_champion_required"
    assert policy["fresh_champion_required"] is True
    assert policy["runtime_aggregate_excluded"] is True
    assert policy["standalone_optimization_signal"] is False
    assert policy["runtime_signal_role"] == "audit_or_proposal_guidance_only"
    assert policy["proposal_guidance_only"] is True
    assert policy["decision_features_excluded"] is True
    assert "RUNTIME_EVIDENCE_FRESH_CHAMPION_REQUIRED" in (
        policy["policy_reason_codes"]
    )
    visibility = raw["runtime_gate_visibility"]
    assert visibility["schema_version"] == "runtime_gate_visibility.v1"
    assert visibility["reason_semantics"] == [
        "runtime_fresh_champion_required"
    ]
    assert visibility["fresh_champion_required"] is True
    assert visibility["rerun_recommendation"] == (
        "fresh_champion_re_evaluation_required"
    )
    assert visibility["fresh_champion_requirement"] == (
        "fresh_champion_re_evaluation_required_before_runtime_tie_advances"
    )
    assert visibility["formal_rerun_scheduled"] is False
    assert visibility["decision_features_excluded"] is True
    status_snapshot = _read_partial_metrics_snapshot(second.raw_metrics_ref)
    assert status_snapshot["runtime_evidence_status"] == "fresh_champion_required"
    assert status_snapshot["runtime_evidence_policy"] == policy
    assert status_snapshot["runtime_gate_visibility"] == visibility
    assert status_snapshot["champion_cached_runtime_pairs"] == 1


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("seed", {"seed": 8}),
        ("time_limit_sec", {"time_limit_sec": 12}),
        ("selected_surface", {"selected_surface": "surface_b"}),
        (
            "objective_policy",
            {
                "objective_policy": SimpleNamespace(
                    mode="weighted_sum",
                    expose_weights_to_llm=False,
                )
            },
        ),
    ],
)
def test_cache_key_changes_for_protocol_inputs(tmp_path, field, kwargs):
    cache, base_key, base_args = _primed_cache(tmp_path)
    changed_args = {**base_args, **kwargs}
    changed_key = cache.build_key(**changed_args)

    assert field
    assert changed_key["digest"] != base_key["digest"]
    assert cache.get(changed_key) is None


def test_cache_key_changes_for_case_content_and_workspace_digest(tmp_path):
    cache, base_key, base_args = _primed_cache(tmp_path)
    case_path = Path(base_args["case_path"])
    case_path.write_text('{"input": 2}\n', encoding="utf-8")

    changed_case_key = cache.build_key(**base_args)

    assert changed_case_key["digest"] != base_key["digest"]
    assert cache.get(changed_case_key) is None

    case_path.write_text('{"input": 1}\n', encoding="utf-8")
    workspace_path = Path(base_args["champion_workspace"])
    (workspace_path / "source.py").write_text("VALUE = 2\n", encoding="utf-8")
    changed_workspace_key = cache.build_key(
        **{**base_args, "workspace_digest": None}
    )

    assert changed_workspace_key["digest"] != base_key["digest"]
    assert cache.get(changed_workspace_key) is None


def test_cache_key_tracks_scion_env_and_ignores_unrelated_env(tmp_path, monkeypatch):
    case_path = tmp_path / "cases" / "case.json"
    case_path.parent.mkdir()
    case_path.write_text('{"input": 1}\n', encoding="utf-8")
    champion_ws = _workspace(tmp_path, "champion")
    cache = ChampionResultCache(tmp_path / "cache")
    runner = LocalSubprocessRunner()
    base_args = {
        "champion_workspace": str(champion_ws),
        "case_path": str(case_path),
        "seed": 7,
        "time_limit_sec": 10,
        "selected_surface": "surface_a",
        "runner": runner,
        "metric_specs": None,
        "objective_policy": SimpleNamespace(
            mode="lexicographic",
            expose_weights_to_llm=False,
        ),
        "problem_spec": None,
        "workspace_digest": None,
    }
    monkeypatch.delenv("SCION_TEST_CHAMPION_CACHE_INPUT", raising=False)
    monkeypatch.setenv("UNRELATED_CHAMPION_CACHE_INPUT", "old")
    base_key = cache.build_key(**base_args)
    assert cache.put(base_key, _run_result(score=2, elapsed_ms=100))

    monkeypatch.setenv("UNRELATED_CHAMPION_CACHE_INPUT", "new")
    unrelated_key = cache.build_key(**base_args)
    assert unrelated_key["digest"] == base_key["digest"]
    assert cache.get(unrelated_key) is not None

    monkeypatch.setenv("SCION_TEST_CHAMPION_CACHE_INPUT", "new")
    scion_key = cache.build_key(**base_args)
    assert scion_key["digest"] != base_key["digest"]
    assert cache.get(scion_key) is None


def test_cache_preserves_solution_payload(tmp_path):
    cache, base_key, _base_args = _primed_cache(tmp_path)
    result = RunResult(
        success=True,
        exit_code=0,
        stdout="out",
        stderr="",
        elapsed_ms=12,
        output=SolverOutput(
            objective={"score": 5},
            feasible=True,
            runtime={"observed": 5},
            solution_payload={"artifact": {"items": [1, 2]}},
        ),
    )

    assert cache.put(base_key, result)

    cached = cache.get(base_key)
    assert cached is not None
    assert cached.output is not None
    assert cached.output.solution_payload == {"artifact": {"items": [1, 2]}}


def test_cache_restores_unknown_output_fields_as_solution_payload(tmp_path):
    cache, base_key, _base_args = _primed_cache(tmp_path)
    path = cache._entry_path(base_key["digest"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    output = payload["run_result"]["output"]
    output.pop("solution_payload", None)
    output["artifact"] = {"items": [3]}
    path.write_text(json.dumps(payload), encoding="utf-8")

    cached = cache.get(base_key)
    assert cached is not None
    assert cached.output is not None
    assert cached.output.solution_payload == {"artifact": {"items": [3]}}


def test_cache_source_files_stay_generic():
    terms = [
        "".join(("cv", "rp")),
        "".join(("rou", "te")),
        "".join(("al", "ns")),
        "".join(("vn", "s")),
        "".join(("capa", "city")),
        "".join(("fl", "eet")),
        "".join(("cust", "omer")),
        "".join(("de", "pot")),
    ]
    paths = [
        Path(__file__),
        Path(__file__).parents[2] / "protocol" / "experiment" / "cache.py",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert all(term not in text for term in terms)


class _CountingRunner:
    schema_version = "test-runner-v1"

    def __init__(self, *, champion_ws: Path) -> None:
        self.champion_ws = str(champion_ws)
        self.calls: list[dict] = []

    def run_solver(self, **kwargs):
        self.calls.append(dict(kwargs))
        if kwargs["workdir"] == self.champion_ws:
            return _run_result(score=2, elapsed_ms=100)
        return _run_result(score=1, elapsed_ms=120)

    def call_count(self, workdir: str) -> int:
        return sum(1 for call in self.calls if call["workdir"] == workdir)


class _TieRuntimeRunner(_CountingRunner):
    def run_solver(self, **kwargs):
        self.calls.append(dict(kwargs))
        if kwargs["workdir"] == self.champion_ws:
            return _run_result(score=1, elapsed_ms=100)
        return _run_result(score=1, elapsed_ms=50)


def _protocol(tmp_path: Path, runner, case_path: Path) -> ExperimentProtocol:
    return ExperimentProtocol(
        protocol_config=ProtocolConfig(
            screening=ScreeningConfig(n_cases_modify=1, n_cases_create=1)
        ),
        split_manager=SplitManager(
            SplitManifest(
                version="test",
                screening=[str(case_path)],
                validation=["validation_case"],
                frozen=["frozen_case"],
                canary=["canary_case"],
            )
        ),
        seed_ledger=SeedLedger(
            SeedLedgerConfig(
                version="test",
                screening=[7],
                validation=[11],
                frozen=[13],
                canary=[17],
            )
        ),
        runner=runner,
        time_limit_sec=10,
        metrics_dir=str(tmp_path / "metrics"),
    )


def _workspace(tmp_path: Path, name: str) -> Path:
    workspace = tmp_path / name
    workspace.mkdir()
    (workspace / "registry.yaml").write_text("version: test\n", encoding="utf-8")
    (workspace / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    return workspace


def _run_result(*, score: int, elapsed_ms: int) -> RunResult:
    return RunResult(
        success=True,
        exit_code=0,
        stdout="out",
        stderr="",
        elapsed_ms=elapsed_ms,
        output=SolverOutput(
            objective={"score": score},
            feasible=True,
            runtime={"observed": score},
        ),
    )


def _primed_cache(tmp_path: Path):
    case_path = tmp_path / "cases" / "case.json"
    case_path.parent.mkdir()
    case_path.write_text('{"input": 1}\n', encoding="utf-8")
    champion_ws = _workspace(tmp_path, "champion")
    runner = _CountingRunner(champion_ws=champion_ws)
    cache = ChampionResultCache(tmp_path / "cache")
    base_args = {
        "champion_workspace": str(champion_ws),
        "case_path": str(case_path),
        "seed": 7,
        "time_limit_sec": 10,
        "selected_surface": "surface_a",
        "runner": runner,
        "metric_specs": None,
        "objective_policy": SimpleNamespace(
            mode="lexicographic",
            expose_weights_to_llm=False,
        ),
        "problem_spec": None,
        "workspace_digest": None,
    }
    base_key = cache.build_key(**base_args)
    assert cache.put(base_key, _run_result(score=2, elapsed_ms=100))
    return cache, base_key, base_args
