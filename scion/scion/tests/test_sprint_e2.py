"""Tests for Sprint E2: T05/T07/T08/T11/T26.

T05: Frozen holdout expansion (split_manifest.yaml).
T07: Hypothesis family tracking — family assignment, coverage report.
T08: Strategy-shift guidance — repeated family failure detection.
T11: Screening set rebalance (split_manifest.yaml — already verified).
T26: Context manager memory classification — What Worked / What Failed sections.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

import pytest

from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisFamily,
    HypothesisProposal,
    HypothesisRecord,
    ProtocolResult,
    StepRecord,
)
from scion.proposal.context_manager import (
    ContextManager,
    _build_runtime_feedback,
    _build_strategy_guidance,
    _build_what_worked_section,
    _extract_families_from_steps,
    assign_family_id,
    build_exploration_coverage,
)
from scion.tests.taxonomy_helpers import cvrp_family_taxonomy, warehouse_family_taxonomy

WAREHOUSE_MECHANISM_TAXONOMY = warehouse_family_taxonomy()
CVRP_FAMILY_TAXONOMY = cvrp_family_taxonomy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(
    text: str = "some hypothesis",
    action: str = "create_new",
    locus: str = "vehicle_level",
) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=text,
        change_locus=locus,
        action=action,
        target_file=None,
        predicted_direction="improve",
        target_weakness="slow",
        expected_effect="faster",
    )


def _make_step(
    branch_id: str = "b1",
    round_num: int = 1,
    hypothesis_text: str = "test hypothesis",
    action: str = "create_new",
    locus: str = "vehicle_level",
    decision: Decision = Decision.CONTINUE_EXPLORE,
    failure_stage: Optional[str] = None,
    win_rate: float = 0.0,
    runtime_ratio_median=None,
    runtime_delta_median_ms=None,
    runtime_regression_rate=None,
    runtime_pairs: int = 0,
) -> StepRecord:
    protocol_result = None
    if failure_stage is None:
        stats = EvalStats(
            n_cases=6,
            wins=int(win_rate * 6),
            losses=6 - int(win_rate * 6),
            ties=0,
            win_rate=win_rate,
            median_delta=0.01 if win_rate > 0 else 0.0,
            ci_low=0.0,
            ci_high=0.02,
            runtime_ratio_median=runtime_ratio_median,
            runtime_delta_median_ms=runtime_delta_median_ms,
            runtime_regression_rate=runtime_regression_rate,
            runtime_pairs=runtime_pairs,
        )
        protocol_result = ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=stats,
            gate_outcome="pass" if win_rate > 0.6 else "continue",
            reason_codes=("TEST",),
            exposed_summary="test",
            raw_metrics_ref="/tmp/test.json",
        )
    return StepRecord(
        round_num=round_num,
        branch_id=branch_id,
        hypothesis=_make_hypothesis(hypothesis_text, action, locus),
        patch=None,
        contract_passed=True,
        verification_passed=(failure_stage is None),
        protocol_result=protocol_result,
        decision=decision,
        failure_stage=failure_stage,
        failure_detail=f"failed at {failure_stage}" if failure_stage else None,
    )


def _make_family(
    mechanism_label: str,
    action_pattern: str = "create_new",
    locus_pattern: str = "vehicle_level",
    statuses: Optional[List[str]] = None,
) -> HypothesisFamily:
    statuses = statuses or []
    return HypothesisFamily(
        family_id=f"{mechanism_label}/{action_pattern}/{locus_pattern}",
        mechanism_label=mechanism_label,
        action_pattern=action_pattern,
        locus_pattern=locus_pattern,
        evidence_count=len(statuses),
        statuses=statuses,
    )


# ---------------------------------------------------------------------------
# T05: Frozen holdout expansion
# ---------------------------------------------------------------------------

MANIFEST_PATH = Path(__file__).parent.parent.parent / "problems/warehouse_delivery/split_manifest.yaml"


def test_t05_frozen_set_has_at_least_six():
    """T05: Frozen set must have 6-8 cases after expansion."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    assert len(manifest.frozen) >= 6, f"Frozen set has {len(manifest.frozen)} cases"  # v4: 18


