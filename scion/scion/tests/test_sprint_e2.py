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

from scion.config.problem import ProblemSpec, SearchSpace
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
    _build_runtime_failure_guidance,
    _build_strategy_guidance,
    _build_what_worked_section,
    _extract_families_from_steps,
    assign_family_id,
    build_exploration_coverage,
)
from scion.proposal.engine import _split_hypothesis_context
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
    protocol_stage: ExperimentStage = ExperimentStage.SCREENING,
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
            stage=protocol_stage,
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


def test_context_family_extraction_handles_prior_failed_family_mentions():
    steps = [
        _make_step(
            hypothesis_text=(
                "Implement a 2-opt intra-route local search operator that "
                "reverses route segments when distance decreases."
            ),
            action="create_new",
            locus="route_local",
        ),
        _make_step(
            hypothesis_text=(
                "Implement an Or-opt inter-route relocation operator. Unlike "
                "the previously attempted intra-route 2-opt, this targets "
                "cross-route distance reduction."
            ),
            action="create_new",
            locus="route_pair",
        ),
        _make_step(
            hypothesis_text=(
                "Implement a ruin-and-recreate segment ruin strategy. This "
                "differs from the failed intra-route 2-opt and inter-route "
                "single-node relocation by rebuilding a cluster."
            ),
            action="create_new",
            locus="ruin_recreate",
        ),
        _make_step(
            hypothesis_text=(
                "Implement a 3-opt segment move that relocates chains from "
                "one route to another route rather than single nodes."
            ),
            action="create_new",
            locus="route_pair",
        ),
    ]

    families = _extract_families_from_steps(steps, taxonomy=CVRP_FAMILY_TAXONOMY)
    counts = {fam.mechanism_label: fam.evidence_count for fam in families}

    assert counts == {
        "route_local": 1,
        "route_pair": 2,
        "ruin_recreate": 1,
    }


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


def test_coverage_report_respects_available_actions():
    steps = [_make_step(action="create_new", locus="route_local")]
    families = _extract_families_from_steps(steps, taxonomy=CVRP_FAMILY_TAXONOMY)

    report = build_exploration_coverage(families, available_actions={"create_new"})

    assert "modify" not in report
    assert "remove" not in report


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


