"""Dynamic loader for ProblemAdapter implementations.

Loads a ProblemAdapter from the import_path specified in ProblemSpecV1.
All adapters must live under ``scion.problems.<id>.*`` — this is enforced
both by ProblemSpecV1 validation and by the loader itself.
"""
from __future__ import annotations

import importlib
from typing import cast

from scion.problem.contracts import ProblemAdapter
from scion.problem.spec import ProblemSpecV1


class ProblemAdapterLoadError(RuntimeError):
    pass


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
