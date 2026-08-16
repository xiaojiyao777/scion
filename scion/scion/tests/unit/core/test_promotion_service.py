from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scion.core.branch import BranchController
from scion.core.models import Branch, BranchState, ChampionState, OperatorConfig
from scion.core.promotion_service import PromotionService


class FakeMaterializer:
    def __init__(self, *, fail_freeze: bool = False) -> None:
        self.fail_freeze = fail_freeze
        self.frozen: list[str] = []

    def freeze_snapshot(self, path: str) -> None:
        if self.fail_freeze:
            raise OSError("freeze failed")
        self.frozen.append(path)


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
        code_snapshot_path=f"/tmp/champion_v{version}",
        promoted_at="2026-05-01T00:00:00",
    )


def _workspace(
    path: Path,
    *,
    with_registry: bool = True,
    registry_text: str | None = None,
) -> Path:
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


def test_promote_is_one_operation_from_workspace_through_state_hooks(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path / "candidate")
    calls: list[tuple[str, object]] = []
    materializer = FakeMaterializer()
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=materializer,
        set_champion=lambda champion: calls.append(("champion", champion.version)),
        promote_branch=lambda branch_id, champion: calls.append(
            ("branch", (branch_id, champion.version))
        ),
        mark_stale=lambda version: calls.append(("stale", version)) or ("branch-2",),
        clock=lambda: "2026-05-01T12:00:00",
    )

    result = service.promote(
        branch_id="branch-1",
        candidate_workspace=str(workspace),
        champion=_champion(),
    )

    expected_snapshot = str(tmp_path / "champions" / "champion_v2")
    assert result.champion.version == 2
    assert result.champion.code_snapshot_path == expected_snapshot
    assert result.champion.operator_pool["ls"].class_name == "LS"
    assert result.stale_branch_ids == ("branch-2",)
    assert materializer.frozen == [expected_snapshot]
    assert calls == [
        ("champion", 2),
        ("branch", ("branch-1", 2)),
        ("stale", 2),
    ]
    with pytest.raises(FrozenInstanceError):
        result.stale_branch_ids = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        result.current_weights["ls"] = 0.5  # type: ignore[index]


def test_snapshot_failure_stops_before_state_hooks(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate")
    calls: list[str] = []
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(fail_freeze=True),
        set_champion=lambda champion: calls.append(f"champion:{champion.version}"),
        mark_stale=lambda version: calls.append(f"stale:{version}") or (),
    )

    with pytest.raises(RuntimeError, match="freeze champion snapshot failed"):
        service.promote(
            branch_id="branch-1",
            candidate_workspace=str(workspace),
            champion=_champion(),
        )

    assert calls == []


def test_registry_read_failure_stops_promotion(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate", registry_text="operators: [")
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
        read_weights_fn=lambda _registry_path: {},
    )

    with pytest.raises(RuntimeError, match="read champion registry failed"):
        service.promote(
            branch_id="branch-1",
            candidate_workspace=str(workspace),
            champion=_champion(),
        )


def test_absent_registry_preserves_current_operator_pool(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate", with_registry=False)
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
    )
    champion = _champion()

    result = service.promote(
        branch_id="branch-1",
        candidate_workspace=str(workspace),
        champion=champion,
    )

    assert result.champion.operator_pool == champion.operator_pool


def test_existing_snapshot_fails_closed_without_replacement(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate")
    snapshot = tmp_path / "champions" / "champion_v2"
    snapshot.mkdir(parents=True)
    marker = snapshot / "keep"
    marker.write_text("existing\n", encoding="utf-8")
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
    )

    with pytest.raises(RuntimeError, match="champion snapshot already exists"):
        service.promote(
            branch_id="branch-1",
            candidate_workspace=str(workspace),
            champion=_champion(),
        )

    assert marker.read_text(encoding="utf-8") == "existing\n"


def test_state_hook_failure_stops_later_hooks(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate")
    calls: list[tuple[str, object]] = []

    def fail_champion(champion: ChampionState) -> None:
        calls.append(("champion", champion.version))
        raise RuntimeError("memory install unavailable")

    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
        set_champion=fail_champion,
        promote_branch=lambda branch_id, champion: calls.append(
            ("branch", (branch_id, champion.version))
        ),
        mark_stale=lambda version: calls.append(("stale", version)) or (),
    )

    with pytest.raises(RuntimeError, match="memory install unavailable"):
        service.promote(
            branch_id="branch-1",
            candidate_workspace=str(workspace),
            champion=_champion(),
        )

    assert calls == [("champion", 2)]


def test_stale_marking_preserves_frozen_branch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "candidate")
    ctrl = BranchController()
    ctrl._branches["frozen"] = Branch(
        branch_id="frozen",
        state=BranchState.FROZEN_TESTING,
        base_champion_id=1,
    )
    ctrl._branches["ready"] = Branch(
        branch_id="ready",
        state=BranchState.READY_VALIDATE,
        base_champion_id=1,
    )
    service = PromotionService(
        snapshot_root=tmp_path / "champions",
        materializer=FakeMaterializer(),
        mark_stale=ctrl.mark_all_stale,
    )

    result = service.promote(
        branch_id="promoted",
        candidate_workspace=str(workspace),
        champion=_champion(),
    )

    assert result.stale_branch_ids == ("ready",)
    assert ctrl._branches["frozen"].state == BranchState.FROZEN_TESTING
    assert ctrl._branches["ready"].state == BranchState.STALE
