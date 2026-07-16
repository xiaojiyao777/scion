from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import logging
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scion.core.models import RunResult, SolverOutput
from scion.runtime.runner import resolve_offloaded

logger = logging.getLogger(__name__)

_SOLVER_OUTPUT_FRAMEWORK_FIELDS = frozenset(
    {"objective", "feasible", "runtime", "solution_payload"}
)


CHAMPION_RESULT_CACHE_KEY_SCHEMA = "scion.champion_result_cache.key.v1"
CHAMPION_RESULT_CACHE_VALUE_SCHEMA = "scion.champion_result_cache.value.v1"
RUNNER_RUNTIME_SCHEMA = "scion.runner_runtime.v1"

_TRANSIENT_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "logs",
        "metrics",
        "temp",
        "tmp",
        "venv",
    }
)
_TRANSIENT_FILE_NAMES = frozenset(
    {
        ".coverage",
        ".DS_Store",
    }
)
_TRANSIENT_SUFFIXES = (".log", ".pyc", ".pyo", ".swp", ".tmp")


class ChampionResultCache:
    """Persistent champion-side result cache for generic experiment runs."""

    def __init__(self, cache_dir: str | os.PathLike[str]) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_key(
        self,
        *,
        champion_workspace: str,
        case_path: str,
        seed: int,
        time_limit_sec: int | float,
        selected_surface: str | None,
        runner: Any,
        metric_specs: Sequence[Any] | None = None,
        objective_policy: Any | None = None,
        problem_spec: Any | None = None,
        workspace_digest: str | None = None,
    ) -> dict[str, Any]:
        key = {
            "schema": CHAMPION_RESULT_CACHE_KEY_SCHEMA,
            "workspace_role": "champion",
            "workspace": {
                "path": str(Path(champion_workspace).resolve(strict=False)),
                "digest": workspace_digest
                or compute_workspace_digest(champion_workspace),
            },
            "case": _case_identity(case_path),
            "seed": int(seed),
            "time_limit_sec": _canonical_number(time_limit_sec),
            "selected_surface": selected_surface or None,
            "objective_digest": objective_digest(
                metric_specs=metric_specs,
                objective_policy=objective_policy,
                problem_spec=problem_spec,
            ),
            "runner_runtime": runner_runtime_identity(
                runner,
                selected_surface=selected_surface,
            ),
        }
        key["digest"] = stable_digest(key)
        return key

    def get(self, key: Mapping[str, Any]) -> RunResult | None:
        path = self._entry_path(str(key.get("digest") or ""))
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("schema") != CHAMPION_RESULT_CACHE_VALUE_SCHEMA:
            return None
        if payload.get("key") != dict(key):
            return None
        result_payload = payload.get("run_result")
        if not isinstance(result_payload, Mapping):
            return None
        return _run_result_from_payload(result_payload)

    def put(self, key: Mapping[str, Any], result: RunResult) -> bool:
        if not cacheable_champion_result(result):
            return False
        try:
            result_payload = _run_result_to_payload(result)
        except OSError as exc:
            logger.warning(
                "Champion result cache skipped unreadable stdout/stderr offload: %s",
                exc,
            )
            return False
        payload = {
            "schema": CHAMPION_RESULT_CACHE_VALUE_SCHEMA,
            "key": dict(key),
            "run_result": result_payload,
        }
        path = self._entry_path(str(key.get("digest") or stable_digest(key)))
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
            os.replace(tmp_name, path)
            return True
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _entry_path(self, digest: str) -> Path:
        clean = "".join(ch for ch in digest if ch in "0123456789abcdef")
        if len(clean) < 8:
            clean = hashlib.sha256(digest.encode("utf-8")).hexdigest()
        return self.cache_dir / clean[:2] / f"{clean}.json"


def cacheable_champion_result(result: RunResult) -> bool:
    return bool(result.success and result.output is not None)


def compute_workspace_digest(workspace: str | os.PathLike[str]) -> str:
    root = Path(workspace).resolve(strict=False)
    h = hashlib.sha256()
    h.update(CHAMPION_RESULT_CACHE_KEY_SCHEMA.encode("utf-8"))
    h.update(b"\0workspace\0")
    h.update(str(root).encode("utf-8", errors="surrogateescape"))
    if not root.exists():
        h.update(b"\0missing")
        return h.hexdigest()
    if root.is_file():
        h.update(b"\0file\0")
        h.update(_safe_file_digest(root).encode("ascii"))
        return h.hexdigest()
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not _is_transient_name(d, is_dir=True))
        current_path = Path(current)
        for filename in sorted(files):
            if _is_transient_name(filename, is_dir=False):
                continue
            path = current_path / filename
            rel = path.relative_to(root).as_posix()
            h.update(b"\0path\0")
            h.update(rel.encode("utf-8", errors="surrogateescape"))
            h.update(b"\0sha256\0")
            h.update(_safe_file_digest(path).encode("ascii"))
    return h.hexdigest()


def objective_digest(
    *,
    metric_specs: Sequence[Any] | None = None,
    objective_policy: Any | None = None,
    problem_spec: Any | None = None,
) -> str:
    policy = objective_policy
    if policy is None and problem_spec is not None:
        policy = getattr(problem_spec, "objective_policy", None)
    metrics = metric_specs
    if metrics is None and problem_spec is not None:
        metrics = getattr(problem_spec, "objectives", None)
    return stable_digest(
        {
            "objective_policy": _stable_payload(policy),
            "metric_specs": _stable_payload(metrics),
        }
    )