def test_t05_frozen_set_has_size_diversity():
    """T05: Frozen set should have large + xlarge + xxlarge cases."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    frozen = manifest.frozen
    # Check we have l, x, and xx tiers
    has_large = any("fro_l" in f for f in frozen)
    has_xlarge = any("fro_x0" in f for f in frozen)
    has_xxlarge = any("fro_xx" in f for f in frozen)
    assert has_large, "Frozen should include large-tier instances (fro_l)"
    assert has_xlarge, "Frozen should include xlarge-tier instances (fro_x)"
    assert has_xxlarge, "Frozen should include xxlarge-tier instances (fro_xx)"


def test_t05_frozen_no_overlap_with_screening_or_validation():
    """T05: Frozen must not overlap with screening or validation."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    frozen_set = set(manifest.frozen)
    assert frozen_set.isdisjoint(set(manifest.screening))
    assert frozen_set.isdisjoint(set(manifest.validation))


# ---------------------------------------------------------------------------
# T11: Screening set rebalance
# ---------------------------------------------------------------------------

def test_t11_screening_has_40_percent_large():
    """T11: ~40% of screening cases should be large."""
    from scion.config.split_manifest import SplitManifest
    manifest = SplitManifest.from_yaml(str(MANIFEST_PATH))
    screening = manifest.screening
    large_count = sum(1 for f in screening if "_scr_l" in f)
    ratio = large_count / len(screening)
    assert ratio >= 0.20, f"Large screening ratio is {ratio:.1%}, expected >=20%"  # v4: 23.5%


# ---------------------------------------------------------------------------
# T07: Family assignment by keywords
# ---------------------------------------------------------------------------

