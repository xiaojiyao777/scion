"""Ephemeral, non-evidentiary development checks for code research.

This module is deliberately separate from :mod:`scion.verification.gate`.
Development observations are bounded hints for a provider research loop; they
are never VerificationResult values and cannot be reused as formal evidence.
"""

from __future__ import annotations

import math
import os
import resource
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from scion.contract.checks.security import check_import_whitelist, check_sensitive_api
from scion.contract.patch_graph import PatchSetGraph
from scion.core.models import PatchProposal, patch_file_changes
from scion.core.path_match import segment_glob_match
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_surface_index import editable_patterns
from scion.verification.interface import check_interface
from scion.verification.syntax import check_syntax
from scion.verification.undefined_names import check_undefined_names

DevelopmentCheckName = Literal[
    "D1_syntax",
    "D1b_undefined_names",
    "D2_interface",
    "D3_unit_tests",
    "D4_regression_tests",
]
DevelopmentOutcome = Literal[
    "passed",
    "failed",
    "timeout",
    "launch_error",
    "preflight_rejected",
    "unavailable",
]

_SUITE_NAMES = ("D3_unit_tests", "D4_regression_tests")
_BWRAP = Path("/usr/bin/bwrap")
_PRLIMIT = Path("/usr/bin/prlimit")
_SANDBOX_PYTHON_ROOT = "/opt/scion-python"
_SANDBOX_FRAMEWORK_ROOT = "/opt/scion-runtime"
_SANDBOX_WORKSPACE = "/work"


@dataclass(frozen=True)
class DevelopmentSuiteManifest:
    """Host-authored exact public test/support closure for one suite."""

    check_name: Literal["D3_unit_tests", "D4_regression_tests"]
    source_root: str
    test_path: str
    support_paths: tuple[str, ...] = ()

    @property
    def declared_paths(self) -> tuple[str, ...]:
        return (self.test_path, *self.support_paths)


@dataclass(frozen=True)
class DevelopmentCheckObservation:
    """One enum-only observation safe to project to the provider."""

    name: DevelopmentCheckName
    outcome: DevelopmentOutcome

    @property
    def passed(self) -> bool:
        return self.outcome == "passed"


@dataclass(frozen=True)
class DevelopmentCheckRun:
    """One non-evidentiary result from a fresh scratch candidate."""

    outcome: DevelopmentOutcome
    checks: tuple[DevelopmentCheckObservation, ...] = ()

    @property
    def passed(self) -> bool:
        return self.outcome == "passed"

    def provider_projection(self) -> dict[str, Any]:
        passed = sum(check.passed for check in self.checks)
        return {
            "outcome": self.outcome,
            "checks": [
                {"name": check.name, "outcome": check.outcome}
                for check in self.checks
            ],
            "counts": {
                "total": len(self.checks),
                "passed": passed,
                "failed": len(self.checks) - passed,
            },
        }


def declared_development_suites(problem_spec: Any) -> tuple[DevelopmentSuiteManifest, ...]:
    """Resolve the authoritative V1 host manifest without fallback discovery."""

    spec_v1 = getattr(problem_spec, "spec_v1", problem_spec)
    declarations = (
        (
            "D3_unit_tests",
            getattr(spec_v1, "development_unit_test_path", ""),
            getattr(spec_v1, "development_unit_test_support_paths", ()),
        ),
        (
            "D4_regression_tests",
            getattr(spec_v1, "development_regression_test_path", ""),
            getattr(spec_v1, "development_regression_test_support_paths", ()),
        ),
    )
    if not any(raw_test_path for _name, raw_test_path, _support in declarations):
        return ()
    root = Path(str(getattr(spec_v1, "root_dir", ""))).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("development suite root is not a directory")
    suites: list[DevelopmentSuiteManifest] = []
    for check_name, raw_test_path, raw_support_paths in declarations:
        if not raw_test_path:
            continue
        test_path = _canonical_manifest_path(raw_test_path)
        support_paths = tuple(
            _canonical_manifest_path(value) for value in raw_support_paths or ()
        )
        declared = (test_path, *support_paths)
        if len(declared) != len(set(declared)):
            raise ValueError("development suite contains duplicate declared files")
        for relative_path in declared:
            _authoritative_file(root, relative_path)
        suites.append(
            DevelopmentSuiteManifest(
                check_name=check_name,
                source_root=str(root),
                test_path=test_path,
                support_paths=support_paths,
            )
        )
    return tuple(suites)


