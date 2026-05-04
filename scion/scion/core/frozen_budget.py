"""Campaign-level frozen holdout usage ledger."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


FROZEN_BUDGET_EVENT_KIND = "frozen_budget"
FROZEN_BUDGET_EXHAUSTED = "frozen_budget_exhausted"


@dataclass(frozen=True)
class FrozenBudgetDecision:
    allowed: bool
    used: int
    limit: int
    branch_id: str
    reason: str = ""


class FrozenBudgetLedger:
    """Consume frozen holdout attempts before protocol evaluation starts.

    The ledger is campaign-level, not branch-level. Consumption is persisted as
    append-only lineage events so a fresh manager/service can rebuild the used
    count from SQLite instead of trusting process memory.
    """

    def __init__(
        self,
        *,
        max_uses: int,
        registry: Any | None = None,
        campaign_id: str = "",
    ) -> None:
        max_uses = _coerce_max_uses(max_uses)
        if max_uses <= 0:
            raise ValueError("max_uses must be positive")
        self.max_uses = int(max_uses)
        self.registry = registry
        self.campaign_id = campaign_id
        self._used = self._load_used_from_registry()

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.max_uses - self._used)

    def snapshot(self) -> dict[str, int]:
        return {
            "used": self._used,
            "limit": self.max_uses,
            "remaining": self.remaining,
        }

    def try_consume(self, *, branch_id: str) -> FrozenBudgetDecision:
        """Consume one frozen attempt if budget remains."""
        if self._used >= self.max_uses:
            self._record_event(
                branch_id=branch_id,
                consumed=False,
                reason=FROZEN_BUDGET_EXHAUSTED,
            )
            return FrozenBudgetDecision(
                allowed=False,
                used=self._used,
                limit=self.max_uses,
                branch_id=branch_id,
                reason=FROZEN_BUDGET_EXHAUSTED,
            )

        self._used += 1
        self._record_event(branch_id=branch_id, consumed=True, reason="consumed")
        return FrozenBudgetDecision(
            allowed=True,
            used=self._used,
            limit=self.max_uses,
            branch_id=branch_id,
        )

    def _load_used_from_registry(self) -> int:
        db_path = getattr(self.registry, "db_path", None)
        if not db_path:
            return 0
        try:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT decision_features_json
                    FROM experiment_events
                    WHERE event_kind = ?
                    """,
                    (FROZEN_BUDGET_EVENT_KIND,),
                ).fetchall()
        except Exception:
            return 0
        used = 0
        for (raw,) in rows:
            try:
                payload = json.loads(raw or "{}")
            except Exception:
                continue
            if payload.get("consumed") is True:
                used += 1
        return used

    def _record_event(
        self,
        *,
        branch_id: str,
        consumed: bool,
        reason: str,
    ) -> None:
        if self.registry is None:
            return
        payload: Mapping[str, Any] = {
            "consumed": consumed,
            "reason": reason,
            "used": self._used,
            "limit": self.max_uses,
            "remaining": self.remaining,
        }
        event = {
            "campaign_id": self.campaign_id,
            "branch_id": branch_id,
            "timestamp": datetime.now().isoformat(),
            "event_kind": FROZEN_BUDGET_EVENT_KIND,
            "stage": "frozen",
            "decision": "allow" if consumed else "block",
            "decision_reason": reason,
            "decision_features_json": json.dumps(payload, sort_keys=True),
        }
        try:
            self.registry.record_event(event)
        except Exception:
            pass


def _coerce_max_uses(value: Any) -> int:
    if isinstance(value, bool):
        return 3
    try:
        return int(value)
    except Exception:
        return 3
