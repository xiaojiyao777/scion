"""Small utility helpers shared across proposal-pipeline slices."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now().isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _runtime_attr(runtime: Any, name: str) -> Any:
    try:
        return getattr(runtime, name)
    except Exception:
        return None


def _agentic_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")
