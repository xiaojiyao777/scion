"""Host-owned public-closure evaluator for bounded code research."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import PatchProposal
from scion.core.path_match import segment_glob_match
from scion.core.research_surface_index import editable_patterns
from scion.verification.development import (
    BubblewrapDevelopmentSandbox,
    DevelopmentCheckRun,
    DevelopmentSuiteManifest,
    copy_declared_development_files,
    copy_development_suite_closure,
    run_development_checks,
    write_development_source_corpus,
)


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
    ) -> DevelopmentCheckRun:
        if not self.suites or not source_corpus:
            return DevelopmentCheckRun(outcome="unavailable")
        candidate: str | None = None
        try:
            candidate = self.materializer.create_empty_candidate_workspace()
            remaining_files = self.limits.max_test_files
            remaining_bytes = self.limits.max_test_copy_bytes
            count, copied_bytes = write_development_source_corpus(
                source_corpus,
                candidate,
                max_files=remaining_files,
                max_bytes=remaining_bytes,
            )
            remaining_files -= count
            remaining_bytes -= copied_bytes
            self.materializer.apply_patch(candidate, patch)

            spec_v1 = getattr(self.problem_spec, "spec_v1", self.problem_spec)
            patch_paths = frozenset(
                change.file_path for change in patch.iter_file_changes()
            )
            source_paths = frozenset(source_corpus)
            suite_paths = frozenset(
                path for suite in self.suites for path in suite.declared_paths
            )
            workspace_paths = frozenset(self.workspace_paths)
            if workspace_paths & (source_paths | patch_paths | suite_paths):
                return DevelopmentCheckRun(outcome="preflight_rejected")
            if self.workspace_paths:
                count, copied_bytes = copy_declared_development_files(
                    source_root=str(getattr(spec_v1, "root_dir", "")),
                    paths=self.workspace_paths,
                    destination_root=candidate,
                    max_files=remaining_files,
                    max_bytes=remaining_bytes,
                    forbidden_paths=source_paths | patch_paths | suite_paths,
                )
                remaining_files -= count
                remaining_bytes -= copied_bytes

            problem_id = str(
                getattr(spec_v1, "id", None)
                or getattr(spec_v1, "name", "")
            )
            if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", problem_id) is None:
                return DevelopmentCheckRun(outcome="preflight_rejected")
            problems_root = Path(candidate) / ".scion-development-problems"
            runtime_root = problems_root / problem_id
            runtime_root.mkdir(parents=True, exist_ok=False)
            (problems_root / "__init__.py").write_text("", encoding="utf-8")
            if self.problem_package_paths:
                if any(
                    segment_glob_match(path, pattern)
                    for path in self.problem_package_paths
                    for pattern in editable_patterns(self.problem_spec)
                ):
                    return DevelopmentCheckRun(outcome="preflight_rejected")
                count, copied_bytes = copy_declared_development_files(
                    source_root=str(getattr(spec_v1, "root_dir", "")),
                    paths=self.problem_package_paths,
                    destination_root=runtime_root,
                    max_files=remaining_files,
                    max_bytes=remaining_bytes,
                )
                remaining_files -= count
                remaining_bytes -= copied_bytes

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
            return run_development_checks(
                patch=patch,
                candidate_workspace=candidate,
                problem_spec=self.problem_spec,
                selected_surface=selected_surface,
                operator_execute_signature=self.operator_execute_signature,
                suites=copied_suites,
                per_suite_timeout_sec=self.limits.max_test_suite_timeout_sec,
                total_timeout_sec=min(
                    float(self.limits.max_test_total_timeout_sec),
                    total_timeout_sec,
                ),
                sandbox=self.sandbox,
                problem_runtime_root=str(problems_root),
            )
        except (OSError, TypeError, ValueError):
            return DevelopmentCheckRun(outcome="preflight_rejected")
        finally:
            if candidate is not None:
                self.materializer.cleanup_candidate_workspace(candidate)


__all__ = ["CodeDevelopmentEvaluator"]
