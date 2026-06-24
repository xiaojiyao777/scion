"""Problem opportunity summary collection for proposal contexts."""

from __future__ import annotations

from typing import Any, Mapping

from scion.opportunity import redact_problem_opportunity_payload


def problem_opportunity_summary_from_adapter(adapter: Any | None) -> dict[str, Any]:
    """Return a redacted proposal-only opportunity summary from a problem adapter."""

    hook = getattr(adapter, "render_problem_opportunity_summary", None)
    if not callable(hook):
        return {}
    try:
        payload = hook()
    except Exception:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    redacted = redact_problem_opportunity_payload(dict(payload))
    if not isinstance(redacted, Mapping):
        return {}
    result = dict(redacted)
    result["schema_version"] = (
        result.get("schema_version") or "scion.problem_opportunity_summary.v1"
    )
    result["proposal_visibility_only"] = True
    result["decision_features_excluded"] = True
    result["decision_input_policy"] = "excluded_from_decision_features"
    return {
        key: value
        for key, value in result.items()
        if value not in ("", None, [], {}, ())
    }
