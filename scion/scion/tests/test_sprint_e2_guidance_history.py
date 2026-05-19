"""Focused tests split from test_sprint_e2.py."""

from .sprint_e2_test_support import *  # noqa: F401,F403

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
