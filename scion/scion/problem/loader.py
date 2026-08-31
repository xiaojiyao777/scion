"""Dynamic loaders for ProblemSpecV1 definitions and their adapters.

Loads a ProblemAdapter from the import_path specified in ProblemSpecV1.
All adapters must live under ``scion.problems.<id>.*`` — this is enforced
both by ProblemSpecV1 validation and by the loader itself.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import cast

import yaml

from scion.problem.contracts import ProblemAdapter
from scion.problem.spec import ProblemSpecV1


class ProblemAdapterLoadError(RuntimeError):
    pass


def load_problem_spec_v1_from_yaml(path: str | Path) -> ProblemSpecV1:
    """Load ProblemSpecV1, resolving root_dir relative to the YAML file."""

    spec_path = Path(path).expanduser().resolve()
    with open(spec_path, encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    root_dir = str(payload.get("root_dir") or "").strip()
    if not root_dir or root_dir == "PLACEHOLDER":
        payload["root_dir"] = str(spec_path.parent)
    else:
        root_path = Path(root_dir).expanduser()
        if not root_path.is_absolute():
            payload["root_dir"] = str((spec_path.parent / root_path).resolve())
    return ProblemSpecV1(**payload)


def adapter_package_prefixes(spec: object) -> tuple[str, ...]:
    """Return the package containing the adapter declared by *spec*.

    Source-research code uses this ordinary declaration to follow adjacent
    imports without assuming where problem packages live in the repository.
    """

    adapter_ref = getattr(spec, "adapter", None)
    import_path = str(
        getattr(adapter_ref, "import_path", None)
        or getattr(spec, "adapter_import_path", None)
        or ""
    ).strip()
    module_path = import_path.split(":", 1)[0].strip()
    if not module_path or "." not in module_path:
        return ()
    package = module_path.rsplit(".", 1)[0].strip(".")
    return (f"{package}.",) if package else ()


def load_problem_adapter(spec: ProblemSpecV1) -> ProblemAdapter:
    """Import and instantiate a ProblemAdapter from *spec*.

    The import_path format is ``module.path:ClassName``.
    """
    import_path = spec.adapter.import_path
    if ":" not in import_path:
        raise ProblemAdapterLoadError(
            f"adapter import_path must use 'module:Class' format, got '{import_path}'"
        )

    module_path, class_name = import_path.rsplit(":", 1)

    allowed_prefix = f"scion.problems.{spec.id}."
    if not module_path.startswith(allowed_prefix):
        raise ProblemAdapterLoadError(
            f"adapter module must start with '{allowed_prefix}', got '{module_path}'"
        )

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ProblemAdapterLoadError(
            f"cannot import adapter module '{module_path}': {exc}"
        ) from exc

    cls = getattr(module, class_name, None)
    if cls is None:
        raise ProblemAdapterLoadError(
            f"module '{module_path}' has no attribute '{class_name}'"
        )

    try:
        adapter = cls(spec)
    except TypeError as exc:
        raise ProblemAdapterLoadError(
            f"failed to instantiate {class_name}(spec): {exc}"
        ) from exc

    if not isinstance(adapter, ProblemAdapter):
        raise ProblemAdapterLoadError(
            f"{import_path} does not implement ProblemAdapter protocol"
        )

    return cast(ProblemAdapter, adapter)
