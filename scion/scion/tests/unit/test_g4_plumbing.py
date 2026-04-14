"""Sprint G4 tests: prompt plumbing, registry sync, CLI wiring, lineage events."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
import yaml

from scion.core.models import (
    HypothesisProposal, OperatorConfig, PatchProposal,
)
from scion.proposal.engine import _split_hypothesis_context, _split_code_context
from scion.runtime.pool_manager import PoolManager, read_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hypothesis(action: str = "modify", target_file: str = "operators/old.py",
                     locus: str = "order_level") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Test hypothesis",
        change_locus=locus,
        action=action,  # type: ignore[arg-type]
        target_file=target_file,
        predicted_direction="improve",
        target_weakness="none",
        expected_effect="better",
        suggested_weight=0.2,
    )


def _make_patch(action: str = "modify", file_path: str = "operators/old.py",
                code: str = "class Op:\n    def execute(self, s, rng): return s\n") -> PatchProposal:
    return PatchProposal(
        file_path=file_path,
        action=action,  # type: ignore[arg-type]
        code_content=code,
        test_hint=None,
    )


def _op(name: str, file_path: str, weight: float = 0.5) -> OperatorConfig:
    return OperatorConfig(name=name, file_path=file_path, category="order_level",
                          weight=weight, class_name=name.capitalize())


def _champ_pool() -> Dict[str, OperatorConfig]:
    return {
        "swap": _op("swap", "operators/swap.py", 0.6),
        "move": _op("move", "operators/move.py", 0.4),
    }


def _base_context(**overrides) -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "problem_summary": "Solve VRP",
        "champion_operators_code": "class ChampOp: pass",
        "champion_stats": "win_rate=0.5",
        "experiment_history": "no history",
        "blacklist_summary": "none",
        "sibling_summary": "none",
        "operator_categories": "['order_level']",
        "branch_code": "",
        "branch_direction": "",
        "exploration_coverage": "",
        "strategy_guidance": "",
        "champion_baselines": "",
        "hypothesis_detail": "test hyp",
        "target_file_code": "class Old: pass",
        "reference_operators": "",
        "editable_patterns": "operators/",
        "frozen_patterns": "solver.py",
        "operator_interface_spec": "def execute(self, s, rng) -> Solution",
        "import_whitelist": "math, random",
        "prior_code_failure": "",
        "original_code": "",
        "failure_detail": "",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Prompt plumbing tests
# ---------------------------------------------------------------------------

def test_hypothesis_prompt_contains_strategy_guidance():
    """strategy_guidance 非空时出现在 hypothesis prompt 中"""
    ctx = _base_context(strategy_guidance="Try focusing on route merging instead of splitting.")
    system_blocks, _user = _split_hypothesis_context(ctx)
    all_text = " ".join(b["text"] for b in system_blocks)
    assert "Strategy Guidance" in all_text
    assert "route merging" in all_text


def test_hypothesis_prompt_contains_branch_code():
    """branch_code 与 champion 不同时出现在 hypothesis prompt 中"""
    ctx = _base_context(
        branch_code="class BranchSpecificOp: pass",
        champion_operators_code="class ChampOp: pass",
    )
    system_blocks, _user = _split_hypothesis_context(ctx)
    all_text = " ".join(b["text"] for b in system_blocks)
    assert "Current Branch Code" in all_text
    assert "BranchSpecificOp" in all_text


def test_hypothesis_prompt_contains_exploration_coverage():
    """exploration_coverage 出现在 hypothesis prompt 中"""
    ctx = _base_context(exploration_coverage="order_level: 3 attempts, route_level: 0 attempts")
    system_blocks, _user = _split_hypothesis_context(ctx)
    all_text = " ".join(b["text"] for b in system_blocks)
    assert "Exploration Coverage" in all_text
    assert "order_level" in all_text


def test_code_prompt_contains_prior_failure():
    """prior_code_failure 非空时出现在 code prompt 中"""
    ctx = _base_context(prior_code_failure="SyntaxError: unexpected indent on line 5")
    _system_blocks, user_prompt = _split_code_context(ctx)
    assert "Previous Attempt Failed" in user_prompt
    assert "SyntaxError" in user_prompt
    assert "Avoid the same mistake" in user_prompt


def test_hypothesis_prompt_never_contains_validation_per_case():
    """hypothesis prompt 不含 validation/frozen per-case 数据"""
    # Even if we pass validation details in other fields, they should not appear
    # The context_manager correctly filters these; here we verify prompt doesn't
    # include any per-case validation data.
    ctx = _base_context(
        experiment_history="screening: win_rate=0.6",
        # per-case validation data should NOT be in context
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    all_text = " ".join(b["text"] for b in system_blocks) + user_prompt
    # No per-case validation data should appear
    assert "validation_per_case" not in all_text
    assert "frozen_per_case" not in all_text


def test_hypothesis_prompt_contains_branch_direction():
    """branch_direction 非空时出现在 hypothesis prompt system blocks 中"""
    ctx = _base_context(branch_direction="local_search: explore 2-opt improvements")
    system_blocks, _user = _split_hypothesis_context(ctx)
    all_text = " ".join(b["text"] for b in system_blocks)
    assert "## Branch Direction" in all_text
    assert "2-opt improvements" in all_text


def test_hypothesis_prompt_omits_branch_direction_when_empty():
    """branch_direction が空のとき，prompt に ## Branch Direction は出現しない"""
    ctx = _base_context(branch_direction="")
    system_blocks, _user = _split_hypothesis_context(ctx)
    all_text = " ".join(b["text"] for b in system_blocks)
    assert "## Branch Direction" not in all_text


