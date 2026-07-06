"""CVRP protected-case prepared handoff checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from scion.postrun.inventory.prepared_contract import resolve_manifest_path


CVRP_SPLIT_CASE_STAGES = ("screening", "validation", "frozen", "canary")


def cvrp_protected_cases_split_status(
    config: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    manifest_run_root: str = "",
    local_run_root: Path | None = None,
    repo_dir: Path,
    scion_project_dir: Path,
) -> dict[str, Any]:
    protected_cases = _string_items(requirements.get("protected_cases"))
    protected_case_tokens = [_cvrp_case_token(item) for item in protected_cases]
    split_value = config.get("split")
    split_path = (
        resolve_manifest_path(
            split_value,
            manifest_run_root=manifest_run_root,
            local_run_root=local_run_root,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
        )
        if isinstance(split_value, str) and split_value.strip()
        else None
    )
    if split_path is None:
        missing_tokens = sorted(set(protected_case_tokens))
        return _missing_split_status(
            split_value=split_value,
            split_path=None,
            split_readable=False,
            protected_cases=protected_cases,
            missing_tokens=missing_tokens,
            error="split_path_unresolvable",
        )

    try:
        data = yaml.safe_load(split_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        missing_tokens = sorted(set(protected_case_tokens))
        return _missing_split_status(
            split_value=split_value,
            split_path=str(split_path),
            split_readable=False,
            protected_cases=protected_cases,
            missing_tokens=missing_tokens,
            error=f"{type(exc).__name__}: {exc}",
        )

    if not isinstance(data, dict):
        missing_tokens = sorted(set(protected_case_tokens))
        return _missing_split_status(
            split_value=split_value,
            split_path=str(split_path),
            split_readable=True,
            protected_cases=protected_cases,
            missing_tokens=missing_tokens,
            error=f"split_yaml_not_mapping:{type(data).__name__}",
        )

    stage_membership: dict[str, list[str]] = {
        case: [] for case in sorted(set(protected_case_tokens))
    }
    split_case_tokens: set[str] = set()
    for stage in CVRP_SPLIT_CASE_STAGES:
        cases = data.get(stage)
        if not isinstance(cases, list):
            continue
        for raw_case in _string_items(cases):
            token = _cvrp_case_token(raw_case)
            split_case_tokens.add(token)
            if token in stage_membership:
                stage_membership[token].append(stage)

    missing_cases = sorted(
        case for case in set(protected_case_tokens) if case not in split_case_tokens
    )
    present_cases = sorted(
        case for case in set(protected_case_tokens) if case in split_case_tokens
    )
    missing_screening_cases = sorted(
        case
        for case, stages in stage_membership.items()
        if "screening" not in stages
    )
    return {
        "complete": bool(protected_case_tokens)
        and not missing_cases
        and not missing_screening_cases,
        "split": split_value,
        "split_path": str(split_path),
        "split_readable": True,
        "protected_cases": protected_cases,
        "present_cases": present_cases,
        "missing_cases": missing_cases,
        "missing_screening_cases": missing_screening_cases,
        "stage_membership": stage_membership,
        "case_count": len(split_case_tokens),
        "stages_checked": list(CVRP_SPLIT_CASE_STAGES),
        "required_stage": "screening",
        "error": None,
    }


def cvrp_protected_cases_priority_status(
    config: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    manifest_run_root: str = "",
    local_run_root: Path | None = None,
    repo_dir: Path,
    scion_project_dir: Path,
) -> dict[str, Any]:
    protected_cases = _string_items(requirements.get("protected_cases"))
    protected_case_tokens = [_cvrp_case_token(item) for item in protected_cases]
    protocol_value = config.get("protocol")
    protocol_path = (
        resolve_manifest_path(
            protocol_value,
            manifest_run_root=manifest_run_root,
            local_run_root=local_run_root,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
        )
        if isinstance(protocol_value, str) and protocol_value.strip()
        else None
    )
    if protocol_path is None:
        return _missing_priority_status(
            protocol_value=protocol_value,
            protocol_path=None,
            protocol_readable=False,
            protected_cases=protected_cases,
            missing_tokens=sorted(set(protected_case_tokens)),
            error="protocol_path_unresolvable",
        )

    try:
        data = yaml.safe_load(protocol_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return _missing_priority_status(
            protocol_value=protocol_value,
            protocol_path=str(protocol_path),
            protocol_readable=False,
            protected_cases=protected_cases,
            missing_tokens=sorted(set(protected_case_tokens)),
            error=f"{type(exc).__name__}: {exc}",
        )

    screening = data.get("screening") if isinstance(data, dict) else None
    priority_case_ids = (
        _string_items(screening.get("priority_case_ids"))
        if isinstance(screening, Mapping)
        else []
    )
    priority_tokens = {_cvrp_case_token(item) for item in priority_case_ids}
    missing_cases = sorted(
        case for case in set(protected_case_tokens) if case not in priority_tokens
    )
    present_cases = sorted(
        case for case in set(protected_case_tokens) if case in priority_tokens
    )
    return {
        "complete": bool(protected_case_tokens) and not missing_cases,
        "protocol": protocol_value,
        "protocol_path": str(protocol_path),
        "protocol_readable": True,
        "protected_cases": protected_cases,
        "priority_case_ids": priority_case_ids,
        "present_priority_cases": present_cases,
        "missing_priority_cases": missing_cases,
        "required_stage": "screening",
        "error": None,
    }


def _missing_split_status(
    *,
    split_value: Any,
    split_path: str | None,
    split_readable: bool,
    protected_cases: list[str],
    missing_tokens: list[str],
    error: str,
) -> dict[str, Any]:
    return {
        "complete": False,
        "split": split_value,
        "split_path": split_path,
        "split_readable": split_readable,
        "protected_cases": protected_cases,
        "present_cases": [],
        "missing_cases": missing_tokens,
        "missing_screening_cases": missing_tokens,
        "stage_membership": {},
        "case_count": 0,
        "required_stage": "screening",
        "error": error,
    }


def _missing_priority_status(
    *,
    protocol_value: Any,
    protocol_path: str | None,
    protocol_readable: bool,
    protected_cases: list[str],
    missing_tokens: list[str],
    error: str,
) -> dict[str, Any]:
    return {
        "complete": False,
        "protocol": protocol_value,
        "protocol_path": protocol_path,
        "protocol_readable": protocol_readable,
        "protected_cases": protected_cases,
        "priority_case_ids": [],
        "present_priority_cases": [],
        "missing_priority_cases": missing_tokens,
        "required_stage": "screening",
        "error": error,
    }


def _cvrp_case_token(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    return Path(text).stem.upper()


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []
