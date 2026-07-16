"""Focused ownership tests for durable campaign identity."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from scion.lineage.registry import LineageRegistry
from scion.tests.campaign_test_support import _campaign


def _record_legacy_event(
    registry: LineageRegistry,
    *,
    event_id: str,
    campaign_id: str | None,
) -> None:
    registry.record_event(
        {
            "event_id": event_id,
            "campaign_id": campaign_id,
            "branch_id": f"branch-{event_id}",
            "timestamp": f"timestamp-{event_id}",
        }
    )


def _durable_campaign_id(db_path: Path) -> str | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT campaign_id FROM campaign_identity WHERE singleton_id = 1"
        ).fetchone()
    return None if row is None else str(row[0])


def test_fresh_registry_claim_is_stable(tmp_path: Path) -> None:
    db_path = tmp_path / "scion.db"
    registry = LineageRegistry(str(db_path))

    assert registry.claim_campaign_id("campaign-first") == "campaign-first"
    assert registry.claim_campaign_id("campaign-second") == "campaign-first"
    assert _durable_campaign_id(db_path) == "campaign-first"


def test_reopened_registry_ignores_a_different_proposed_identity(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    original = LineageRegistry(str(db_path)).claim_campaign_id("campaign-original")

    reopened = LineageRegistry(str(db_path))

    assert reopened.claim_campaign_id("campaign-after-reopen") == original
    assert _durable_campaign_id(db_path) == original


def test_legacy_history_with_no_distinct_identity_uses_proposed_identity(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    registry = LineageRegistry(str(db_path))
    _record_legacy_event(registry, event_id="null-id", campaign_id=None)
    _record_legacy_event(registry, event_id="blank-id", campaign_id="   ")

    assert registry.claim_campaign_id("campaign-proposed") == "campaign-proposed"
    assert _durable_campaign_id(db_path) == "campaign-proposed"


def test_legacy_history_with_one_distinct_identity_is_adopted(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    registry = LineageRegistry(str(db_path))
    _record_legacy_event(registry, event_id="old-1", campaign_id="campaign-legacy")
    _record_legacy_event(registry, event_id="old-2", campaign_id="campaign-legacy")
    _record_legacy_event(registry, event_id="blank-id", campaign_id="")

    assert registry.claim_campaign_id("campaign-proposed") == "campaign-legacy"
    assert _durable_campaign_id(db_path) == "campaign-legacy"


def test_legacy_history_with_multiple_identities_fails_closed(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scion.db"
    registry = LineageRegistry(str(db_path))
    _record_legacy_event(registry, event_id="old-a", campaign_id="campaign-a")
    _record_legacy_event(registry, event_id="old-b", campaign_id="campaign-b")

    with pytest.raises(RuntimeError, match="legacy campaign identity is ambiguous"):
        registry.claim_campaign_id("campaign-proposed")

    assert _durable_campaign_id(db_path) is None


def test_campaign_manager_reopen_keeps_identity_for_old_and_new_events(
    tmp_path: Path,
) -> None:
    original = _campaign(tmp_path)
    original_id = original._campaign_id
    _record_legacy_event(
        original._registry,
        event_id="before-reopen",
        campaign_id=original_id,
    )

    # The test support creates its input snapshot on every construction.
    shutil.rmtree(tmp_path / "champion_code")
    reopened = _campaign(tmp_path)
    _record_legacy_event(
        reopened._registry,
        event_id="after-reopen",
        campaign_id=reopened._campaign_id,
    )

    assert reopened._campaign_id == original_id
    with sqlite3.connect(tmp_path / "campaign" / "scion.db") as conn:
        event_campaign_ids = conn.execute(
            """
            SELECT event_id, campaign_id
            FROM experiment_events
            WHERE event_id IN ('before-reopen', 'after-reopen')
            ORDER BY event_id
            """
        ).fetchall()
    assert event_campaign_ids == [
        ("after-reopen", original_id),
        ("before-reopen", original_id),
    ]
