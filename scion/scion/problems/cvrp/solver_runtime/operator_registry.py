"""Registry operator loading for the CVRP solver runtime."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping

from scion.problems.cvrp.solver_runtime.neighborhood_portfolio import (
    _ALLOWED_PORTFOLIO_COMPONENTS,
)


class _LoadedOperator:
    def __init__(
        self,
        name: str,
        weight: float,
        instance: Any,
        order: int,
        component: str,
    ) -> None:
        self.name = name
        self.weight = weight
        self.instance = instance
        self.order = order
        self.component = component


def _load_registry_operators(
    *,
    registry_path: str,
    workspace_root: str | Path,
    audit: dict[str, Any],
) -> tuple[_LoadedOperator, ...]:
    if not registry_path:
        return tuple()
    path = Path(registry_path)
    if not path.exists():
        return tuple()

    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        audit["operator_errors"] += 1
        _record_event(audit, "<registry>", "error", f"registry read failed: {exc}")
        return tuple()

    raw_operators = payload.get("operators", []) if isinstance(payload, Mapping) else []
    if not isinstance(raw_operators, list):
        audit["operator_errors"] += 1
        _record_event(audit, "<registry>", "error", "operators field is not a list")
        return tuple()

    workspace = Path(workspace_root).resolve()
    loaded: list[_LoadedOperator] = []
    for index, entry in enumerate(raw_operators):
        if not isinstance(entry, Mapping):
            audit["operator_skipped"] += 1
            _record_event(audit, f"entry-{index}", "skipped", "registry entry is not a mapping")
            continue
        name = str(entry.get("name") or f"operator-{index}")
        file_path = str(entry.get("file_path") or "").strip()
        class_name = str(entry.get("class_name") or "").strip()
        weight = _coerce_weight(entry.get("weight"))
        target = _operator_path(workspace, file_path)
        if target is None:
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "operator path escapes workspace")
            continue
        if not class_name:
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "missing class_name")
            continue
        if not target.is_file():
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", f"operator file not found: {file_path}")
            continue
        try:
            instance = _load_operator_instance(target, class_name, index)
        except Exception as exc:
            audit["operator_errors"] += 1
            _record_event(audit, name, "error", str(exc))
            continue
        if not hasattr(instance, "execute"):
            audit["operator_skipped"] += 1
            _record_event(audit, name, "skipped", "operator has no execute method")
            continue
        component = _operator_component(entry, instance)
        loaded.append(
            _LoadedOperator(
                name=name,
                weight=weight,
                instance=instance,
                order=index,
                component=component,
            )
        )

    loaded.sort(key=lambda op: (-op.weight, op.order))
    audit["operator_loaded"] = len(loaded)
    return tuple(loaded)


def _operator_component(entry: Mapping[str, Any], instance: Any) -> str:
    raw = entry.get("category")
    if not raw:
        raw = getattr(instance, "category", "")
    component = str(raw or "").strip()
    if component in _ALLOWED_PORTFOLIO_COMPONENTS:
        return component
    return "registry_operator"


def _operator_path(workspace: Path, file_path: str) -> Path | None:
    if not file_path:
        return None
    rel = Path(file_path)
    if rel.is_absolute():
        return None
    target = (workspace / rel).resolve()
    try:
        target.relative_to(workspace)
    except ValueError:
        return None
    return target


def _load_operator_instance(path: Path, class_name: str, index: int) -> Any:
    module_name = f"_scion_cvrp_operator_{index}_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    cls = getattr(module, class_name)
    return cls()


def _coerce_weight(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _record_event(
    audit: dict[str, Any],
    operator_name: str,
    status: str,
    detail: str,
) -> None:
    events = audit["operator_events"]
    if len(events) >= 20:
        return
    payload = {"operator": operator_name, "status": status}
    if detail:
        payload["detail"] = detail
    events.append(payload)
