"""Problem data-root activation for file-backed experiment splits."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

GENERIC_DATA_ROOT_ENV = "SCION_PROBLEM_DATA_ROOT"


@dataclass(frozen=True)
class DataRootActivation:
    env_name: str
    data_root: Path | None
    source: Path
    activated: bool


def activate_declared_problem_data_root(
    *,
    problem_yaml: Path,
    protocol_path: Path | None,
) -> DataRootActivation | None:
    """Activate a data root declared by protocol-side budget metadata.

    The framework stays problem-agnostic here: a problem package may declare a
    data-root environment variable in a sibling ``budgets.json``. When copied
    experiment configs omit that file, an explicit ``SCION_PROBLEM_DATA_ROOT``
    environment variable still wires strict case-path safety for the run.
    """

    budgets_path = _budgets_path_for_protocol(protocol_path)
    if budgets_path is None:
        fallback = _generic_env_data_root(problem_yaml)
        if fallback is not None:
            return fallback
        return None

    budget = _load_budget_json(budgets_path)
    env_name = str(budget.get("data_root_env") or "").strip()
    rel_root = str(budget.get("data_root_expected_repo_relative") or "").strip()
    if not env_name or not rel_root:
        return None

    existing = os.environ.get(env_name, "").strip()
    if existing:
        return DataRootActivation(
            env_name=env_name,
            data_root=Path(existing).expanduser().resolve(strict=False),
            source=budgets_path,
            activated=False,
        )

    data_root = _find_repo_relative_root(
        start=budgets_path.parent,
        relative_path=Path(rel_root),
    )
    if data_root is None:
        data_root = _find_repo_relative_root(
            start=problem_yaml.parent,
            relative_path=Path(rel_root),
        )
    if data_root is None:
        return DataRootActivation(
            env_name=env_name,
            data_root=None,
            source=budgets_path,
            activated=False,
        )

    os.environ[env_name] = str(data_root)
    return DataRootActivation(
        env_name=env_name,
        data_root=data_root,
        source=budgets_path,
        activated=True,
    )


def validate_declared_problem_data_cases(
    *,
    activation: DataRootActivation | None,
    problem_yaml: Path,
    split_manifest: Any,
) -> None:
    """Fail before a campaign if declared data-root cases are not resolvable."""

    if activation is None or not activation.env_name:
        return

    roots = _declared_data_roots(activation)
    missing = missing_problem_data_cases(
        problem_yaml=problem_yaml,
        split_manifest=split_manifest,
        data_roots=roots,
    )

    if missing:
        missing_detail = ", ".join(missing)
        roots_text = ", ".join(str(root) for root in roots) or "<unset>"
        raise ValueError(
            "split manifest contains data-root-relative cases that do not resolve "
            f"via {activation.env_name}={roots_text}: {missing_detail}"
        )


def missing_problem_data_cases(
    *,
    problem_yaml: Path,
    split_manifest: Any,
    data_roots: Sequence[str | Path],
) -> list[str]:
    """Return cases unresolved by exactly the supplied roots.

    This pure form is used by launch preparation, where an ambient data-root
    environment variable must not silently replace the path written into the
    prepared run contract.
    """

    roots = _dedupe_paths(
        [Path(root).expanduser().resolve(strict=False) for root in data_roots]
    )
    return [
        case
        for case in _all_split_cases(split_manifest)
        if resolve_problem_data_case(
            case,
            problem_dir=problem_yaml.parent,
            data_roots=roots,
        )
        is None
    ]


def resolve_problem_data_case(
    case: str,
    *,
    problem_dir: Path,
    data_roots: Sequence[str | Path],
) -> Path | None:
    """Resolve one case without CWD lookup or allowed-root escape."""

    roots = _dedupe_paths(
        [
            problem_dir.expanduser().resolve(strict=False),
            *(
                Path(root).expanduser().resolve(strict=False)
                for root in data_roots
            ),
        ]
    )
    path = Path(case).expanduser()
    if path.is_absolute():
        resolved = path.resolve(strict=False)
        if (
            path.is_file()
            and not path.is_symlink()
            and any(resolved.is_relative_to(root) for root in roots)
        ):
            return resolved
        return None
    for root in roots:
        candidate = root / path
        resolved = candidate.resolve(strict=False)
        if (
            resolved.is_relative_to(root)
            and candidate.is_file()
            and not candidate.is_symlink()
        ):
            return resolved
    return None


def with_declared_problem_data_roots(
    *,
    activation: DataRootActivation | None,
    split_manifest: Any,
) -> Any:
    """Return a split manifest whose safe roots include declared data roots."""

    roots = _declared_data_roots(activation)
    if not roots:
        return split_manifest

    combined = _dedupe_paths(
        [
            *(
                Path(root).expanduser().resolve(strict=False)
                for root in getattr(split_manifest, "safe_data_roots", ()) or ()
                if str(root).strip()
            ),
            *roots,
        ]
    )
    safe_data_roots = [str(root) for root in combined]
    if safe_data_roots == list(getattr(split_manifest, "safe_data_roots", ()) or ()):
        return split_manifest

    model_copy = getattr(split_manifest, "model_copy", None)
    if callable(model_copy):
        return model_copy(update={"safe_data_roots": safe_data_roots})

    setattr(split_manifest, "safe_data_roots", safe_data_roots)
    return split_manifest


def _budgets_path_for_protocol(protocol_path: Path | None) -> Path | None:
    if protocol_path is None:
        return None
    candidate = Path(protocol_path).expanduser().resolve(strict=False).parent / "budgets.json"
    return candidate if candidate.exists() else None


def _load_budget_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _generic_env_data_root(source: Path) -> DataRootActivation | None:
    """Use the explicit generic data-root env when copied configs lack budgets."""

    existing = os.environ.get(GENERIC_DATA_ROOT_ENV, "").strip()
    if not existing:
        return None
    return DataRootActivation(
        env_name=GENERIC_DATA_ROOT_ENV,
        data_root=Path(existing).expanduser().resolve(strict=False),
        source=source,
        activated=False,
    )


def _find_repo_relative_root(*, start: Path, relative_path: Path) -> Path | None:
    for base in (start, *start.parents):
        candidate = (base / relative_path).expanduser().resolve(strict=False)
        if candidate.exists():
            return candidate
    return None


def _all_split_cases(split_manifest: Any) -> list[str]:
    cases: list[str] = []
    for name in ("screening", "validation", "frozen", "canary"):
        value = getattr(split_manifest, name, ()) or ()
        cases.extend(str(case) for case in value if str(case))
    return cases


def _declared_data_roots(activation: DataRootActivation | None) -> list[Path]:
    if activation is None or not activation.env_name:
        return []

    roots: list[Path] = []
    env_value = os.environ.get(activation.env_name, "").strip()
    if env_value:
        roots.append(Path(env_value).expanduser().resolve(strict=False))
    if activation.data_root is not None:
        roots.append(Path(activation.data_root).expanduser().resolve(strict=False))
    return _dedupe_paths(roots)


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


__all__ = (
    "DataRootActivation",
    "activate_declared_problem_data_root",
    "missing_problem_data_cases",
    "resolve_problem_data_case",
    "validate_declared_problem_data_cases",
    "with_declared_problem_data_roots",
)
