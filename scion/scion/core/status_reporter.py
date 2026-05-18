"""Small JSON status snapshots for long-running campaigns."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scion.core.public_refs import redact_public_refs

API_BALANCE_EXHAUSTED_STOP_REASON = "api_balance_exhausted"
PROVIDER_ERROR_CATEGORY_BALANCE_EXHAUSTED = "balance_exhausted"


def is_provider_balance_exhausted_detail(detail: Any) -> bool:
    """Return true when an LLM/provider error text indicates exhausted credits."""
    text = str(detail or "").strip().lower()
    if not text:
        return False
    if "no credits" in text or "credit balance" in text:
        return True
    has_balance_word = "balance" in text or "recharge" in text
    has_exhaustion_word = any(
        marker in text
        for marker in (
            "insufficient",
            "exhausted",
            "depleted",
            "recharge",
            "not enough",
        )
    )
    return has_balance_word and has_exhaustion_word


def normalize_stopped_reason(
    stopped_reason: Any,
    *,
    balance_exhausted: bool = False,
    circuit_breaker_tripped: bool = False,
) -> Any:
    """Keep provider-balance stops from being reported as generic circuit breaks."""
    if balance_exhausted or stopped_reason == API_BALANCE_EXHAUSTED_STOP_REASON:
        return API_BALANCE_EXHAUSTED_STOP_REASON
    if circuit_breaker_tripped and stopped_reason in (None, "run_complete"):
        return "circuit_breaker"
    return stopped_reason


def normalize_status_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Add structured stop/provider fields while preserving existing keys."""
    normalized = dict(payload)
    stopped_reason = normalized.get("stopped_reason")
    balance_exhausted = bool(normalized.get("balance_exhausted")) or (
        stopped_reason == API_BALANCE_EXHAUSTED_STOP_REASON
    )
    circuit_breaker_tripped = bool(normalized.get("circuit_breaker_tripped"))
    effective_reason = normalize_stopped_reason(
        stopped_reason,
        balance_exhausted=balance_exhausted,
        circuit_breaker_tripped=circuit_breaker_tripped,
    )
    if effective_reason is not None:
        normalized["stopped_reason"] = effective_reason
    if effective_reason == API_BALANCE_EXHAUSTED_STOP_REASON:
        normalized["balance_exhausted"] = True
        normalized["stop_category"] = "provider_error"
        normalized.setdefault(
            "provider_error",
            {"category": PROVIDER_ERROR_CATEGORY_BALANCE_EXHAUSTED},
        )
    return normalized


class StatusReporter:
    """Write the latest campaign status to ``status.json`` atomically."""

    def __init__(self, campaign_dir: str, filename: str = "status.json") -> None:
        self._path = Path(campaign_dir) / filename

    @property
    def path(self) -> Path:
        return self._path

    def write(self, payload: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **redact_public_refs(
                normalize_status_payload(payload),
                base_dir=self._path.parent,
            ),
        }
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        os.replace(tmp_path, self._path)
