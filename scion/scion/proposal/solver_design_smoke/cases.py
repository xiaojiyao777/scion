"""Smoke case selection and instance path resolution."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Mapping

import yaml

from scion.core.models import ExperimentStage

from .constants import (
    _ALGORITHM_SMOKE_DEFAULT_SEED,
    _ALGORITHM_SMOKE_MAX_SCREENING_CASES,
)
from .models import _RuntimeSmokeCase
from .utils import _attr

if TYPE_CHECKING:
    from scion.proposal.tools import ProposalToolContext
else:
    ProposalToolContext = Any


def _runtime_smoke_cases(
    *,
    workspace: Path,
    base_workspace: Path,
    canary_rel: str,
    split_manifest: Any = None,
    seed_ledger: Any = None,
    safe_data_roots: Any = None,
) -> tuple[list[_RuntimeSmokeCase], list[str]]:
    cases: list[_RuntimeSmokeCase] = []
    missing: list[str] = []
    seen: set[tuple[str, int]] = set()

    def add_case(label: str, rel_path: Any, seed: Any, case_source: str) -> None:
        rel = str(rel_path or "").strip()
        if not rel:
            return
        try:
            seed_value = int(seed)
        except (TypeError, ValueError):
            seed_value = _ALGORITHM_SMOKE_DEFAULT_SEED
        key = (rel, seed_value)
        if key in seen:
            return
        seen.add(key)
        resolution = _resolve_smoke_instance(
            workspace=workspace,
            base_workspace=base_workspace,
            case_rel=rel,
            safe_data_roots=safe_data_roots,
            case_source=case_source,
        )
        if resolution["path"] is None:
            missing.append(f"{label} smoke case not found: {rel}")
            return
        cases.append(
            _RuntimeSmokeCase(
                label=label,
                rel_path=rel,
                seed=seed_value,
                path=resolution["path"],
                data_root=resolution["data_root"],
                data_root_source=resolution["data_root_source"],
                data_root_status=resolution["data_root_status"],
                case_source=case_source,
            )
        )

    if split_manifest is None:
        split_manifest = _load_runtime_smoke_yaml(
            workspace=workspace,
            base_workspace=base_workspace,
            filename="split_manifest.yaml",
        )
    if seed_ledger is None:
        seed_ledger = _load_runtime_smoke_yaml(
            workspace=workspace,
            base_workspace=base_workspace,
            filename="seed_ledger.yaml",
        )
    if safe_data_roots is None:
        safe_data_roots = _runtime_smoke_safe_data_roots_from_manifest(split_manifest)

    canary_seed = _first_int(
        _runtime_smoke_stage_value(seed_ledger, "canary"),
        _ALGORITHM_SMOKE_DEFAULT_SEED,
    )
    canary_cases = _string_list(_runtime_smoke_stage_value(split_manifest, "canary"))
    case_source = _runtime_smoke_case_source(split_manifest)
    if canary_rel and canary_rel not in canary_cases:
        canary_cases.append(canary_rel)
    for rel in canary_cases[:1]:
        add_case("canary", rel, canary_seed, case_source)

    screening_seed = _first_int(
        _runtime_smoke_stage_value(seed_ledger, "screening"),
        _ALGORITHM_SMOKE_DEFAULT_SEED,
    )
    screening_cases = _select_runtime_smoke_screening_cases(
        _string_list(_runtime_smoke_stage_value(split_manifest, "screening")),
        _ALGORITHM_SMOKE_MAX_SCREENING_CASES,
    )
    for rel in screening_cases:
        add_case("screening", rel, screening_seed, case_source)
    return cases, missing


def _runtime_smoke_stage_value(source: Any, stage: str) -> Any:
    if source is None:
        return None
    if isinstance(source, Mapping):
        return source.get(stage)
    if stage == "canary":
        getter = getattr(source, "get_canary_cases", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        seed_getter = getattr(source, "get_canary_seeds", None)
        if callable(seed_getter):
            try:
                return seed_getter()
            except Exception:
                return None
    getter = getattr(source, "get_cases", None)
    if callable(getter):
        arguments = _runtime_smoke_stage_arguments(stage)
        for argument in arguments:
            try:
                return getter(argument)
            except Exception:
                continue
    seed_getter = getattr(source, "get_seeds", None)
    if callable(seed_getter):
        arguments = _runtime_smoke_stage_arguments(stage)
        for argument in arguments:
            try:
                return seed_getter(argument)
            except Exception:
                continue
    try:
        return getattr(source, stage)
    except Exception:
        return None


def _runtime_smoke_stage_arguments(stage: str) -> tuple[Any, ...]:
    enum_stage = getattr(ExperimentStage, stage.upper(), None)
    if enum_stage is None:
        return (stage,)
    return (enum_stage, stage)


def _select_runtime_smoke_screening_cases(paths: list[str], max_cases: int) -> list[str]:
    cases = [path for path in paths if str(path or "").strip()]
    total = len(cases)
    if max_cases <= 0 or total <= 0:
        return []
    if max_cases >= total:
        return cases
    if max_cases == 1:
        return [cases[total // 2]]

    indices = [round(i * (total - 1) / (max_cases - 1)) for i in range(max_cases)]
    selected: list[int] = []
    seen: set[int] = set()
    for idx in indices:
        if idx in seen:
            continue
        selected.append(idx)
        seen.add(idx)
    for idx in range(total):
        if len(selected) >= max_cases:
            break
        if idx in seen:
            continue
        selected.append(idx)
        seen.add(idx)
    return [cases[idx] for idx in sorted(selected[:max_cases])]


def _load_runtime_smoke_yaml(
    *,
    workspace: Path,
    base_workspace: Path,
    filename: str,
) -> Mapping[str, Any]:
    for root in (workspace, base_workspace):
        path = root / filename
        if not path.is_file():
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        if isinstance(payload, Mapping):
            return payload
        return {}
    return {}


def _first_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, (str, bytes)):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)
    else:
        candidates = []
    for item in candidates:
        try:
            return int(item)
        except (TypeError, ValueError):
            continue
    return default


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, (list, tuple)):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            result.append(text)
    return result


def _runtime_smoke_safe_data_roots(context: ProposalToolContext) -> tuple[Path, ...]:
    roots: list[Any] = []
    for source in (
        getattr(context, "split_manifest", None),
        getattr(context, "problem_spec", None),
        _attr(getattr(context, "adapter", None), "spec"),
    ):
        roots.extend(_runtime_smoke_safe_data_roots_from_manifest(source))
    return _normalize_runtime_smoke_safe_roots(roots)


def _runtime_smoke_safe_data_roots_from_manifest(source: Any) -> list[Any]:
    if source is None:
        return []
    values: list[Any] = []
    keys = (
        "safe_data_roots",
        "safe_data_root",
        "data_roots",
        "data_root",
        "problem_data_roots",
        "problem_data_root",
    )
    for key in keys:
        value = _attr(source, key)
        if value in (None, "", [], ()):
            continue
        if isinstance(value, Mapping):
            values.extend(value.values())
        elif isinstance(value, (list, tuple, set)):
            values.extend(value)
        else:
            values.append(value)
    return values


def _normalize_runtime_smoke_safe_roots(value: Any) -> tuple[Path, ...]:
    if value in (None, "", [], ()):
        return ()
    raw_values = value if isinstance(value, (list, tuple, set)) else (value,)
    roots: list[Path] = []
    seen: set[str] = set()
    for item in raw_values:
        text = str(item or "").strip()
        if not text:
            continue
        root = Path(text).expanduser().resolve(strict=False)
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        roots.append(root)
    return tuple(roots)


def _runtime_smoke_case_source(split_manifest: Any) -> str:
    if split_manifest is None:
        return "workspace_split_manifest"
    source = str(_attr(split_manifest, "source") or "").strip()
    if source:
        return source
    if isinstance(split_manifest, Mapping):
        return "campaign_config_manifest"
    return "campaign_split_manifest"


def _runtime_smoke_relative_path(case_rel: str) -> Path | None:
    text = str(case_rel or "").replace("\\", "/").strip()
    if not text:
        return None
    pure = PurePosixPath(text)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    return Path(*pure.parts)


def _runtime_smoke_candidate_within_root(
    path: Path,
    *,
    workspace: Path,
    base_workspace: Path,
    safe_data_roots: Any,
) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    roots = (
        workspace.expanduser().resolve(strict=False),
        base_workspace.expanduser().resolve(strict=False),
        *_normalize_runtime_smoke_safe_roots(safe_data_roots),
    )
    for root in roots:
        try:
            candidate.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _runtime_smoke_audited_manifest_ref(
    *,
    workspace: Path,
    base_workspace: Path,
    rel_path: str,
) -> str | None:
    for root in (workspace, base_workspace):
        root = root.expanduser().resolve(strict=False)
        for manifest_path in sorted(root.glob("**/manifests/*.json")):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, Mapping):
                continue
            cases = payload.get("cases")
            if not isinstance(cases, list):
                continue
            for case in cases:
                if not isinstance(case, Mapping):
                    continue
                if str(case.get("source_path") or "").strip() != rel_path:
                    continue
                try:
                    return manifest_path.relative_to(root).as_posix()
                except ValueError:
                    return "problem_case_manifest"
    return None


def _runtime_smoke_case_public_payload(
    smoke_case: _RuntimeSmokeCase,
) -> dict[str, Any]:
    case_ref = f"{smoke_case.data_root_source}:{smoke_case.rel_path}"
    provenance = {
        "source": smoke_case.case_source,
        "case_path_ref": case_ref,
        "data_root_source": smoke_case.data_root_source,
        "data_root_status": smoke_case.data_root_status,
        "absolute_paths_exposed": False,
    }
    return {
        "case": smoke_case.rel_path,
        "resolved_case_path": smoke_case.rel_path,
        "case_path_ref": case_ref,
        "data_root": smoke_case.data_root,
        "data_root_source": smoke_case.data_root_source,
        "data_root_status": smoke_case.data_root_status,
        "provenance": provenance,
    }


def _runtime_smoke_payload_provenance(
    representative: Mapping[str, Any],
) -> dict[str, Any]:
    provenance = representative.get("provenance")
    if isinstance(provenance, Mapping):
        result = dict(provenance)
    else:
        result = {
            "source": "runtime_smoke_manifest",
            "absolute_paths_exposed": False,
        }
    result.setdefault("absolute_paths_exposed", False)
    return result


def _resolve_smoke_instance_path(
    *,
    workspace: Path,
    base_workspace: Path,
    case_rel: str,
    safe_data_roots: Any = None,
) -> Path | None:
    return _resolve_smoke_instance(
        workspace=workspace,
        base_workspace=base_workspace,
        case_rel=case_rel,
        safe_data_roots=safe_data_roots,
    )["path"]


def _resolve_smoke_instance(
    *,
    workspace: Path,
    base_workspace: Path,
    case_rel: str,
    safe_data_roots: Any = None,
    case_source: str = "runtime_smoke_manifest",
) -> dict[str, Any]:
    rel = _runtime_smoke_relative_path(case_rel)
    if rel is None:
        path = Path(str(case_rel or ""))
        source = (
            "rejected_absolute_path" if path.is_absolute() else "rejected_case_path"
        )
        status = (
            "absolute_path_rejected"
            if path.is_absolute()
            else "unsafe_relative_rejected"
        )
        return {
            "path": None,
            "data_root": None,
            "data_root_source": source,
            "data_root_status": status,
        }
    candidates: list[tuple[Path, str | None, str, str]] = []
    candidates.append(
        (workspace / rel, "workspace", "workspace", "safe_root_relative")
    )
    candidates.append(
        (
            base_workspace / rel,
            "base_workspace",
            "base_workspace",
            "safe_root_relative",
        )
    )
    for index, safe_root in enumerate(
        _normalize_runtime_smoke_safe_roots(safe_data_roots)
    ):
        candidates.append(
            (
                safe_root / rel,
                f"safe_data_root:{index}",
                "safe_data_root",
                "safe_root_relative",
            )
        )
    for path, data_root, source, status in candidates:
        if not _runtime_smoke_candidate_within_root(
            path,
            workspace=workspace,
            base_workspace=base_workspace,
            safe_data_roots=safe_data_roots,
        ):
            continue
        if path.is_file():
            manifest_ref = _runtime_smoke_audited_manifest_ref(
                workspace=workspace,
                base_workspace=base_workspace,
                rel_path=rel.as_posix(),
            )
            if manifest_ref:
                source = "audited_problem_data_manifest"
                status = "audited_manifest_relative"
                data_root = manifest_ref
            return {
                "path": path,
                "data_root": data_root,
                "data_root_source": source,
                "data_root_status": status,
            }
    return {
        "path": None,
        "data_root": None,
        "data_root_source": case_source,
        "data_root_status": "missing",
    }