def declared_development_workspace_paths(problem_spec: Any) -> tuple[str, ...]:
    """Return exact public files copied to the development workspace root."""

    spec_v1 = getattr(problem_spec, "spec_v1", problem_spec)
    paths = tuple(
        _canonical_manifest_path(path)
        for path in getattr(spec_v1, "development_workspace_paths", ()) or ()
    )
    _validate_declared_runtime_paths(spec_v1, paths, label="workspace")
    return paths


def declared_development_problem_package_paths(
    problem_spec: Any,
) -> tuple[str, ...]:
    """Return exact public files mounted below ``scion.problems.<id>``."""

    spec_v1 = getattr(problem_spec, "spec_v1", problem_spec)
    paths = tuple(
        _canonical_manifest_path(path)
        for path in getattr(spec_v1, "development_problem_package_paths", ()) or ()
    )
    _validate_declared_runtime_paths(spec_v1, paths, label="problem package")
    return paths


def validate_development_closure_boundary(
    *,
    problem_spec: Any,
    suites: Sequence[DevelopmentSuiteManifest],
    workspace_paths: Sequence[str],
    problem_package_paths: Sequence[str],
    split_manifest: Any | None,
    champion_root: str | None,
) -> None:
    """Reject any public development file that aliases a Protocol case.

    Development support is ordinary host-authored material.  It cannot reuse
    screening, validation, frozen, or canary cases, and there is no fallback
    from the explicit development manifest to formal Verification paths.
    """

    spec_v1 = getattr(problem_spec, "spec_v1", problem_spec)
    problem_root = Path(str(getattr(spec_v1, "root_dir", ""))).expanduser().resolve()
    development_paths: set[Path] = set()
    for suite in suites:
        root = Path(suite.source_root).expanduser().resolve()
        development_paths.update(
            (root / path).resolve() for path in suite.declared_paths
        )
    development_paths.update(
        (problem_root / _canonical_manifest_path(path)).resolve()
        for path in (*workspace_paths, *problem_package_paths)
    )

    roots = [problem_root]
    if champion_root:
        roots.append(Path(champion_root).expanduser().resolve())
    roots.extend(
        Path(path).expanduser().resolve()
        for path in getattr(split_manifest, "safe_data_roots", ()) or ()
    )
    raw_cases: list[Any] = []
    for field_name in ("screening", "validation", "frozen", "canary"):
        raw_cases.extend(getattr(split_manifest, field_name, ()) or ())
    raw_canary = getattr(spec_v1, "canary_case_path", "")
    if raw_canary:
        raw_cases.append(raw_canary)

    forbidden: set[Path] = set()
    for raw_case in raw_cases:
        case = Path(str(raw_case)).expanduser()
        if case.is_absolute():
            forbidden.add(case.resolve())
        else:
            forbidden.update((root / case).resolve() for root in roots)
    overlap = sorted(str(path) for path in development_paths & forbidden)
    if overlap:
        raise ValueError(
            "development closure overlaps Protocol/canary case paths: "
            + ", ".join(overlap)
        )


def _validate_declared_runtime_paths(
    spec_v1: Any,
    paths: tuple[str, ...],
    *,
    label: str,
) -> None:
    if len(paths) != len(set(paths)):
        raise ValueError(f"development {label} paths must be unique")
    root = Path(str(getattr(spec_v1, "root_dir", ""))).expanduser().resolve()
    if paths and not root.is_dir():
        raise ValueError(f"development {label} root is not a directory")
    for path in paths:
        _authoritative_file(root, path)


