"""Sprint G3: Weight optimizer correctness tests.

Verifies:
- optimizer evaluates true baseline (current_weights) BEFORE random samples
- baseline_weights == current_weights passed in
- baseline_score == eval of current_weights
- improved=False when best_score < true_baseline_score
- improved=True only when best_score > true_baseline_score
- observations saved to JSON file (observations_ref is valid path)
- compute_snapshot_hash changes when registry.yaml changes
- compute_snapshot_hash stable when nothing changes
- mutable staging is writable
- freeze_snapshot makes files read-only
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

import pytest

from scion.parameter.optimizer import RandomLocalWeightOptimizer
from scion.parameter.search_space import ParameterSearchSpace
from scion.runtime.workspace import WorkspaceMaterializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_space(n_random: int = 3, n_iter: int = 2) -> ParameterSearchSpace:
    return ParameterSearchSpace(
        operator_names=("op_a", "op_b"),
        weight_bounds=(0.1, 3.0),
        n_initial_random=n_random,
        n_iterations=n_iter,
    )


def _current_weights() -> Dict[str, float]:
    return {"op_a": 1.0, "op_b": 1.0}


def _make_workspace_with_registry(tmp_path: Path, registry_content: str) -> str:
    """Create a minimal workspace dir with an operators/ subdir and registry.yaml."""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "operators").mkdir()
    (ws / "operators" / "op_a.py").write_text("class OpA:\n    pass\n")
    (ws / "registry.yaml").write_text(registry_content)
    return str(ws)


# ---------------------------------------------------------------------------
# T1 tests — true baseline evaluation
# ---------------------------------------------------------------------------

def test_optimizer_evaluates_true_baseline_before_random_samples():
    """optimizer 第一次 eval_fn 调用的 weights 是 current_weights"""
    calls: List[Dict[str, float]] = []
    current = _current_weights()

    def tracking_eval(w: Dict[str, float]) -> float:
        calls.append(dict(w))
        return 0.5

    space = _make_space(n_random=3, n_iter=0)
    opt = RandomLocalWeightOptimizer(space, tracking_eval, seed=0)
    opt.optimize(current)

    assert len(calls) >= 1, "eval_fn should have been called at least once"
    assert calls[0] == current, "First eval_fn call must be current_weights (true baseline)"


def test_baseline_weights_equal_current_weights():
    """result.baseline_weights == 传入的 current_weights"""
    current = _current_weights()

    def eval_fn(w):
        return 0.1

    space = _make_space()
    opt = RandomLocalWeightOptimizer(space, eval_fn, seed=0)
    result = opt.optimize(current)

    assert result.baseline_weights == current


def test_baseline_score_is_true_baseline_evaluation():
    """result.baseline_score 是 current_weights 的实测分数"""
    current = _current_weights()
    baseline_score_value = 0.42

    call_count = [0]

    def eval_fn(w):
        call_count[0] += 1
        if w == current:
            return baseline_score_value
        return 0.0  # all random samples return 0

    space = _make_space(n_random=2, n_iter=0)
    opt = RandomLocalWeightOptimizer(space, eval_fn, seed=0)
    result = opt.optimize(current)

    assert result.baseline_score == baseline_score_value


# ---------------------------------------------------------------------------
# T1 tests — improved correctness
# ---------------------------------------------------------------------------

def test_improved_false_when_best_below_true_baseline():
    """best_score < true_baseline_score → improved=False"""
    current = _current_weights()
    true_baseline = 1.0

    def eval_fn(w):
        if w == current:
            return true_baseline
        return 0.5  # all search points are worse

    space = _make_space(n_random=4, n_iter=2)
    opt = RandomLocalWeightOptimizer(space, eval_fn, seed=0)
    result = opt.optimize(current)

    assert result.improved is False
    assert result.best_score <= result.baseline_score


def test_improved_true_only_when_best_exceeds_true_baseline():
    """best_score > true_baseline_score → improved=True"""
    current = _current_weights()
    true_baseline = 0.1
    better_score = 0.9

    call_count = [0]

    def eval_fn(w):
        call_count[0] += 1
        if w == current:
            return true_baseline
        # Make the second call return a better score (first random)
        if call_count[0] == 2:
            return better_score
        return 0.05

    space = _make_space(n_random=2, n_iter=0)
    opt = RandomLocalWeightOptimizer(space, eval_fn, seed=0)
    result = opt.optimize(current)

    assert result.improved is True
    assert result.best_score > result.baseline_score


def test_negative_best_not_marked_improved():
    """best 低于 baseline 绝不 improved"""
    current = _current_weights()

    def eval_fn(w):
        if w == current:
            return 0.5
        return -1.0  # all random worse

    space = _make_space(n_random=5, n_iter=3)
    opt = RandomLocalWeightOptimizer(space, eval_fn, seed=1)
    result = opt.optimize(current)

    assert result.improved is False


# ---------------------------------------------------------------------------
# T2 tests — observations file
# ---------------------------------------------------------------------------

def test_observations_written_to_file():
    """optimizer 完成后 observations_ref 指向有效 JSON 文件"""
    current = _current_weights()
    scores = [0.1 * i for i in range(20)]
    idx = [0]

    def eval_fn(w):
        s = scores[idx[0] % len(scores)]
        idx[0] += 1
        return s

    space = _make_space(n_random=3, n_iter=2)
    opt = RandomLocalWeightOptimizer(space, eval_fn, seed=0)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = opt.optimize(current, artifacts_dir=tmpdir)

        assert result.observations_ref != "", "observations_ref should be set"
        assert os.path.isfile(result.observations_ref), "observations_ref must point to a real file"

        with open(result.observations_ref) as f:
            data = json.load(f)

        assert isinstance(data, list), "observations file must contain a JSON list"
        assert len(data) > 0, "observations list must not be empty"
        # First entry must be the baseline evaluation
        assert data[0]["weights"] == current


# ---------------------------------------------------------------------------
# T4 tests — snapshot hash
# ---------------------------------------------------------------------------

def test_snapshot_hash_changes_when_registry_changes(tmp_path):
    """registry.yaml 权重变化后 snapshot hash 变化"""
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    materializer = WorkspaceMaterializer(str(campaign_dir))

    registry_v1 = (
        "operators:\n"
        "  - name: op_a\n"
        "    file_path: operators/op_a.py\n"
        "    class_name: OpA\n"
        "    weight: 1.0\n"
    )
    registry_v2 = (
        "operators:\n"
        "  - name: op_a\n"
        "    file_path: operators/op_a.py\n"
        "    class_name: OpA\n"
        "    weight: 2.5\n"
    )

    ws1_parent = tmp_path / "ws1_parent"
    ws1_parent.mkdir()
    ws2_parent = tmp_path / "ws2_parent"
    ws2_parent.mkdir()
    ws1 = _make_workspace_with_registry(ws1_parent, registry_v1)
    ws2 = _make_workspace_with_registry(ws2_parent, registry_v2)

    hash1 = materializer.compute_snapshot_hash(ws1)
    hash2 = materializer.compute_snapshot_hash(ws2)

    assert hash1 != hash2, "snapshot hash must change when registry weights change"


def test_snapshot_hash_stable_when_code_unchanged(tmp_path):
    """相同代码 + 相同 registry → 相同 hash"""
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    materializer = WorkspaceMaterializer(str(campaign_dir))

    registry_content = (
        "operators:\n"
        "  - name: op_a\n"
        "    file_path: operators/op_a.py\n"
        "    class_name: OpA\n"
        "    weight: 1.0\n"
    )

    ws_a = str(tmp_path / "ws_a")
    ws_b = str(tmp_path / "ws_b")
    for ws in (ws_a, ws_b):
        Path(ws).mkdir()
        (Path(ws) / "operators").mkdir()
        (Path(ws) / "operators" / "op_a.py").write_text("class OpA:\n    pass\n")
        (Path(ws) / "registry.yaml").write_text(registry_content)

    hash_a = materializer.compute_snapshot_hash(ws_a)
    hash_b = materializer.compute_snapshot_hash(ws_b)

    assert hash_a == hash_b, "identical code + registry must produce identical hash"


# ---------------------------------------------------------------------------
# T3 tests — mutable staging + freeze
# ---------------------------------------------------------------------------

def test_mutable_staging_is_writable(tmp_path):
    """staging workspace 中 registry.yaml 可写"""
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    materializer = WorkspaceMaterializer(str(campaign_dir))

    # Create a source workspace with a registry.yaml
    source = str(tmp_path / "source")
    Path(source).mkdir()
    (Path(source) / "registry.yaml").write_text("operators: []\n")
    (Path(source) / "operators").mkdir()

    staging = materializer.create_mutable_staging(source)

    registry_in_staging = Path(staging) / "registry.yaml"
    assert registry_in_staging.exists(), "registry.yaml must be copied to staging"

    # Must be writable
    try:
        registry_in_staging.write_text("operators: [updated]\n")
    except PermissionError:
        pytest.fail("Staging registry.yaml must be writable, got PermissionError")


def test_freeze_snapshot_makes_readonly(tmp_path):
    """freeze 后文件不可写"""
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()
    materializer = WorkspaceMaterializer(str(campaign_dir))

    snapshot = str(tmp_path / "snapshot")
    Path(snapshot).mkdir()
    test_file = Path(snapshot) / "registry.yaml"
    test_file.write_text("operators: []\n")

    materializer.freeze_snapshot(snapshot)

    # File should now be read-only
    mode = test_file.stat().st_mode
    assert not (mode & stat.S_IWUSR), "freeze_snapshot should remove write permission"

    # Cleanup: restore write permission so tmp_path cleanup works
    test_file.chmod(mode | stat.S_IWUSR)
    Path(snapshot).chmod(Path(snapshot).stat().st_mode | stat.S_IWUSR)