def test_guidance_does_not_suggest_modify_without_target_operator():
    """T08: Empty champion operator pool should not push invalid modify/remove."""
    families = [
        _make_family("generic", action_pattern="create_new", statuses=["gate_fail"]),
        _make_family("route_pair", action_pattern="create_new", statuses=["gate_fail"]),
        _make_family("ruin_recreate", action_pattern="create_new", statuses=["gate_fail"]),
    ]

    guidance = _build_strategy_guidance(families, available_actions={"create_new"})

    assert "action='modify'" not in guidance
    assert "no champion operator file" in guidance


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
    """T26: Screening-derived successes appear in 'What Worked' section."""
    steps = [
        _make_step(round_num=1, hypothesis_text="Subcategory merge", win_rate=1.0),
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
    """T26: Hypothesis history balances allowed screening wins and pre-protocol failures."""
    from scion.proposal.context_manager import _build_experiment_history
    steps = [
        _make_step(
            branch_id="b1",
            round_num=1,
            hypothesis_text="Screening-only success",
            win_rate=1.0,
        ),
        _make_step(
            branch_id="b1",
            round_num=2,
            hypothesis_text="Pre-protocol failure",
            failure_stage="verification",
        ),
        _make_step(
            branch_id="b1",
            round_num=3,
            hypothesis_text="Promoted step hidden from hypothesis prompt",
            decision=Decision.PROMOTE,
            win_rate=1.0,
        ),
        _make_step(
            branch_id="b1",
            round_num=4,
            hypothesis_text="Validation step hidden from hypothesis prompt",
            protocol_stage=ExperimentStage.VALIDATION,
            decision=Decision.QUEUE_FROZEN,
            win_rate=1.0,
        ),
        _make_step(
            branch_id="b1",
            round_num=5,
            hypothesis_text="Frozen step hidden from hypothesis prompt",
            protocol_stage=ExperimentStage.FROZEN,
            decision=Decision.PROMOTE,
            win_rate=1.0,
        ),
    ]
    history = _build_experiment_history(steps, "b1")
    assert "What Worked" in history
    assert "Screening-only success" in history
    assert "failed_at" in history
    assert "Pre-protocol failure" in history
    assert "Promoted step hidden from hypothesis prompt" not in history
    assert "Validation step hidden from hypothesis prompt" not in history
    assert "Frozen step hidden from hypothesis prompt" not in history
    assert "QUEUE_FROZEN" not in history
    assert "PROMOTE" not in history
    assert "VALIDATION" not in history
    assert "FROZEN" not in history


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
    assert "action='modify'" not in rendered


def test_hypothesis_prompt_hides_champion_version_from_champion_stats(tmp_path):
    code_dir = tmp_path / "code"
    op_dir = code_dir / "operators"
    op_dir.mkdir(parents=True)
    (op_dir / "baseline.py").write_text(
        "class BaselineOp:\n"
        "    def execute(self, solution, rng):\n"
        "        return solution\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=7,
        operator_pool={
            "baseline": SimpleNamespace(
                weight=0.75,
                category="route_local",
                file_path="operators/baseline.py",
            )
        },
        solver_config_hash="abc",
        code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=7,
        base_champion_hash="x",
    )
    spec = ProblemSpec(
        name="test",
        root_dir=str(code_dir),
        operator_categories=["route_local"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=[],
            import_whitelist=[],
        ),
    )

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[]
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt
    prompt_lower = prompt_text.lower()

    assert ctx["champion_version"] == 7
    assert "BaselineOp" in prompt_text
    assert "Operator pool:" in prompt_text
    assert "baseline [route_local] weight=0.75  file=operators/baseline.py" in prompt_text
    assert "Champion version: 7" not in prompt_text
    assert "version: 7" not in prompt_text
    assert "v7" not in prompt_text
    for forbidden in (
        "promotion count",
        "promotion depth",
        "promoted count",
        "last promoted",
        "champion evolution",
    ):
        assert forbidden not in prompt_lower


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


def test_build_hypothesis_context_includes_structured_runtime_summary(tmp_path):
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
        round_num=5,
        hypothesis_text="structured runtime feedback",
        win_rate=0.7,
        runtime_ratio_median=3.25,
        runtime_delta_median_ms=2250.0,
        runtime_regression_rate=1.0,
        runtime_pairs=1,
    )
    stats = EvalStats(
        n_cases=6,
        wins=4,
        losses=2,
        ties=0,
        win_rate=0.7,
        median_delta=0.01,
        ci_low=0.0,
        ci_high=0.02,
        runtime_ratio_median=3.25,
        runtime_delta_median_ms=2250.0,
        runtime_regression_rate=1.0,
        runtime_pairs=1,
        total_pairs=3,
        attempted_pairs=3,
        valid_pairs=1,
        failed_pairs=2,
        candidate_failed_pairs=1,
        champion_failed_pairs=1,
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=stats,
        gate_outcome="pass",
        reason_codes=("TEST",),
        exposed_summary="test",
        raw_metrics_ref="/tmp/secret-screening-metrics.json",
        candidate_runtime_failure_categories={
            "timeout": 1,
            "operator_error": 1,
            "invalid_output": 1,
        },
        candidate_first_runtime_failure={
            "category": "timeout",
            "code": "timeout",
            "surface": "",
            "component": "solver_process",
            "detail_summary": "candidate solver process failed",
        },
        candidate_operator_attempts=20,
        candidate_operator_accepted=2,
        candidate_operator_errors=1,
        candidate_operator_invalid_outputs=1,
    )

    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[step]
    )

    assert "Recent screening runtime failure categories" in ctx["runtime_feedback"]
    assert "candidate_failure_category=timeout" in ctx["runtime_feedback"]
    assert "Recent screening failure causes" in ctx["runtime_feedback"]
    assert "failed_pairs=2" in ctx["runtime_feedback"]
    assert "candidate_failed_pairs=1" in ctx["runtime_feedback"]
    assert "champion_failed_pairs=1" in ctx["runtime_feedback"]
    assert "operator_attempts=20" in ctx["runtime_feedback"]
    assert "operator_accepted=2" in ctx["runtime_feedback"]
    assert "operator_errors=1" in ctx["runtime_feedback"]
    assert "invalid_outputs=1" in ctx["runtime_feedback"]
    assert "secret-screening-metrics" not in ctx["runtime_feedback"]
    assert "raw_metrics_ref" not in ctx["runtime_feedback"]