def copy_declared_development_files(
    *,
    source_root: str | Path,
    paths: Sequence[str],
    destination_root: str | Path,
    max_files: int,
    max_bytes: int,
    forbidden_paths: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    """Copy only an exact, symlink-free public file closure."""

    root = Path(source_root).resolve()
    destination = Path(destination_root).resolve()
    if not root.is_dir() or not destination.is_dir():
        raise ValueError("development closure roots must be directories")
    normalized = tuple(_canonical_manifest_path(path) for path in paths)
    if len(normalized) != len(set(normalized)):
        raise ValueError("development closure contains duplicate files")
    if len(normalized) > max_files:
        raise ValueError("development suite closure exceeds file cap")
    total = 0
    buffered: list[tuple[str, bytes]] = []
    for relative_path in normalized:
        if relative_path in forbidden_paths:
            raise ValueError("development closure overlaps a candidate patch target")
        source = _authoritative_file(root, relative_path)
        data = _bounded_regular_file_read(source, max_bytes - total)
        total += len(data)
        buffered.append((relative_path, data))
    for relative_path, data in buffered:
        target = destination / relative_path
        _require_destination_inside_scratch(destination, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return len(buffered), total


def write_development_source_corpus(
    corpus: Mapping[str, str],
    destination_root: str | Path,
    *,
    max_files: int,
    max_bytes: int,
) -> tuple[int, int]:
    """Materialize only the already-frozen provider-visible source map."""

    destination = Path(destination_root).resolve()
    if not destination.is_dir():
        raise ValueError("development source destination is not a directory")
    if len(corpus) > max_files:
        raise ValueError("development source corpus exceeds file cap")
    normalized: list[tuple[str, bytes]] = []
    total = 0
    for raw_path, content in corpus.items():
        path = _canonical_manifest_path(raw_path)
        if not isinstance(content, str):
            raise ValueError("development source corpus content must be text")
        data = content.encode("utf-8")
        total += len(data)
        if total > max_bytes:
            raise ValueError("development source corpus exceeds byte cap")
        normalized.append((path, data))
    if len({path for path, _data in normalized}) != len(normalized):
        raise ValueError("development source corpus contains duplicate files")
    for path, data in normalized:
        target = destination / path
        _require_destination_inside_scratch(destination, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return len(normalized), total


def copy_development_suite_closure(
    suites: Sequence[DevelopmentSuiteManifest],
    candidate_workspace: str,
    *,
    max_files: int,
    max_bytes: int,
    forbidden_paths: frozenset[str] = frozenset(),
) -> tuple[DevelopmentSuiteManifest, ...]:
    """Copy the exact manifest bytes into scratch, preserving relative layout."""

    workspace = Path(candidate_workspace).resolve()
    if not workspace.is_dir():
        raise ValueError("development candidate workspace is not a directory")
    unique_sources: dict[tuple[str, str], tuple[str, bytes]] = {}
    total_bytes = 0
    normalized_suites: list[DevelopmentSuiteManifest] = []
    for suite in suites:
        root = Path(suite.source_root).resolve()
        paths = tuple(_canonical_manifest_path(path) for path in suite.declared_paths)
        for relative_path in paths:
            if relative_path in forbidden_paths:
                raise ValueError(
                    "development suite closure overlaps a candidate patch target"
                )
            source = _authoritative_file(root, relative_path)
            key = (str(root), relative_path)
            if key not in unique_sources:
                remaining = max_bytes - total_bytes
                data = _bounded_regular_file_read(source, remaining)
                total_bytes += len(data)
                unique_sources[key] = (relative_path, data)
        normalized_suites.append(
            DevelopmentSuiteManifest(
                check_name=suite.check_name,
                source_root=str(root),
                test_path=suite.test_path,
                support_paths=suite.support_paths,
            )
        )
    if len(unique_sources) > max_files:
        raise ValueError("development suite closure exceeds file cap")
    if total_bytes > max_bytes:
        raise ValueError("development suite closure exceeds byte cap")
    for relative_path, data in unique_sources.values():
        destination = workspace / relative_path
        _require_destination_inside_scratch(workspace, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return tuple(normalized_suites)


def run_development_checks(
    *,
    patch: PatchProposal,
    candidate_workspace: str,
    problem_spec: Any,
    selected_surface: str | None,
    operator_execute_signature: str | None,
    suites: Sequence[DevelopmentSuiteManifest],
    per_suite_timeout_sec: int | float,
    total_timeout_sec: int | float,
    sandbox: "BubblewrapDevelopmentSandbox",
    problem_runtime_root: str,
) -> DevelopmentCheckRun:
    """Run D1-D4 fail-fast; never call formal Contract/Verification gates."""

    for value in (per_suite_timeout_sec, total_timeout_sec):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or value <= 0
        ):
            raise ValueError("development timeouts must be finite and positive")
    checks: list[DevelopmentCheckObservation] = []
    static = (
        ("D1_syntax", check_syntax(patch).passed),
        ("D1b_undefined_names", check_undefined_names(patch).passed),
        (
            "D2_interface",
            check_interface(
                patch,
                candidate_workspace,
                problem_spec=problem_spec,
                selected_surface=selected_surface,
                operator_execute_signature=operator_execute_signature,
            ).passed,
        ),
    )
    for name, passed in static:
        observation = DevelopmentCheckObservation(
            name=name,
            outcome="passed" if passed else "failed",
        )
        checks.append(observation)
        if not passed:
            return DevelopmentCheckRun(outcome="failed", checks=tuple(checks))

    if not _development_safety_preflight(
        patch=patch,
        problem_spec=problem_spec,
        candidate_workspace=candidate_workspace,
    ):
        return DevelopmentCheckRun(
            outcome="preflight_rejected",
            checks=tuple(checks),
        )
    if not sandbox.available:
        return DevelopmentCheckRun(outcome="unavailable", checks=tuple(checks))

    started = time.monotonic()
    for suite in _validated_suite_order(suites):
        remaining = total_timeout_sec - (time.monotonic() - started)
        if remaining <= 0:
            outcome: DevelopmentOutcome = "timeout"
        else:
            outcome = sandbox.run_pytest(
                workspace=candidate_workspace,
                test_path=suite.test_path,
                timeout_sec=min(float(per_suite_timeout_sec), remaining),
                problem_runtime_root=problem_runtime_root,
            )
        observation = DevelopmentCheckObservation(
            name=suite.check_name,
            outcome=outcome,
        )
        checks.append(observation)
        if not observation.passed:
            return DevelopmentCheckRun(outcome=outcome, checks=tuple(checks))
    return DevelopmentCheckRun(outcome="passed", checks=tuple(checks))


class BubblewrapDevelopmentSandbox:
    """Fail-closed Linux sandbox for tainted development test execution."""

    def __init__(
        self,
        *,
        bwrap_path: Path = _BWRAP,
        python_executable: Path | None = None,
        python_prefix: Path | None = None,
        framework_root: Path | None = None,
        popen: Callable[..., subprocess.Popen[Any]] = subprocess.Popen,
    ) -> None:
        self._bwrap = Path(bwrap_path)
        self._python_executable = Path(python_executable or sys.executable).resolve()
        self._python_prefix = Path(python_prefix or sys.prefix).resolve()
        self._framework_root = Path(
            framework_root or Path(__file__).resolve().parents[1]
        ).resolve()
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        self._python_site = self._python_prefix / "lib" / python_version / "site-packages"
        self._popen = popen

    @property
    def available(self) -> bool:
        try:
            mode = self._bwrap.stat().st_mode
            self._python_executable.relative_to(self._python_prefix)
        except (OSError, ValueError):
            return False
        return (
            stat.S_ISREG(mode)
            and os.access(self._bwrap, os.X_OK)
            and _regular_nonsymlink_file(_PRLIMIT)
            and os.access(_PRLIMIT, os.X_OK)
            and self._python_prefix.is_dir()
            and self._framework_root.is_dir()
            and _regular_nonsymlink_file(self._python_site / "pytest" / "__init__.py")
        )

    def run_pytest(
        self,
        *,
        workspace: str,
        test_path: str,
        timeout_sec: float,
        problem_runtime_root: str,
    ) -> DevelopmentOutcome:
        if not self.available:
            return "unavailable"
        workspace_path = Path(workspace).resolve()
        relative_test = _canonical_manifest_path(test_path)
        host_test = workspace_path / relative_test
        try:
            _require_destination_inside_scratch(workspace_path, host_test)
        except ValueError:
            return "preflight_rejected"
        if not host_test.is_file() or host_test.is_symlink():
            return "preflight_rejected"
        runtime_path = Path(problem_runtime_root).resolve()
        if not runtime_path.is_dir() or not runtime_path.is_relative_to(workspace_path):
            return "preflight_rejected"
        argv = self._argv(workspace_path, relative_test, runtime_path)
        try:
            proc = self._popen(
                argv,
                cwd="/",
                env={},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                start_new_session=True,
                preexec_fn=_resource_limiter(timeout_sec),
            )
        except Exception:
            return "launch_error"
        try:
            return_code = proc.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)
            return "timeout"
        except BaseException:
            _kill_process_group(proc)
            raise
        return "passed" if return_code == 0 else "failed"

    def _argv(
        self,
        workspace: Path,
        relative_test: str,
        problem_runtime_root: Path,
    ) -> list[str]:
        executable_rel = self._python_executable.relative_to(self._python_prefix)
        sandbox_python = str(Path(_SANDBOX_PYTHON_ROOT) / executable_rel)
        argv = [
            str(self._bwrap),
            "--die-with-parent",
            "--new-session",
            "--unshare-all",
            "--clearenv",
            "--ro-bind",
            "/usr",
            "/usr",
        ]
        for system_root in ("/lib", "/lib64"):
            if Path(system_root).exists():
                argv.extend(("--ro-bind", system_root, system_root))
        sandbox_site = str(
            Path(_SANDBOX_PYTHON_ROOT)
            / self._python_site.relative_to(self._python_prefix)
        )
        python_path = ":".join(
            (_SANDBOX_WORKSPACE, _SANDBOX_FRAMEWORK_ROOT, sandbox_site)
        )
        argv.extend(
            (
                "--ro-bind",
                str(self._python_prefix),
                _SANDBOX_PYTHON_ROOT,
                "--ro-bind",
                str(self._framework_root),
                f"{_SANDBOX_FRAMEWORK_ROOT}/scion",
                "--tmpfs",
                f"{_SANDBOX_FRAMEWORK_ROOT}/scion/tests",
                "--ro-bind",
                str(problem_runtime_root),
                f"{_SANDBOX_FRAMEWORK_ROOT}/scion/problems",
                "--ro-bind",
                str(workspace),
                _SANDBOX_WORKSPACE,
                "--size",
                str(64 * 1024 * 1024),
                "--tmpfs",
                "/tmp",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--chdir",
                _SANDBOX_WORKSPACE,
                "--setenv",
                "PYTHONPATH",
                python_path,
                "--setenv",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "1",
                "--setenv",
                "PYTHONNOUSERSITE",
                "1",
                "--setenv",
                "PYTHONDONTWRITEBYTECODE",
                "1",
                "--setenv",
                "PYTHONHASHSEED",
                "0",
                str(_PRLIMIT),
                "--nproc=64",
                "--",
                sandbox_python,
                "-S",
                "-B",
                "-m",
                "pytest",
                f"{_SANDBOX_WORKSPACE}/{relative_test}",
                "-q",
                "--tb=no",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "--rootdir",
                _SANDBOX_WORKSPACE,
                "--confcutdir",
                _SANDBOX_WORKSPACE,
            )
        )
        return argv


def _development_safety_preflight(
    *,
    patch: PatchProposal,
    problem_spec: Any,
    candidate_workspace: str,
) -> bool:
    patterns = editable_patterns(problem_spec)
    search_space = getattr(problem_spec, "search_space", None)
    frozen_patterns = tuple(getattr(search_space, "frozen", ()) or ())
    graph = PatchSetGraph.from_patch(patch)
    workspace = Path(candidate_workspace).resolve()

    def is_editable(path: str) -> bool:
        return any(segment_glob_match(path, pattern) for pattern in patterns)

    def read_source(path: str) -> str | None:
        try:
            relative = normalize_relative_patch_path(path)
            candidate = workspace / relative
            _require_destination_inside_scratch(workspace, candidate)
            if not candidate.is_file() or candidate.is_symlink():
                return None
            return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            return None

    for change in patch_file_changes(patch):
        single = PatchProposal(
            file_path=change.file_path,
            action=change.action,
            code_content=change.code_content,
            test_hint=change.test_hint,
        )
        if not is_editable(change.file_path):
            return False
        if any(
            segment_glob_match(change.file_path, pattern)
            for pattern in frozen_patterns
        ):
            return False
        if not check_sensitive_api(single).passed:
            return False
        if not check_import_whitelist(
            single,
            problem_spec=problem_spec,
            patch_graph=graph,
            is_editable_solver_file=is_editable,
            relative_import_file_exists=lambda path: read_source(path) is not None,
            relative_import_source=read_source,
        ).passed:
            return False
    return True


def _validated_suite_order(
    suites: Sequence[DevelopmentSuiteManifest],
) -> tuple[DevelopmentSuiteManifest, ...]:
    normalized = tuple(suites)
    names = tuple(suite.check_name for suite in normalized)
    if len(names) != len(set(names)) or names != tuple(
        name for name in _SUITE_NAMES if name in names
    ):
        raise ValueError("development suites must be unique and in D3/D4 order")
    return normalized


def _canonical_manifest_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("development manifest path must be a string")
    path = normalize_relative_patch_path(value)
    if path != value or any(character in path for character in "*?["):
        raise ValueError("development manifest path must be one exact canonical file")
    return path


def _authoritative_file(root: Path, relative_path: str) -> Path:
    candidate = root / _canonical_manifest_path(relative_path)
    current = root
    for part in Path(relative_path).parts:
        current = current / part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise ValueError("development manifest symlinks are not allowed")
        except OSError as exc:
            raise ValueError("development manifest file is not available") from exc
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("development manifest file is not a regular root-owned file")
    return resolved


def _bounded_regular_file_read(path: Path, maximum: int) -> bytes:
    if maximum <= 0:
        raise ValueError("development suite closure exceeds byte cap")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("development manifest source is not a regular file")
        chunks: list[bytes] = []
        total = 0
        while total <= maximum:
            chunk = os.read(descriptor, min(65_536, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        data = b"".join(chunks)
        if len(data) > maximum:
            raise ValueError("development suite closure exceeds byte cap")
        return data
    finally:
        os.close(descriptor)


def _require_destination_inside_scratch(workspace: Path, destination: Path) -> None:
    resolved_parent = destination.parent.resolve()
    if not resolved_parent.is_relative_to(workspace):
        raise ValueError("development destination escapes scratch workspace")
    current = workspace
    for part in destination.relative_to(workspace).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError("development destination contains a symlink")


def _resource_limiter(timeout_sec: float) -> Callable[[], None]:
    cpu_seconds = max(1, int(math.ceil(timeout_sec)))

    def limit() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        if hasattr(resource, "RLIMIT_AS"):
            resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3,) * 2)

    return limit


def _regular_nonsymlink_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink()
    except OSError:
        return False


def _kill_process_group(proc: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        pass


__all__ = [
    "BubblewrapDevelopmentSandbox",
    "DevelopmentCheckName",
    "DevelopmentCheckObservation",
    "DevelopmentCheckRun",
    "DevelopmentOutcome",
    "DevelopmentSuiteManifest",
    "copy_development_suite_closure",
    "copy_declared_development_files",
    "declared_development_problem_package_paths",
    "declared_development_workspace_paths",
    "declared_development_suites",
    "run_development_checks",
    "validate_development_closure_boundary",
    "write_development_source_corpus",
]