# ---------------------------------------------------------------------------
# Registry sync tests
# ---------------------------------------------------------------------------

def test_remove_action_deletes_registry_entry(tmp_path: Path):
    """remove action 后 registry.yaml 不含被删算子"""
    pool = _champ_pool()
    hypothesis = _make_hypothesis(action="remove", target_file="operators/swap.py")
    patch = _make_patch(action="delete", file_path="operators/swap.py")

    pool_mgr = PoolManager(pool)
    candidate_pool = pool_mgr.build_candidate_pool(pool, hypothesis, patch)
    pool_mgr.export_registry(candidate_pool, str(tmp_path))

    registry_path = tmp_path / "registry.yaml"
    assert registry_path.exists()
    with open(registry_path) as f:
        data = yaml.safe_load(f)
    names = {op["name"] for op in data["operators"]}
    assert "swap" not in names
    assert "move" in names


def test_remove_action_renormalizes_weights(tmp_path: Path):
    """remove 后剩余算子权重归一化"""
    pool = _champ_pool()
    hypothesis = _make_hypothesis(action="remove", target_file="operators/swap.py")
    patch = _make_patch(action="delete", file_path="operators/swap.py")

    pool_mgr = PoolManager(pool)
    candidate_pool = pool_mgr.build_candidate_pool(pool, hypothesis, patch)
    total = sum(op.weight for op in candidate_pool.values())
    assert abs(total - 1.0) < 1e-6


def test_modify_updates_registry_file_path(tmp_path: Path):
    """modify 且 file_path 变化时 registry 同步更新"""
    pool = _champ_pool()
    hypothesis = _make_hypothesis(action="modify", target_file="operators/swap.py")
    new_path = "operators/swap_v2.py"
    patch = _make_patch(action="modify", file_path=new_path)

    pool_mgr = PoolManager(pool)
    candidate_pool = pool_mgr.build_candidate_pool(pool, hypothesis, patch)
    pool_mgr.export_registry(candidate_pool, str(tmp_path))

    with open(tmp_path / "registry.yaml") as f:
        data = yaml.safe_load(f)

    file_paths = {op["file_path"] for op in data["operators"]}
    assert new_path in file_paths
    assert "operators/swap.py" not in file_paths


_MIN_PROBLEM_YAML = """\
name: test_problem
root_dir: {root_dir}
operator_categories:
  - order_level
search_space:
  editable:
    - operators/
  frozen: []
  import_whitelist: []
"""


def _write_problem_yaml(problem_dir: Path) -> Path:
    """Write a minimal valid problem.yaml to problem_dir."""
    problem_yaml = problem_dir / "problem.yaml"
    problem_yaml.write_text(_MIN_PROBLEM_YAML.format(root_dir=str(problem_dir)))
    return problem_yaml


def _setup_campaign(tmp_path: Path, with_registry: bool = False) -> tuple:
    """Create minimal campaign dir + problem dir. Returns (problem_yaml, campaign_dir)."""
    problem_dir = tmp_path / "problem"
    problem_dir.mkdir()
    if with_registry:
        registry_data = {
            "operators": [
                {"name": "swap", "file_path": "operators/swap.py",
                 "category": "order_level", "weight": 1.0, "class_name": "Swap"},
            ]
        }
        with open(problem_dir / "registry.yaml", "w") as f:
            yaml.dump(registry_data, f)

    problem_yaml = _write_problem_yaml(problem_dir)

    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    state = {
        "problem_yaml": str(problem_yaml),
        "campaign_dir": str(campaign_dir),
        "problem_name": "test_problem",
    }
    (campaign_dir / ".scion_state.json").write_text(json.dumps(state))
    return problem_yaml, campaign_dir


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

