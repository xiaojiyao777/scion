from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scion.core import campaign_owner_registry as subject
from scion.core.models import Branch, BranchState, HypothesisRecord
from scion.lineage.durable_owner import (
    DurableOwnerIntegrityError,
    RevisionedBranchRecord,
    RevisionedHypothesisRecord,
)


_NOW = datetime(2026, 7, 17, 1, 2, 3, 123456, tzinfo=timezone.utc)


def _branch(*, branch_id: str = "branch-a") -> RevisionedBranchRecord:
    return RevisionedBranchRecord.from_value(
        Branch(
            branch_id=branch_id,
            state=BranchState.EXPLORE,
            base_champion_id=7,
            base_champion_hash="a" * 64,
            lineage_id="lineage-a",
            created_at=_NOW,
            updated_at=_NOW,
        ),
        owner_revision=0,
    )


def _hypothesis(
    hypothesis_id: str,
    *,
    branch_id: str = "branch-a",
    parent_id: str | None = None,
    status: str = "rejected",
    revision: int = 0,
) -> RevisionedHypothesisRecord:
    return RevisionedHypothesisRecord.from_value(
        HypothesisRecord(
            hypothesis_id=hypothesis_id,
            branch_id=branch_id,
            change_locus="solver_design",
            action="modify",
            status=status,
            target_file="solver.py",
            parent_hypothesis_id=parent_id,
            hypothesis_text="Change one deterministic search mechanism.",
            created_at=_NOW,
            base_champion_version=7,
            family_id="solver_design",
            family_source="keyword",
            taxonomy_version="v1",
            predicted_direction="improve",
            proposal_digest="b" * 64,
        ),
        owner_revision=revision,
    )


def _root() -> subject._CampaignOwnerState:
    return subject._build_owner_state(
        {"branch-a": _branch()},
        {"h-parent": _hypothesis("h-parent")},
        generation=4,
    )


def test_creation_successor_adds_one_revision_zero_hypothesis() -> None:
    old = _root()
    target = _hypothesis(
        "h-new",
        parent_id="h-parent",
        status="active",
    )

    successor = subject._prepare_successor_root(
        old,
        {},
        created_hypothesis=target,
    )

    assert successor.publication_generation == 5
    assert set(successor.hypothesis_slots.by_id) == {"h-parent", "h-new"}
    assert (
        successor.hypothesis_slots.by_id["h-parent"].owner
        == old.hypothesis_slots.by_id["h-parent"].owner
    )
    assert successor.hypothesis_slots.by_id["h-new"].owner == target
    assert successor.hypothesis_slots.current_by_branch == {"branch-a": "h-new"}


@pytest.mark.parametrize(
    "target",
    [
        _hypothesis("h-parent", status="active"),
        _hypothesis("h-new", branch_id="branch-missing", status="active"),
        _hypothesis("h-new", parent_id="h-missing", status="active"),
        _hypothesis("h-new", parent_id="h-parent", status="active", revision=1),
    ],
)
def test_creation_successor_rejects_non_creation_root_shapes(
    target: RevisionedHypothesisRecord,
) -> None:
    with pytest.raises(DurableOwnerIntegrityError):
        subject._prepare_successor_root(
            _root(),
            {},
            created_hypothesis=target,
        )


def test_creation_successor_rejects_cross_branch_parent() -> None:
    root = subject._build_owner_state(
        {"branch-a": _branch(), "branch-b": _branch(branch_id="branch-b")},
        {"h-parent": _hypothesis("h-parent", branch_id="branch-b")},
        generation=4,
    )

    with pytest.raises(DurableOwnerIntegrityError):
        subject._prepare_successor_root(
            root,
            {},
            created_hypothesis=_hypothesis(
                "h-new",
                parent_id="h-parent",
                status="active",
            ),
        )
