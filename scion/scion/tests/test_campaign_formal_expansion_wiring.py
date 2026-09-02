"""Campaign wiring regression for the formal CVRP staged screen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.models import (
    BranchState,
    CanaryResult,
    Decision,
    EvalStats,
    ExperimentStage,
    PairwiseCaseFeedback,
    ProtocolResult,
)
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.mock_client import MockLLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.protocol.experiment.selection import select_cases
from scion.protocol.gates import screening_gate, validation_gate

from .campaign_test_support import _VALID_HYPOTHESIS, _VALID_PATCH, _campaign
from .protocol_adapter_test_support import protocol_test_adapter

_FORMAL_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp" / "formal"


def _ordinary_source_bytes(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        assert not path.is_symlink()
        if {"__pycache__", ".pytest_cache"}.intersection(relative.parts):
            continue
        if relative.suffix == ".pyc" or path.is_dir():
            continue
        assert path.is_file()
        files[relative.as_posix()] = path.read_bytes()
    return files


class _FormalPopulationTracingProtocol(ExperimentProtocol):
    """Use the real formal selectors and gates without running solver processes."""

    def __init__(
        self,
        *,
        config: ProtocolConfig,
        split: SplitManifest,
        seeds: SeedLedgerConfig,
        metrics_dir: Path,
    ) -> None:
        super().__init__(
            protocol_config=config,
            split_manager=SplitManager(split),
            seed_ledger=SeedLedger(seeds),
            runner=object(),
            metrics_dir=str(metrics_dir),
            adapter=protocol_test_adapter(
                (
                    ObjectiveMetricSpec(
                        name="total_distance",
                        direction="minimize",
                        priority=1,
                    ),
                )
            ),
        )
        self.calls: list[dict[str, Any]] = []

    def run_canary(
        self,
        candidate_ws: str,
        champion_ws: str,
        *,
        selected_surface: str | None = None,
    ) -> CanaryResult:
        del candidate_ws, champion_ws, selected_surface
        return CanaryResult(passed=True)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
        selected_surface: str | None = None,
        **_kwargs: Any,
    ) -> ProtocolResult:
        cases = self._select_cases(
            stage,
            hypothesis_action,
            expand_round if expand else 0,
        )
        seeds = self._select_seeds(stage, expanded=expand)
        n_cases = len(cases)
        wins = n_cases * 3 // 4
        pair_feedback = tuple(
            PairwiseCaseFeedback(
                case_id=case,
                seed=seed,
                comparison="win" if case_index < wins else "tie",
                delta=10.0 if case_index < wins else 0.0,
            )
            for case_index, case in enumerate(cases)
            for seed in seeds
        )
        stats = EvalStats(
            n_cases=n_cases,
            wins=wins,
            losses=0,
            ties=n_cases - wins,
            win_rate=wins / n_cases,
            median_delta=10.0,
            ci_low=5.0,
            ci_high=15.0,
            total_pairs=n_cases * len(seeds),
            attempted_pairs=n_cases * len(seeds),
            valid_pairs=n_cases * len(seeds),
            pair_wins=wins * len(seeds),
            pair_ties=(n_cases - wins) * len(seeds),
        )
        gate = (
            screening_gate(stats, self.config, expanded=expand)
            if stage is ExperimentStage.SCREENING
            else validation_gate(stats, self.config, expanded=expand)
        )
        candidate_source = (
            Path(candidate_ws) / "operators" / "local_search.py"
        ).read_bytes()
        self.calls.append(
            {
                "stage": stage,
                "expand": expand,
                "expand_round": expand_round,
                "hypothesis_action": hypothesis_action,
                "candidate_ws": candidate_ws,
                "champion_ws": champion_ws,
                "selected_surface": selected_surface,
                "candidate_source": candidate_source,
                "cases": tuple(cases),
                "seeds": tuple(seeds),
                "gate_outcome": gate.outcome,
                "reason_codes": gate.reason_codes,
                "proposal_subject": _kwargs.get("proposal_subject"),
            }
        )
        return ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome=gate.outcome,
            reason_codes=gate.reason_codes,
            exposed_summary=f"stage={stage.value} outcome={gate.outcome}",
            raw_metrics_ref=str(Path(self.metrics_dir) / f"{len(self.calls)}.json"),
            case_ids=tuple(cases),
            seed_set=tuple(seeds),
            pair_feedback=pair_feedback,
            selected_surface=selected_surface,
            case_aggregation_method=self.config.case_aggregation,
            case_effect_metric=self.config.effect_metric,
            case_equivalence_band=self.config.case_equivalence_band,
        )


def test_formal_screening_expansion_reuses_exact_candidate_then_enters_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = ProtocolConfig.from_yaml(_FORMAL_DIR / "protocol.yaml")
    split = SplitManifest.from_yaml(_FORMAL_DIR / "split_manifest.yaml")
    seeds = SeedLedgerConfig.from_yaml(_FORMAL_DIR / "seed_ledger.yaml")
    protocol = _FormalPopulationTracingProtocol(
        config=config,
        split=split,
        seeds=seeds,
        metrics_dir=tmp_path / "metrics",
    )
    provider = MockLLMClient(
        hypothesis_response=_VALID_HYPOTHESIS,
        patch_response=_VALID_PATCH,
    )
    campaign = _campaign(
        tmp_path,
        llm_client=provider,
        experiment_protocol=protocol,
    )

    candidate_workspace_creations: list[str] = []
    create_candidate_workspace = campaign._materializer.create_candidate_workspace

    def capture_candidate_workspace(*args, **kwargs):
        workspace = create_candidate_workspace(*args, **kwargs)
        candidate_workspace_creations.append(workspace)
        return workspace

    monkeypatch.setattr(
        campaign._materializer,
        "create_candidate_workspace",
        capture_candidate_workspace,
    )

    initial = campaign.run_one_step()
    branch_id = initial.branch_id
    branch = campaign._branch_ctrl.get_branch(branch_id)
    hypothesis = branch.hypothesis
    assert hypothesis is not None

    assert initial.decision is Decision.EXPAND_SCREENING
    assert branch.state is BranchState.EXPLORE_EXPAND
    assert provider.call_count == 2
    assert len(candidate_workspace_creations) == 1
    assert protocol.calls[0]["gate_outcome"] == "expand"
    assert protocol.calls[0]["reason_codes"] == ("SCREENING_EXPAND_REQUIRED_FOR_PASS",)

    expanded = campaign.run_one_step()
    branch = campaign._branch_ctrl.get_branch(branch_id)

    assert expanded.branch_id == branch_id
    assert expanded.decision is Decision.QUEUE_VALIDATE
    assert branch.state is BranchState.READY_VALIDATE
    assert branch.screening_expand_count == 1
    assert provider.call_count == 2
    assert len(candidate_workspace_creations) == 1
    assert branch.hypothesis == hypothesis
    assert protocol.calls[1]["gate_outcome"] == "pass"
    assert protocol.calls[1]["reason_codes"] == ("SCREENING_PASS",)
    assert protocol.calls[1]["expand"] is True
    assert protocol.calls[1]["expand_round"] == 1
    assert (
        protocol.calls[1]["candidate_source"] == protocol.calls[0]["candidate_source"]
    )
    assert protocol.calls[1]["candidate_ws"] == protocol.calls[0]["candidate_ws"]
    initial_subject = protocol.calls[0]["proposal_subject"]
    expanded_subject = protocol.calls[1]["proposal_subject"]
    assert initial_subject == expanded_subject
    assert set(initial_subject) == {"schema_version", "changes"}
    assert initial_subject["schema_version"] == "scion.problem_proposal_subject.v1"
    assert len(initial_subject["changes"]) == 1
    subject_change = initial_subject["changes"][0]
    assert set(subject_change) == {
        "file_path",
        "action",
        "before_source",
        "after_source",
    }
    assert subject_change["file_path"] == _VALID_PATCH["file_path"]
    assert subject_change["action"] == "modify"
    assert subject_change["before_source"] != subject_change["after_source"]
    assert subject_change["before_source"] == branch.accepted_changes[-1].before_sources[
        0
    ].source
    assert subject_change["before_source"] == (
        Path(campaign._champion.code_snapshot_path) / _VALID_PATCH["file_path"]
    ).read_text(encoding="utf-8")
    assert subject_change["after_source"].encode("utf-8") == protocol.calls[0][
        "candidate_source"
    ]
    subject_keys = set(initial_subject) | set(subject_change)
    assert subject_keys.isdisjoint(
        {"digest", "hash", "identity", "lease", "receipt", "registry", "signature"}
    )
    durable_candidate = Path(campaign._branch_workspaces[branch_id]).resolve()
    candidate_root = Path(campaign._campaign_dir) / "candidate_workspaces"
    candidate_children = sorted(path.resolve() for path in candidate_root.iterdir())
    assert candidate_children == [durable_candidate]
    assert durable_candidate.is_dir() and not durable_candidate.is_symlink()
    assert Path(protocol.calls[1]["candidate_ws"]).resolve() == durable_candidate
    assert hypothesis.action == "modify"
    baseline_source = _ordinary_source_bytes(
        Path(campaign._champion.code_snapshot_path)
    )
    candidate_source = _ordinary_source_bytes(durable_candidate)
    assert set(baseline_source) == set(candidate_source)
    assert [
        path
        for path in baseline_source
        if baseline_source[path] != candidate_source[path]
    ] == [_VALID_PATCH["file_path"]]
    assert branch.current_code_hash is not None
    assert branch.current_code_hash == campaign._materializer.compute_code_hash(
        str(durable_candidate)
    )

    expected_initial_cases = tuple(
        select_cases(
            config=config,
            split_manager=SplitManager(split),
            stage=ExperimentStage.SCREENING,
            hypothesis_action="modify",
            expand_round=0,
        )
    )
    expected_expanded_cases = tuple(
        select_cases(
            config=config,
            split_manager=SplitManager(split),
            stage=ExperimentStage.SCREENING,
            hypothesis_action="modify",
            expand_round=1,
        )
    )
    assert protocol.calls[0]["cases"] == expected_initial_cases
    assert protocol.calls[0]["seeds"] == tuple(seeds.screening[:4])
    assert protocol.calls[1]["cases"] == expected_expanded_cases
    assert protocol.calls[1]["seeds"] == tuple(seeds.screening[:8])
    assert len(expected_initial_cases) == 8
    assert len(expected_expanded_cases) == 12
    assert set(expected_initial_cases) < set(expected_expanded_cases)

    validation = campaign.run_one_step()
    branch = campaign._branch_ctrl.get_branch(branch_id)

    assert validation.branch_id == branch_id
    assert validation.decision is Decision.QUEUE_FROZEN
    assert branch.state is BranchState.READY_FROZEN
    assert provider.call_count == 2
    assert len(candidate_workspace_creations) == 1
    assert [call["stage"] for call in protocol.calls] == [
        ExperimentStage.SCREENING,
        ExperimentStage.SCREENING,
        ExperimentStage.VALIDATION,
    ]
    assert protocol.calls[2]["cases"] == tuple(split.validation)
    assert protocol.calls[2]["seeds"] == tuple(seeds.validation)
    assert len(protocol.calls[2]["cases"]) == 12
    assert (
        protocol.calls[2]["candidate_source"] == protocol.calls[0]["candidate_source"]
    )
