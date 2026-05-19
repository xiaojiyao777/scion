"""Focused tests split from test_sprint_e2.py."""

from .sprint_e2_test_support import *  # noqa: F401,F403

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