def test_runtime_feedback_uses_configurable_slow_case_threshold(tmp_path):
    step = _make_step(
        round_num=7,
        hypothesis_text="threshold feedback",
        win_rate=0.7,
        runtime_ratio_median=2.5,
        runtime_delta_median_ms=1500.0,
        runtime_regression_rate=1.0,
        runtime_pairs=2,
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=step.protocol_result.stats,
        gate_outcome="pass",
        reason_codes=("TEST",),
        exposed_summary="test",
        raw_metrics_ref="/tmp/secret-threshold-metrics.json",
    )

    strict = _build_runtime_feedback([step], slow_case_threshold=1.25)
    lenient = _build_runtime_feedback([step], slow_case_threshold=3.0)

    assert "Recent screening runtime summary" in strict
    assert "median_ratio=2.50x" in strict
    assert "secret-threshold-metrics" not in strict
    assert "secret-threshold-metrics" not in lenient


def test_runtime_feedback_distinguishes_noop_tie_dominated_operator(tmp_path):
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
        raw_metrics_ref="/tmp/secret-noop-metrics.json",
        candidate_runtime_failure_categories={"no_accepted_moves": 4},
        candidate_operator_attempts=40,
        candidate_operator_accepted=0,
        candidate_runtime_stop_reasons={"no_improvement_round": 4},
    )

    rendered = _build_runtime_feedback([step])

    assert "no accepted operator moves" in rendered
    assert "tie-dominated screening evidence" in rendered
    assert "operator_stop_reason=no_improvement_round:4" in rendered
    assert "not schema/runtime failure" in rendered
    assert "no schema/runtime failure detected" in rendered
    assert "candidate_failure_category=no_accepted_moves" in rendered
    assert "secret-noop-metrics" not in rendered
    assert "runtime guard failed" not in rendered


def test_runtime_failure_guidance_uses_problem_declared_surface_names(tmp_path):
    code_dir = tmp_path / "code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "policies").mkdir(parents=True)
    spec = ProblemSpec(
        name="toy_surface_problem",
        root_dir=str(code_dir),
        operator_categories=["alpha_moves", "beta_scheduler"],
        research_surfaces=[
            SimpleNamespace(
                name="alpha_moves",
                kind="operator",
                description="arbitrary move surface",
                target_files=["operators/*.py"],
            ),
            SimpleNamespace(
                name="beta_scheduler",
                kind="policy",
                description="arbitrary scheduler surface",
                target_files=["policies/beta_scheduler.py"],
                create_new_allowed=False,
                remove_allowed=False,
            ),
        ],
        runtime_failure_guidance=[
            SimpleNamespace(
                failure_categories=["no_accepted_moves"],
                applies_to_surface_kinds=["operator"],
                min_category_fraction=0.5,
                min_count=2,
                recommended_surfaces=["beta_scheduler"],
                discouraged_surfaces=["alpha_moves"],
                guidance=(
                    "Switch to the declared scheduler surface when arbitrary "
                    "move attempts do not produce accepted moves."
                ),
            )
        ],
        search_space=SearchSpace(
            editable=["operators/*.py", "policies/*.py"],
            frozen=["solver.py"],
            import_whitelist=[],
        ),
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="abc",
        code_snapshot_path=str(code_dir),
        code_snapshot_hash="def",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="x",
    )
    step = _make_step(
        round_num=9,
        hypothesis_text="arbitrary move surface has no accepted moves",
        locus="alpha_moves",
        win_rate=0.0,
    )
    step.protocol_result = ProtocolResult(
        stage=ExperimentStage.SCREENING,
        stats=EvalStats(
            n_cases=4,
            wins=0,
            losses=0,
            ties=4,
            win_rate=0.0,
            median_delta=0.0,
            ci_low=0.0,
            ci_high=0.0,
            total_pairs=4,
            attempted_pairs=4,
            valid_pairs=4,
        ),
        gate_outcome="continue",
        reason_codes=("tie_dominated",),
        exposed_summary="test",
        raw_metrics_ref="/tmp/secret-runtime-guidance.json",
        candidate_runtime_failure_categories={"no_accepted_moves": 4},
        candidate_operator_attempts=24,
        candidate_operator_accepted=0,
    )

    rendered = _build_runtime_failure_guidance([step], problem_spec=spec)
    ctx = ContextManager().build_hypothesis_context(
        branch, champion, spec, [], [], step_history=[step]
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "beta_scheduler" in rendered
    assert "alpha_moves" in rendered
    assert "declared scheduler surface" in rendered
    assert "Runtime Failure Guidance" in prompt_text
    assert "recommended_surfaces: beta_scheduler" in prompt_text
    assert "secret-runtime-guidance" not in prompt_text
    assert "raw_metrics_ref" not in prompt_text


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