def runner_runtime_identity(
    runner: Any,
    *,
    selected_surface: str | None = None,
) -> dict[str, Any]:
    runner_type = type(runner)
    payload: dict[str, Any] = {
        "schema": RUNNER_RUNTIME_SCHEMA,
        "class": f"{runner_type.__module__}.{runner_type.__qualname__}",
    }
    for attr in ("schema_version", "version", "runtime_schema"):
        value = getattr(runner, attr, None)
        if value is not None:
            payload[attr] = str(value)
    runtime_identity = _runner_runtime_identity_payload(
        runner,
        selected_surface=selected_surface,
    )
    if runtime_identity is not None:
        payload["runtime_identity"] = runtime_identity
    return payload


def _runner_runtime_identity_payload(
    runner: Any,
    *,
    selected_surface: str | None,
) -> Any | None:
    for method_name in ("cache_identity", "runtime_identity"):
        try:
            inspect.getattr_static(runner, method_name)
        except AttributeError:
            continue
        method = getattr(runner, method_name, None)
        if not callable(method):
            continue
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            return _stable_payload(method())
        parameters = signature.parameters
        accepts_selected_surface = (
            "selected_surface" in parameters
            or any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )
        )
        if accepts_selected_surface:
            return _stable_payload(method(selected_surface=selected_surface))
        return _stable_payload(method())
    return None


def stable_digest(value: Any) -> str:
    encoded = json.dumps(
        _stable_payload(value),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _case_identity(case_path: str) -> dict[str, Any]:
    path = Path(case_path).resolve(strict=False)
    payload: dict[str, Any] = {"path": str(path)}
    if path.exists() and path.is_file():
        payload["content_digest"] = _safe_file_digest(path)
    else:
        payload["content_digest"] = None
        try:
            stat = path.stat()
        except OSError:
            payload["stat_digest"] = None
        else:
            payload["stat_digest"] = stable_digest(
                {
                    "mtime_ns": stat.st_mtime_ns,
                    "size": stat.st_size,
                }
            )
    return payload


def _run_result_to_payload(result: RunResult) -> dict[str, Any]:
    stdout = resolve_offloaded(result.stdout or "")
    stderr = resolve_offloaded(result.stderr or "")
    return {
        "success": result.success,
        "exit_code": result.exit_code,
        "elapsed_ms": result.elapsed_ms,
        "output": _solver_output_to_payload(result.output),
        "error_category": result.error_category,
        "stdout_sha256": _text_digest(stdout),
        "stderr_sha256": _text_digest(stderr),
        "stdout": stdout,
        "stderr": stderr,
    }


def _run_result_from_payload(payload: Mapping[str, Any]) -> RunResult | None:
    output_payload = payload.get("output")
    output = (
        _solver_output_from_payload(output_payload)
        if isinstance(output_payload, Mapping)
        else None
    )
    if output is None:
        return None
    return RunResult(
        success=bool(payload.get("success")),
        exit_code=int(payload.get("exit_code") or 0),
        stdout=str(payload.get("stdout") or ""),
        stderr=str(payload.get("stderr") or ""),
        elapsed_ms=int(payload.get("elapsed_ms") or 0),
        output=output,
        error_category=payload.get("error_category"),
    )


def _solver_output_to_payload(output: SolverOutput | None) -> dict[str, Any] | None:
    if output is None:
        return None
    return dataclasses.asdict(output)


def _solver_output_from_payload(payload: Mapping[str, Any]) -> SolverOutput:
    solution_payload = payload.get("solution_payload")
    if not isinstance(solution_payload, Mapping):
        solution_payload = {
            key: value
            for key, value in payload.items()
            if key not in _SOLVER_OUTPUT_FRAMEWORK_FIELDS
        }
    return SolverOutput(
        objective=dict(payload.get("objective") or {}),
        feasible=bool(payload.get("feasible")),
        runtime=dict(payload.get("runtime") or {}),
        solution_payload=dict(solution_payload),
    )


def _safe_file_digest(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError as exc:
        h.update(type(exc).__name__.encode("utf-8"))
        h.update(str(exc).encode("utf-8", errors="replace"))
    return h.hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _stable_payload(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _stable_payload(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_stable_payload(item) for item in value]
    if dataclasses.is_dataclass(value):
        return _stable_payload(dataclasses.asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _stable_payload(model_dump(mode="json"))
        except TypeError:
            return _stable_payload(model_dump())
    if hasattr(value, "__dict__"):
        return _stable_payload(
            {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        )
    return repr(value)


def _is_transient_name(name: str, *, is_dir: bool) -> bool:
    if is_dir:
        return name in _TRANSIENT_DIR_NAMES
    return name in _TRANSIENT_FILE_NAMES or name.endswith(_TRANSIENT_SUFFIXES)


def _canonical_number(value: int | float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else number


__all__ = [
    "CHAMPION_RESULT_CACHE_KEY_SCHEMA",
    "CHAMPION_RESULT_CACHE_VALUE_SCHEMA",
    "ChampionResultCache",
    "cacheable_champion_result",
    "compute_workspace_digest",
    "objective_digest",
    "runner_runtime_identity",
    "stable_digest",
]