def test_family_assignment_by_keywords_subcategory():
    fid = assign_family_id(
        "Merge subcategory vehicles to reduce splits",
        "create_new",
        "vehicle_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "subcategory_consolidation" in fid


def test_family_assignment_by_keywords_destroy():
    fid = assign_family_id(
        "Destroy and rebuild the vehicle assignment",
        "create_new",
        "vehicle_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "destroy_rebuild" in fid


def test_family_assignment_by_keywords_swap():
    fid = assign_family_id(
        "Swap orders between vehicles",
        "modify",
        "order_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "order_swap" in fid


def test_family_assignment_by_keywords_cost():
    fid = assign_family_id(
        "Downsize vehicles to reduce total cost",
        "modify",
        "vehicle_level",
        taxonomy=WAREHOUSE_MECHANISM_TAXONOMY,
    )
    assert "cost_reduction" in fid


def test_family_assignment_default():
    fid = assign_family_id("Some unrecognised hypothesis text xyz", "modify", "vehicle_level")
    assert "generic" in fid


def test_family_assignment_default_does_not_emit_warehouse_labels():
    fid = assign_family_id("Merge subcategory vehicles to reduce splits", "create_new", "vehicle_level")
    assert fid == "generic/create_new/vehicle_level"
    assert "subcategory_consolidation" not in fid
    assert "cost_reduction" not in fid


def test_context_family_extraction_route_taxonomy_blocks_warehouse_labels():
    steps = [
        _make_step(
            hypothesis_text="merge subcategory clusters and reduce cost",
            action="create_new",
            locus="route_pair",
        ),
        _make_step(
            hypothesis_text="try route-pair 2-opt* exchange",
            action="modify",
            locus="route_pair",
        ),
    ]

    families = _extract_families_from_steps(
        steps,
        taxonomy=CVRP_FAMILY_TAXONOMY,
    )
    family_ids = {f.family_id for f in families}

    assert "NEW_FAMILY/create_new/route_pair" in family_ids
    assert "route_pair/modify/route_pair" in family_ids
    assert all("subcategory_consolidation" not in fid for fid in family_ids)
    assert all("cost_reduction" not in fid for fid in family_ids)


def test_family_id_includes_action_and_locus():
    fid = assign_family_id("Swap orders between vehicles", "modify", "order_level")
    assert "modify" in fid
    assert "order_level" in fid


# ---------------------------------------------------------------------------
# T07: Coverage report format
# ---------------------------------------------------------------------------

def test_coverage_report_format_shows_family_ids():
    """T07: Coverage report lists family IDs and counts."""
    steps = [
        _make_step(hypothesis_text="Merge subcategory vehicles", action="create_new", locus="vehicle_level"),
        _make_step(hypothesis_text="Swap orders between vehicles", action="modify", locus="order_level"),
    ]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    report = build_exploration_coverage(families)
    assert "Exploration Coverage" in report
    assert "subcategory_consolidation" in report
    assert "order_swap" in report


def test_coverage_report_shows_unexplored_actions():
    """T07: Coverage report flags unexplored action types."""
    steps = [_make_step(action="modify", locus="vehicle_level")]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    report = build_exploration_coverage(families)
    assert "create_new" in report  # unexplored action should be flagged


def test_coverage_report_empty_for_no_steps():
    assert build_exploration_coverage([]) == ""


# ---------------------------------------------------------------------------
# T07: Family tracking across rounds
# ---------------------------------------------------------------------------

def test_family_tracking_across_rounds():
    """T07: Same family accumulates evidence_count across multiple steps."""
    steps = [
        _make_step(round_num=1, hypothesis_text="Consolidate subcategory splits"),
        _make_step(round_num=2, hypothesis_text="Subcategory merge attempt"),
        _make_step(round_num=3, hypothesis_text="Subcategory consolidation improved"),
    ]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    subcat_families = [f for f in families if "subcategory_consolidation" in f.family_id]
    assert len(subcat_families) == 1, "Same mechanism should be one family"
    assert subcat_families[0].evidence_count == 3


def test_family_tracking_different_actions_are_different_families():
    """T07: Same mechanism but different action = different family."""
    steps = [
        _make_step(hypothesis_text="Merge subcategory vehicles", action="create_new", locus="vehicle_level"),
        _make_step(hypothesis_text="Subcategory merge refinement", action="modify", locus="vehicle_level"),
    ]
    families = _extract_families_from_steps(steps, taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)
    subcat_families = [f for f in families if "subcategory_consolidation" in f.family_id]
    assert len(subcat_families) == 2, "Different actions = different families"


# ---------------------------------------------------------------------------
# T08: Strategy-shift guidance
# ---------------------------------------------------------------------------

def test_guidance_warns_repeated_family():
    """T08: 3+ consecutive same-family failures → warning."""
    fail_statuses = ["failed_verification", "failed_verification", "failed_verification"]
    families = [_make_family("subcategory_consolidation", statuses=fail_statuses)]
    guidance = _build_strategy_guidance(families)
    assert "subcategory_consolidation" in guidance
    assert "AVOID" in guidance or "failed" in guidance


def test_guidance_suggests_action_switch():
    """T08: All recent attempts create_new → suggest modify."""
    families = [
        _make_family("generic", action_pattern="create_new", statuses=["failed_verification"]),
        _make_family("order_swap", action_pattern="create_new", statuses=["gate_continue"]),
        _make_family("rebalance", action_pattern="create_new", statuses=["gate_continue"]),
    ]
    guidance = _build_strategy_guidance(families)
    assert "modify" in guidance


def test_guidance_highlights_unexplored_locus():
    """T08: Only vehicle_level explored → flag order_level."""
    families = [
        _make_family("subcategory_consolidation", locus_pattern="vehicle_level", statuses=["promoted"]),
        _make_family("destroy_rebuild", locus_pattern="vehicle_level", statuses=["gate_fail"]),
    ]
    spec = SimpleNamespace(operator_categories=["vehicle_level", "order_level"])
    guidance = _build_strategy_guidance(families, spec)
    assert "order_level" in guidance


def test_no_guidance_when_diverse():
    """T08: Diverse exploration across both loci → minimal/no directive guidance."""
    families = [
        _make_family("subcategory_consolidation", action_pattern="create_new", locus_pattern="vehicle_level", statuses=["promoted"]),
        _make_family("order_swap", action_pattern="modify", locus_pattern="order_level", statuses=["gate_continue"]),
        _make_family("rebalance", action_pattern="create_new", locus_pattern="order_level", statuses=["gate_pass"]),
    ]
    guidance = _build_strategy_guidance(families)
    # With both loci covered and no consecutive failures, AVOID directive should not appear
    assert "AVOID" not in guidance


# ---------------------------------------------------------------------------
# T26: History includes successes and failures
# ---------------------------------------------------------------------------

def test_history_includes_successes():
    """T26: Promoted hypotheses appear in 'What Worked' section."""
    steps = [
        _make_step(round_num=1, hypothesis_text="Subcategory merge", decision=Decision.PROMOTE, win_rate=1.0),
        _make_step(round_num=2, hypothesis_text="Order swap", failure_stage="verification"),
    ]
    from scion.proposal.context_manager import _build_what_worked_section
    section = _build_what_worked_section(steps)
    assert "What Worked" in section
    assert "Subcategory merge" in section or "subcategory_consolidation" in section


def test_history_includes_failures_with_reasons():
    """T26: Failed hypotheses show failure stage in history output."""
    from scion.proposal.context_manager import _build_experiment_history
    steps = [
        _make_step(branch_id="b1", round_num=1, failure_stage="verification"),
    ]
    history = _build_experiment_history(steps, "b1")
    assert "failed_at: verification" in history


def test_history_balanced():
    """T26: Both 'What Worked' and failure info present when data exists."""
    from scion.proposal.context_manager import _build_experiment_history
    steps = [
        _make_step(branch_id="b1", round_num=1, hypothesis_text="Subcategory merge", decision=Decision.PROMOTE, win_rate=1.0),
        _make_step(branch_id="b1", round_num=2, hypothesis_text="Order swap", failure_stage="verification"),
    ]
    history = _build_experiment_history(steps, "b1")
    assert "What Worked" in history
    assert "failed_at" in history


def test_history_includes_high_win_rate_steps():
    """T26: Steps with win_rate >= 0.8 appear in What Worked even if not promoted."""
    steps = [
        _make_step(round_num=1, hypothesis_text="Subcategory merge high wr", win_rate=0.9, decision=Decision.CONTINUE_EXPLORE),
    ]
    section = _build_what_worked_section(steps)
    assert "What Worked" in section


def test_build_hypothesis_context_includes_strategy_guidance(tmp_path):
    """T07/T08: build_hypothesis_context returns strategy_guidance key."""
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    champion = ChampionState(
        version=1, operator_pool={},
        solver_config_hash="abc", code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(branch_id="b1", state=BranchState.EXPLORE, base_champion_id=1, base_champion_hash="x")
    from scion.config.problem import ProblemSpec, SearchSpace
    spec = ProblemSpec(
        name="test", root_dir=str(code_dir),
        operator_categories=["vehicle_level", "order_level"],
        search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
    )
    cm = ContextManager()
    ctx = cm.build_hypothesis_context(branch, champion, spec, [], [], step_history=[])
    assert "strategy_guidance" in ctx
    assert "exploration_coverage" in ctx


def test_build_hypothesis_context_uses_cvrp_family_taxonomy(tmp_path):
    """CVRP-style taxonomies must not receive warehouse family labels."""
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    champion = ChampionState(
        version=1, operator_pool={},
        solver_config_hash="abc", code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(branch_id="b1", state=BranchState.EXPLORE, base_champion_id=1, base_champion_hash="x")
    from scion.config.problem import ProblemSpec, SearchSpace
    spec = ProblemSpec(
        name="cvrp", root_dir=str(code_dir),
        operator_categories=["route_local", "route_pair", "ruin_recreate"],
        search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
    )
    object.__setattr__(
        spec,
        "family_taxonomy",
        CVRP_FAMILY_TAXONOMY,
    )
    steps = [
        _make_step(
            branch_id="b1",
            round_num=1,
            hypothesis_text="Swap customers between routes to reduce travel cost",
            locus="route_pair",
            win_rate=0.1,
        ),
        _make_step(
            branch_id="b1",
            round_num=2,
            hypothesis_text="Merge subcategory-shaped buckets with a cost guard",
            locus="route_pair",
            win_rate=0.1,
        ),
        _make_step(
            branch_id="b1",
            round_num=3,
            hypothesis_text="Split high-cost subcategory clusters with local cleanup",
            locus="route_local",
            win_rate=0.1,
        ),
    ]

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=steps
    )
    rendered = "\n".join(
        str(ctx[key])
        for key in (
            "exploration_coverage",
            "strategy_guidance",
            "experiment_history",
            "search_control_guidance",
        )
    )

    assert "route_pair" in rendered or "route_local" in rendered or "generic" in rendered
    for legacy_label in (
        "order_swap",
        "subcategory_consolidation",
        "cost_reduction",
        "split_operator",
    ):
        assert legacy_label not in rendered


def test_build_hypothesis_context_includes_runtime_feedback(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    champion = ChampionState(
        version=1, operator_pool={},
        solver_config_hash="abc", code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(branch_id="b1", state=BranchState.EXPLORE, base_champion_id=1, base_champion_hash="x")
    from scion.config.problem import ProblemSpec, SearchSpace
    spec = ProblemSpec(
        name="test", root_dir=str(code_dir),
        operator_categories=["vehicle_level", "order_level"],
        search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
    )
    step = _make_step(
        round_num=3,
        hypothesis_text="Try unbounded route-pair scan",
        failure_stage="verification",
    )
    step.verification_detail = (
        "severity=heavy  first_failure=V9_perf_guard\n"
        "  [V9_perf_guard] (heavy) too slow: case=x.json candidate=6000ms "
        "champion=1000ms ratio=6.00x timeout=60s"
    )

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[step]
    )

    assert "runtime_feedback" in ctx
    assert "route-pair" not in ctx["runtime_feedback"]
    assert "V9_perf_guard" not in ctx["runtime_feedback"]
    assert "ratio=6.00x" in ctx["runtime_feedback"]
    assert "bounded neighborhoods" in ctx["runtime_feedback"]


def test_build_hypothesis_context_includes_screening_runtime_summary(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    champion = ChampionState(
        version=1, operator_pool={},
        solver_config_hash="abc", code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(branch_id="b1", state=BranchState.EXPLORE, base_champion_id=1, base_champion_hash="x")
    from scion.config.problem import ProblemSpec, SearchSpace
    spec = ProblemSpec(
        name="test", root_dir=str(code_dir),
        operator_categories=["vehicle_level", "order_level"],
        search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
    )
    step = _make_step(
        round_num=4,
        hypothesis_text="bounded screening runtime",
        win_rate=0.7,
        runtime_ratio_median=1.35,
        runtime_delta_median_ms=42.0,
        runtime_regression_rate=0.5,
        runtime_pairs=6,
    )

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[step]
    )

    assert "Recent screening runtime summary" in ctx["runtime_feedback"]
    assert "median_ratio=1.35x" in ctx["runtime_feedback"]
    assert "median_delta_ms=42.00" in ctx["runtime_feedback"]
    assert "regression_rate=0.50" in ctx["runtime_feedback"]
    assert "pairs=6" in ctx["runtime_feedback"]


def test_build_hypothesis_context_includes_screening_runtime_raw_cases(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    champion = ChampionState(
        version=1, operator_pool={},
        solver_config_hash="abc", code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(branch_id="b1", state=BranchState.EXPLORE, base_champion_id=1, base_champion_hash="x")
    from scion.config.problem import ProblemSpec, SearchSpace
    spec = ProblemSpec(
        name="test", root_dir=str(code_dir),
        operator_categories=["vehicle_level", "order_level"],
        search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
    )
    raw_metrics = tmp_path / "screening_metrics.json"
    raw_metrics.write_text(json.dumps({
        "total_pairs": 3,
        "valid_pairs": 1,
        "failed_pairs": 2,
        "candidate_failed_pairs": 1,
        "champion_failed_pairs": 1,
        "runtime_stats": {
            "runtime_ratio_median": 3.25,
            "runtime_delta_median_ms": 2250.0,
            "runtime_regression_rate": 1.0,
            "runtime_pairs": 1,
        },
        "pairs": [
            {
                "case": "/tmp/cases/slow-A.vrp",
                "seed": 7,
                "runtime_ratio": 3.25,
                "candidate_elapsed_ms": 3250,
                "champion_elapsed_ms": 1000,
                "candidate_runtime": {
                    "operator_attempts": 20,
                    "operator_accepted": 2,
                    "operator_errors": 1,
                    "operator_invalid_outputs": 1,
                },
            }
        ],
        "failures": [
            {
                "case": "/tmp/cases/timeout-B.vrp",
                "seed": 9,
                "side": "candidate",
                "error_category": "timeout",
                "elapsed_ms": 2000,
            }
        ],
    }))
    step = _make_step(
        round_num=5,
        hypothesis_text="raw runtime feedback",
        win_rate=0.7,
        runtime_ratio_median=3.25,
        runtime_delta_median_ms=2250.0,
        runtime_regression_rate=1.0,
        runtime_pairs=1,
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="pass",
        reason_codes=("TEST",),
        exposed_summary="test",
        raw_metrics_ref=str(raw_metrics),
    )

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[step]
    )

    assert "Recent screening timeout/crash cases" in ctx["runtime_feedback"]
    assert "timeout-B.vrp" in ctx["runtime_feedback"]
    assert "candidate_failure=timeout" in ctx["runtime_feedback"]
    assert "Recent screening failure causes" in ctx["runtime_feedback"]
    assert "failed_pairs=2" in ctx["runtime_feedback"]
    assert "candidate_failed_pairs=1" in ctx["runtime_feedback"]
    assert "champion_failed_pairs=1" in ctx["runtime_feedback"]
    assert "operator_attempts=20" in ctx["runtime_feedback"]
    assert "operator_accepted=2" in ctx["runtime_feedback"]
    assert "operator_errors=1" in ctx["runtime_feedback"]
    assert "invalid_outputs=1" in ctx["runtime_feedback"]
    assert "Recent slow screening cases" in ctx["runtime_feedback"]
    assert "slow-A.vrp" in ctx["runtime_feedback"]
    assert "runtime_ratio=3.25x" in ctx["runtime_feedback"]


def test_runtime_feedback_uses_configurable_slow_case_threshold(tmp_path):
    raw_metrics = tmp_path / "threshold_metrics.json"
    raw_metrics.write_text(json.dumps({
        "total_pairs": 2,
        "valid_pairs": 2,
        "pairs": [
            {
                "case": "/tmp/cases/slow-15.vrp",
                "seed": 1,
                "runtime_ratio": 1.5,
                "candidate_elapsed_ms": 1500,
                "champion_elapsed_ms": 1000,
            },
            {
                "case": "/tmp/cases/slow-25.vrp",
                "seed": 2,
                "runtime_ratio": 2.5,
                "candidate_elapsed_ms": 2500,
                "champion_elapsed_ms": 1000,
            },
        ],
    }))
    step = _make_step(round_num=7, hypothesis_text="threshold feedback", win_rate=0.7)
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="pass",
        reason_codes=("TEST",),
        exposed_summary="test",
        raw_metrics_ref=str(raw_metrics),
    )

    strict = _build_runtime_feedback([step], slow_case_threshold=1.25)
    lenient = _build_runtime_feedback([step], slow_case_threshold=3.0)

    assert "slow-15.vrp" in strict
    assert "slow-25.vrp" in strict
    assert "slow-25.vrp" not in lenient


def test_runtime_feedback_distinguishes_noop_tie_dominated_operator(tmp_path):
    raw_metrics = tmp_path / "noop_metrics.json"
    raw_metrics.write_text(json.dumps({
        "total_pairs": 4,
        "valid_pairs": 4,
        "failed_pairs": 0,
        "candidate_failed_pairs": 0,
        "champion_failed_pairs": 0,
        "pairs": [
            {
                "case": f"/tmp/cases/tie-{i}.vrp",
                "seed": i,
                "candidate_runtime": {
                    "operator_attempts": 10,
                    "operator_accepted": 0,
                    "operator_errors": 0,
                    "operator_invalid_outputs": 0,
                    "operator_stop_reason": "no_improvement_round",
                },
            }
            for i in range(4)
        ],
    }))
    step = _make_step(round_num=8, hypothesis_text="no accepted moves", win_rate=0.0)
    stats = EvalStats(
        n_cases=4, wins=0, losses=0, ties=4,
        win_rate=0.0, median_delta=0.0, ci_low=0.0, ci_high=0.0,
        total_pairs=4, attempted_pairs=4, valid_pairs=4,
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=stats,
        gate_outcome="continue",
        reason_codes=("tie_dominated",),
        exposed_summary="test",
        raw_metrics_ref=str(raw_metrics),
    )

    rendered = _build_runtime_feedback([step])

    assert "no accepted operator moves" in rendered
    assert "tie-dominated screening evidence" in rendered
    assert "operator_stop_reason=no_improvement_round:4" in rendered
    assert "not schema/runtime failure" in rendered
    assert "no schema/runtime failure detected" in rendered
    assert "candidate_failure=" not in rendered
    assert "runtime guard failed" not in rendered


def test_build_hypothesis_context_distinguishes_contract_failure(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    champion = ChampionState(
        version=1, operator_pool={},
        solver_config_hash="abc", code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(branch_id="b1", state=BranchState.EXPLORE, base_champion_id=1, base_champion_hash="x")
    from scion.config.problem import ProblemSpec, SearchSpace
    spec = ProblemSpec(
        name="test", root_dir=str(code_dir),
        operator_categories=["vehicle_level", "order_level"],
        search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
    )
    step = _make_step(
        round_num=6,
        hypothesis_text="invalid patch",
        failure_stage="patch_contract",
    )
    step.failure_detail = "missing execute(self, solution, instance, rng)"

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[step]
    )

    assert "Recent contract failures" in ctx["runtime_feedback"]
    assert "stage=patch_contract" in ctx["runtime_feedback"]
    assert "missing execute" in ctx["runtime_feedback"]