def test_cli_run_constructs_real_runner_and_protocol(tmp_path: Path):
    """scion run 默认构造真实 Runner/Protocol"""
    from unittest.mock import patch as _patch

    constructed_runner = []
    constructed_protocol = []

    try:
        from scion.runtime import subprocess_runner
        from scion.protocol import experiment
        orig_runner_cls = subprocess_runner.LocalSubprocessRunner
        orig_proto_cls = experiment.ExperimentProtocol
    except Exception:
        pytest.skip("Runtime/protocol modules not importable")

    class TrackingRunner(orig_runner_cls):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            constructed_runner.append(self)

    class TrackingProtocol(orig_proto_cls):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            constructed_protocol.append(self)

    _problem_yaml, campaign_dir = _setup_campaign(tmp_path)

    with (
        _patch.object(subprocess_runner, "LocalSubprocessRunner", TrackingRunner),
        _patch.object(experiment, "ExperimentProtocol", TrackingProtocol),
    ):
        from typer.testing import CliRunner
        from scion.cli.main import app

        cli_runner = CliRunner()
        result = cli_runner.invoke(
            app,
            ["run", "--mock-llm", "--rounds", "0", "--campaign-dir", str(campaign_dir)],
            catch_exceptions=True,
        )

    assert len(constructed_runner) >= 1, (
        f"LocalSubprocessRunner not constructed. CLI output: {result.output}"
    )
    assert len(constructed_protocol) >= 1, (
        f"ExperimentProtocol not constructed. CLI output: {result.output}"
    )


def test_cli_initial_champion_pool_from_registry(tmp_path: Path):
    """CLI 启动时 champion pool 从 registry.yaml 加载，不为空"""
    _problem_yaml, campaign_dir = _setup_campaign(tmp_path, with_registry=True)

    loaded_pools = []

    from scion.core import campaign as _camp_mod
    orig_mgr = _camp_mod.CampaignManager

    class TrackingManager(orig_mgr):
        def __init__(self, *a, champion, **kw):
            loaded_pools.append(dict(champion.operator_pool))
            super().__init__(*a, champion=champion, **kw)

    from unittest.mock import patch as _patch
    with _patch.object(_camp_mod, "CampaignManager", TrackingManager):
        from typer.testing import CliRunner
        from scion.cli.main import app

        cli_runner = CliRunner()
        cli_runner.invoke(
            app,
            ["run", "--mock-llm", "--rounds", "0", "--campaign-dir", str(campaign_dir)],
            catch_exceptions=True,
        )

    assert len(loaded_pools) >= 1
    pool = loaded_pools[0]
    assert "swap" in pool, f"Expected 'swap' operator in pool, got: {list(pool.keys())}"


# ---------------------------------------------------------------------------
# Lineage tests
# ---------------------------------------------------------------------------

def test_lineage_event_contains_real_hypothesis_id(tmp_path: Path):
    """lineage event 的 hypothesis_id 不是空字符串"""
    from scion.lineage.registry import LineageRegistry
    from scion.core.models import (
        Branch, BranchState, CanaryResult, ContractResult, VerificationResult,
        Decision, HypothesisProposal, HypothesisRecord,
    )

    db = LineageRegistry(str(tmp_path / "scion.db"))
    branch = Branch(
        branch_id=str(uuid.uuid4()),
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="abc",
    )
    hyp_id = str(uuid.uuid4())

    event: Dict[str, Any] = {
        "campaign_id": "test",
        "branch_id": branch.branch_id,
        "hypothesis_id": hyp_id,
        "decision": "continue_explore",
    }
    db.record_event(event)

    events = db.query_by_branch(branch.branch_id)
    assert len(events) == 1
    assert events[0]["hypothesis_id"] == hyp_id
    assert events[0]["hypothesis_id"] != ""


def test_lineage_event_contains_decision_reason_codes(tmp_path: Path):
    """有 decision 的事件包含 reason_codes"""
    from scion.lineage.registry import LineageRegistry
    import json as _json

    db = LineageRegistry(str(tmp_path / "scion.db"))
    branch_id = str(uuid.uuid4())
    reason_codes = ["win_rate_below_threshold", "insufficient_cases"]

    db.record_decision(
        branch_id=branch_id,
        features_json=_json.dumps({"win_rate": 0.3}),
        decision="continue_explore",
        reason=_json.dumps(reason_codes),
    )

    events = db.query_by_branch(branch_id)
    assert len(events) == 1
    recorded_reason = events[0].get("decision_reason")
    assert recorded_reason is not None
    parsed = _json.loads(recorded_reason)
    assert parsed == reason_codes
