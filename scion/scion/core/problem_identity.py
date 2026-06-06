"""Generic problem identity anchor helpers."""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def problem_id_anchor(problem_spec: Any) -> str | None:
    """Return the generic problem id used to bind proposal output to a problem."""
    for attr in ("id", "problem_id", "name"):
        value = _clean_anchor(getattr(problem_spec, attr, None))
        if value:
            return value
    return None


def stable_identity_hash(value: Any) -> str | None:
    """Return a deterministic hash for a structured identity object."""
    if value is None:
        return None
    for attr in ("problem_spec_hash", "spec_hash", "hash", "digest"):
        explicit = _clean_anchor(getattr(value, attr, None))
        if explicit:
            return explicit
    payload = _stable_payload(value)
    rendered = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _clean_anchor(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _stable_payload(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _stable_payload(model_dump(mode="json", fallback=str))
        except TypeError:
            try:
                return _stable_payload(model_dump(mode="json"))
            except Exception:
                return _stable_payload(model_dump())
        except Exception:
            return _stable_payload(model_dump())
    if dataclasses.is_dataclass(value):
        return _stable_payload(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _stable_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_stable_payload(item) for item in value]
    if hasattr(value, "__dict__"):
        return _stable_payload(vars(value))
    return str(value)
