"""Host-owned public-closure evaluator for bounded code research."""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from scion.core.code_research_limits import (
    MAX_CODE_RESEARCH_PROBE_SOURCE_CHARS,
    MAX_CODE_RESEARCH_PROBE_TIMEOUT_SEC,
    CodeResearchLimits,
)
from scion.core.models import PatchProposal
from scion.core.path_match import segment_glob_match
from scion.core.research_surface_index import editable_patterns
from scion.verification.development import (
    BubblewrapDevelopmentSandbox,
    DevelopmentCheckRun,
    DevelopmentSuiteManifest,
    copy_declared_development_files,
    copy_development_suite_closure,
    development_probe_path_conflicts,
    development_safety_preflight,
    run_development_checks,
    write_development_probe_source,
    write_development_source_corpus,
)


@dataclass(frozen=True)
class _PreparedScratch:
    path: str
    problems_root: Path
    remaining_files: int
    remaining_bytes: int


@dataclass(frozen=True)
class CodeDevelopmentEvaluator:
    """Evaluate one frozen draft without branch, formal, or evidence mutation."""

    materializer: Any
    problem_spec: Any
    suites: tuple[DevelopmentSuiteManifest, ...]
    workspace_paths: tuple[str, ...]
    problem_package_paths: tuple[str, ...]
    limits: CodeResearchLimits
    operator_execute_signature: str | None = None
    sandbox: BubblewrapDevelopmentSandbox = field(
        default_factory=BubblewrapDevelopmentSandbox
    )

    def evaluate(
        self,
        *,
        source_corpus: Mapping[str, str],
        patch: PatchProposal,
        selected_surface: str | None,
        total_timeout_sec: float,
        falsifier_source: str | None = None,
    ) -> DevelopmentCheckRun:
        started = time.monotonic()
        if not self.suites or not source_corpus:
            return DevelopmentCheckRun(outcome="unavailable")
        candidate: str | None = None
        try:
            suite_paths = frozenset(
                path for suite in self.suites for path in suite.declared_paths
            )
            if development_probe_path_conflicts(
                (
                    *source_corpus,
                    *suite_paths,
                    *self.workspace_paths,
                    *self.problem_package_paths,
                    *(change.file_path for change in patch.iter_file_changes()),
                )
            ):
                return DevelopmentCheckRun(outcome="preflight_rejected")
            prepared = self._prepare_scratch(
                source_corpus=source_corpus,
                patch=patch,
                max_files=self.limits.max_test_files,
                max_bytes=self.limits.max_test_copy_bytes,
                additional_forbidden=suite_paths,
            )
            candidate = prepared.path
            remaining_files = prepared.remaining_files
            remaining_bytes = prepared.remaining_bytes
            if not development_safety_preflight(
                patch=patch,
                problem_spec=self.problem_spec,
                candidate_workspace=candidate,
            ):
                return DevelopmentCheckRun(outcome="preflight_rejected")
            falsifier_outcome = None
            if falsifier_source is not None:
                probe_bytes = len(falsifier_source.encode("utf-8"))
                if remaining_files < 1 or probe_bytes > remaining_bytes:
                    falsifier_outcome = "unavailable"
                else:
                    probe_path = write_development_probe_source(
                        falsifier_source,
                        candidate,
                        max_chars=MAX_CODE_RESEARCH_PROBE_SOURCE_CHARS,
                        max_bytes=min(self.limits.max_action_bytes, remaining_bytes),
                    )
                    remaining_files -= 1
                    remaining_bytes -= probe_bytes
                    probe_timeout = min(
                        float(MAX_CODE_RESEARCH_PROBE_TIMEOUT_SEC),
                        total_timeout_sec - (time.monotonic() - started),
                    )
                    if probe_timeout <= 0:
                        return DevelopmentCheckRun(outcome="timeout")
                    falsifier_outcome = self.sandbox.run_probe(
                        workspace=candidate,
                        probe_path=probe_path,
                        timeout_sec=probe_timeout,
                        problem_runtime_root=str(prepared.problems_root),
                    )
                    probe_file = Path(candidate) / probe_path
                    probe_file.unlink()
                    probe_file.parent.rmdir()

            copied_suites = copy_development_suite_closure(
                self.suites,
                candidate,
                max_files=remaining_files,
                max_bytes=remaining_bytes,
                forbidden_paths=frozenset(
                    {
                        *source_corpus,
                        *(change.file_path for change in patch.iter_file_changes()),
                    }
                ),
            )
            remaining_timeout = total_timeout_sec - (time.monotonic() - started)
            if remaining_timeout <= 0:
                return DevelopmentCheckRun(
                    outcome="timeout",
                    falsifier_outcome=falsifier_outcome,
                )
            run = run_development_checks(
                patch=patch,
                candidate_workspace=candidate,
                problem_spec=self.problem_spec,
                selected_surface=selected_surface,
                operator_execute_signature=self.operator_execute_signature,
                suites=copied_suites,
                per_suite_timeout_sec=self.limits.max_test_suite_timeout_sec,
                total_timeout_sec=min(
                    float(self.limits.max_test_total_timeout_sec),
                    remaining_timeout,
                ),
                sandbox=self.sandbox,
                problem_runtime_root=str(prepared.problems_root),
            )
            return replace(run, falsifier_outcome=falsifier_outcome)
        except (OSError, TypeError, ValueError):
            return DevelopmentCheckRun(outcome="preflight_rejected")
        finally:
            if candidate is not None:
                self.materializer.cleanup_candidate_workspace(candidate)

    def _prepare_scratch(
        self,
        *,
        source_corpus: Mapping[str, str],
        patch: PatchProposal,
        max_files: int,
        max_bytes: int,
        additional_forbidden: frozenset[str] = frozenset(),
    ) -> _PreparedScratch:
        candidate = self.materializer.create_empty_candidate_workspace()
        try:
            count, copied_bytes = write_development_source_corpus(
                source_corpus,
                candidate,
                max_files=max_files,
                max_bytes=max_bytes,
            )
            remaining_files = max_files - count
            remaining_bytes = max_bytes - copied_bytes
            self.materializer.apply_ephemeral_patch(candidate, patch)

            spec_v1 = getattr(self.problem_spec, "spec_v1", self.problem_spec)
            patch_paths = frozenset(
                change.file_path for change in patch.iter_file_changes()
            )
            forbidden = frozenset(source_corpus) | patch_paths | additional_forbidden
            if frozenset(self.workspace_paths) & forbidden:
                raise ValueError("development workspace closure overlaps scratch")
            if self.workspace_paths:
                count, copied_bytes = copy_declared_development_files(
                    source_root=str(getattr(spec_v1, "root_dir", "")),
                    paths=self.workspace_paths,
                    destination_root=candidate,
                    max_files=remaining_files,
                    max_bytes=remaining_bytes,
                    forbidden_paths=forbidden,
                )
                remaining_files -= count
                remaining_bytes -= copied_bytes

            problem_id = str(
                getattr(spec_v1, "id", None) or getattr(spec_v1, "name", "")
            )
            if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", problem_id) is None:
                raise ValueError("development problem id is invalid")
            problems_root = Path(candidate) / ".scion-development-problems"
            runtime_root = problems_root / problem_id
            runtime_root.mkdir(parents=True, exist_ok=False)
            (problems_root / "__init__.py").write_text("", encoding="utf-8")
            if any(
                segment_glob_match(path, pattern)
                for path in self.problem_package_paths
                for pattern in editable_patterns(self.problem_spec)
            ):
                raise ValueError("development runtime closure overlaps editable source")
            if self.problem_package_paths:
                count, copied_bytes = copy_declared_development_files(
                    source_root=str(getattr(spec_v1, "root_dir", "")),
                    paths=self.problem_package_paths,
                    destination_root=runtime_root,
                    max_files=remaining_files,
                    max_bytes=remaining_bytes,
                )
                remaining_files -= count
                remaining_bytes -= copied_bytes
            return _PreparedScratch(
                path=candidate,
                problems_root=problems_root,
                remaining_files=remaining_files,
                remaining_bytes=remaining_bytes,
            )
        except BaseException:
            self.materializer.cleanup_candidate_workspace(candidate)
            raise


__all__ = ["CodeDevelopmentEvaluator"]
