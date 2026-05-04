from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.models import Branch, BranchState, ChampionState, OperatorConfig
from scion.core.promotion_service import (
    PromotionPlan,
    PromotionRequest,
    PromotionService,
)


class FakeMaterializer:
    def __init__(self, *, fail_freeze: bool = False) -> None:
        self.fail_freeze = fail_freeze
        self.frozen: list[str] = []
        self.hashes: list[str] = []

    def freeze_snapshot(self, path: str) -> None:
        if self.fail_freeze:
            raise OSError("freeze failed")
        self.frozen.append(path)

    def compute_snapshot_hash(self, workspace: str) -> str:
        self.hashes.append(workspace)
        return "snapshot-hash"


def _operator(name: str = "ls") -> OperatorConfig:
    return OperatorConfig(
        name=name,
        file_path=f"operators/{name}.py",
        category="local_search",
        weight=1.0,
        class_name=name.upper(),
    )


def _champion(version: int = 1) -> ChampionState:
    return ChampionState(
        version=version,
        operator_pool={"ls": _operator()},
        solver_config_hash="solver-hash",
        code_snapshot_path=f"/tmp/champion_v{version}",
        code_snapshot_hash=f"hash-{version}",
        promoted_at="2026-05-01T00:00:00",
    )


def _workspace(path: Path, *, with_registry: bool = True, registry_text: str | None = None) -> Path:
    ops = path / "operators"
    ops.mkdir(parents=True)
    (ops / "ls.py").write_text("class LS: pass\n", encoding="utf-8")
    if with_registry:
        (path / "registry.yaml").write_text(
            registry_text
            if registry_text is not None
            else "\n".join(
                [
                    "operators:",
                    "- name: ls",
                    "  file_path: operators/ls.py",
                    "  category: local_search",
                    "  weight: 1.0",
                    "  class_name: LS",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return path


def test_prepare_success_returns_immutable_plan(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate")
    champion = _champion()
    materializer = FakeMaterializer()
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=materializer,
        clock=lambda: "2026-05-01T12:00:00",
    )

    plan = service.prepare(
        PromotionRequest.from_champion(
            branch_id="branch-1",
            candidate_workspace=str(workspace),
            champion=champion,
        )
    )

    assert plan.branch_id == "branch-1"
    assert plan.new_champion_version == 2
    assert plan.weight_revision == 0
    assert plan.candidate_snapshot_ref == str(tmp_path / "champions" / "champion_v2")
    assert plan.registry_hash is not None
    assert plan.champion.version == 2
    assert plan.champion.operator_pool["ls"].class_name == "LS"
    assert plan.champion.code_snapshot_hash == "snapshot-hash"
    assert materializer.frozen == [plan.candidate_snapshot_ref]

    with pytest.raises(FrozenInstanceError):
        plan.new_champion_version = 3  # type: ignore[misc]
    with pytest.raises(TypeError):
        plan.current_weights["ls"] = 0.5  # type: ignore[index]


def test_prepare_failure_does_not_call_mutating_dependencies(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate")
    calls: list[str] = []
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(fail_freeze=True),
        commit_champion=lambda champion: calls.append(f"champion:{champion.version}"),
        commit_pool=lambda pool: calls.append(f"pool:{len(pool)}"),
        persist_champion=lambda champion: calls.append(f"persist:{champion.version}"),
        mark_stale=lambda version: calls.append(f"stale:{version}") or (),
    )

    with pytest.raises(RuntimeError, match="freeze champion snapshot failed"):
        service.prepare(
            PromotionRequest.from_champion(
                branch_id="branch-1",
                candidate_workspace=str(workspace),
                champion=_champion(),
            )
        )

    assert calls == []


def test_prepare_registry_read_failure_blocks_promotion_when_registry_exists(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path / "candidate", registry_text="operators: [")
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
        read_weights_fn=lambda registry_path: {},
    )

    with pytest.raises(RuntimeError, match="read champion registry failed"):
        service.prepare(
            PromotionRequest.from_champion(
                branch_id="branch-1",
                candidate_workspace=str(workspace),
                champion=_champion(),
            )
        )


def test_prepare_absent_registry_uses_previous_operator_pool_legacy_fallback(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path / "candidate", with_registry=False)
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
        clock=lambda: "2026-05-01T12:00:00",
    )
    previous_pool = {"legacy": _operator("legacy")}

    plan = service.prepare(
        PromotionRequest(
            branch_id="branch-1",
            candidate_workspace=str(workspace),
            champion_version=1,
            champion_weight_revision=0,
            solver_config_hash="solver-hash",
            previous_operator_pool=previous_pool,
        )
    )

    assert plan.registry_hash is None
    assert set(plan.champion.operator_pool) == {"legacy"}
    assert plan.champion.operator_pool["legacy"].class_name == "LEGACY"


def test_commit_success_calls_champion_pool_and_stale_hooks() -> None:
    calls: list[tuple[str, object]] = []
    champion = _champion(version=2)
    plan = PromotionPlan(
        branch_id="branch-1",
        candidate_snapshot_ref="/tmp/champion_v2",
        new_champion_version=2,
        registry_hash="registry-hash",
        weight_revision=0,
        champion=champion,
        current_weights={"ls": 1.0},
    )
    service = PromotionService(
        before_commit=lambda prepared: calls.append(("before", prepared.new_champion_version)),
        commit_champion=lambda committed: calls.append(("champion", committed.version)),
        commit_pool=lambda pool: calls.append(("pool", tuple(pool))),
        persist_champion=lambda committed: calls.append(("persist", committed.version)),
        promote_branch=lambda branch_id, committed: calls.append(
            ("promote_branch", (branch_id, committed.version))
        ),
        mark_stale=lambda version: calls.append(("stale", version)) or ("branch-2",),
        persist_branch_states=lambda: calls.append(("persist_branches", None)),
        on_promoted_branch=lambda branch_id, committed: calls.append(
            ("branch", (branch_id, committed.version))
        ),
        after_commit=lambda prepared: calls.append(("after", prepared.new_champion_version)),
    )

    result = service.commit(plan)

    assert result.branch_id == "branch-1"
    assert result.champion_version == 2
    assert result.stale_branch_ids == ("branch-2",)
    assert calls == [
        ("persist", 2),
        ("before", 2),
        ("champion", 2),
        ("pool", ("ls",)),
        ("promote_branch", ("branch-1", 2)),
        ("stale", 2),
        ("persist_branches", None),
        ("branch", ("branch-1", 2)),
        ("after", 2),
    ]


def test_commit_champion_store_failure_aborts_mutating_side_effects() -> None:
    calls: list[tuple[str, object]] = []
    plan = PromotionPlan(
        branch_id="branch-1",
        candidate_snapshot_ref="/tmp/champion_v2",
        new_champion_version=2,
        registry_hash="registry-hash",
        weight_revision=0,
        champion=_champion(version=2),
        current_weights={"ls": 1.0},
    )

    def fail_persist(committed: ChampionState) -> None:
        calls.append(("persist", committed.version))
        raise OSError("store unavailable")

    service = PromotionService(
        before_commit=lambda prepared: calls.append(("before", prepared.new_champion_version)),
        commit_champion=lambda committed: calls.append(("champion", committed.version)),
        commit_pool=lambda pool: calls.append(("pool", tuple(pool))),
        persist_champion=fail_persist,
        promote_branch=lambda branch_id, committed: calls.append(
            ("promote_branch", (branch_id, committed.version))
        ),
        mark_stale=lambda version: calls.append(("stale", version)) or ("branch-2",),
        persist_branch_states=lambda: calls.append(("persist_branches", None)),
        on_promoted_branch=lambda branch_id, committed: calls.append(
            ("branch", (branch_id, committed.version))
        ),
        after_commit=lambda prepared: calls.append(("after", prepared.new_champion_version)),
    )

    with pytest.raises(OSError, match="store unavailable"):
        service.commit(plan)

    assert calls == [
        ("persist", 2),
    ]


def test_commit_stale_hook_preserves_frozen_branch_skip_behavior() -> None:
    ctrl = BranchController()
    ctrl._branches["frozen"] = Branch(
        branch_id="frozen",
        state=BranchState.FROZEN_TESTING,
        base_champion_id=1,
        base_champion_hash="hash-1",
    )
    ctrl._branches["ready"] = Branch(
        branch_id="ready",
        state=BranchState.READY_VALIDATE,
        base_champion_id=1,
        base_champion_hash="hash-1",
    )
    plan = PromotionPlan(
        branch_id="promoted",
        candidate_snapshot_ref="/tmp/champion_v2",
        new_champion_version=2,
        registry_hash=None,
        weight_revision=0,
        champion=_champion(version=2),
    )
    service = PromotionService(mark_stale=ctrl.mark_all_stale)

    result = service.commit(plan)

    assert result.stale_branch_ids == ("ready",)
    assert ctrl._branches["frozen"].state == BranchState.FROZEN_TESTING
    assert ctrl._branches["ready"].state == BranchState.STALE
