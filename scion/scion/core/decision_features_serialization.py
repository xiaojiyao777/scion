from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from scion.core.features import _validate_no_free_text
from scion.core.models import DecisionFeatures


DECISION_FEATURES_SCHEMA = "scion.decision_features.v1"


def decision_features_to_payload(features: DecisionFeatures) -> dict[str, Any]:
    """Return a JSON-safe snapshot of the exact DecisionFeatures object."""
    _validate_no_free_text(features)
    payload = _json_safe(asdict(features))
    payload["schema"] = DECISION_FEATURES_SCHEMA
    return payload


def decision_features_to_json(features: DecisionFeatures) -> str:
    return json.dumps(
        decision_features_to_payload(features),
        sort_keys=True,
        separators=(",", ":"),
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"DecisionFeatures contains non-JSON value: {type(value).__name__}")
