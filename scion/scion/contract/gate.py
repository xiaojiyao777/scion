"""ContractGate: static validation of HypothesisProposal and PatchProposal."""
from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any, Callable, List, Mapping

from scion.config.problem import ProblemSpec
from scion.core.operator_interface import parse_execute_signature
from scion.core.paths import normalize_relative_patch_path
from scion.core.models import (
    CheckResult,
    ContractResult,
    HypothesisProposal,
    PatchProposal,
    patch_file_changes,
)
from scion.contract.checks.randomness import check_non_rng_random
from scion.contract.checks.security import (
    check_import_whitelist,
    check_sensitive_api,
)
from scion.contract.checks.targeting import (
    check_file_whitelist,
    check_frozen_files,
    check_patch_action_target,
)
from scion.contract.hypothesis_checks import (
    check_action_target,
    check_change_locus,
    check_hypothesis_schema,
)
from scion.contract.patch_graph import PatchSetGraph
from scion.contract.result_payload import (
    build_result as _build_result,
    check_result as _cr,
    prefix_checks as _prefix_checks,
)
from scion.contract.surface_access import SurfaceAccess
from scion.contract.surface_interface import check_surface_interface

def _normalize_source_overrides(
    source_overrides: Mapping[str, str] | None,
) -> dict[str, str]:
    if not source_overrides:
        return {}
    normalized: dict[str, str] = {}
    for raw_path, content in source_overrides.items():
        if not isinstance(content, str):
            continue
        try:
            file_rel = normalize_relative_patch_path(str(raw_path))
        except ValueError:
            continue
        normalized[file_rel] = content
    return normalized


def _syntax_source_detail(source: str) -> str:
    lines = str(source or "").splitlines()
    if not lines:
        return "<empty>"
    return " | ".join(
        f"{index}: {line!r}"
        for index, line in enumerate(lines, start=1)
    )


class ContractGate:
    """Static gate that validates proposals before any code is executed."""

    def __init__(
        self,
        problem_spec: ProblemSpec,
        *,
        operator_execute_signature: str | None = None,
        champion_snapshot_path: str | None = None,
        champion_snapshot_provider: Callable[[], str | None] | None = None,
        source_overrides: Mapping[str, str] | None = None,
        adapter: Any = None,
    ) -> None:
        self._spec = problem_spec
        self._adapter = adapter
        self._operator_signature = parse_execute_signature(operator_execute_signature)
        self._champion_snapshot_path = champion_snapshot_path
        self._champion_snapshot_provider = champion_snapshot_provider
        self._source_overrides = _normalize_source_overrides(source_overrides)
        self._surface_access = SurfaceAccess(problem_spec)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_hypothesis(
        self,
        hypothesis: HypothesisProposal,
        *,
        base_snapshot_path: str | None = None,
        base_file_overrides: Mapping[str, str] | None = None,
    ) -> ContractResult:
        """Validate the provider hypothesis against host-owned boundaries."""
        checks: List[CheckResult] = []
        source_root = (
            str(base_snapshot_path or "").strip()
            or self._current_champion_snapshot_path()
        )
        normalized_overrides = _normalize_source_overrides(base_file_overrides)
        file_exists = None
        if source_root or normalized_overrides or self._source_overrides:
            source_reader = self._file_content_provider(
                base_snapshot_path,
                source_overrides=normalized_overrides,
            )
            file_exists = lambda file_rel: source_reader(file_rel) is not None
        checks.append(self._c1_schema(hypothesis))
        checks.append(self._c2_change_locus(hypothesis))
        checks.append(self._c3_action_target(hypothesis, file_exists=file_exists))
        return _build_result(checks)

    def _frozen_c1_schema(self, h: HypothesisProposal) -> CheckResult:
        """Compatibility alias for the ordinary structural C1 check."""

        return self._c1_schema(h)

    def _frozen_c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        """Compatibility alias for the ordinary structural C2 check."""

        return self._c2_change_locus(h)

    def _frozen_c3_action_target(self, h: HypothesisProposal) -> CheckResult:
        """Compatibility alias for the ordinary structural C3 check."""

        return self._c3_action_target(h)

    def validate_patch(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None = None,
        *,
        approved_hypothesis: HypothesisProposal | None = None,
        selected_surface: str | None = None,
        base_snapshot_path: str | None = None,
        base_file_overrides: Mapping[str, str] | None = None,
    ) -> ContractResult:
        """Validate typed patch ownership, syntax, interface, and safety."""
        checks: List[CheckResult] = []
        base_file_content = self._file_content_provider(
            base_snapshot_path,
            source_overrides=base_file_overrides,
        )
        contract_hypothesis = (
            approved_hypothesis if approved_hypothesis is not None else hypothesis
        )
        selected_surface_name = (
            self._selected_surface_name(contract_hypothesis) or selected_surface
        )
        patch_graph = PatchSetGraph.from_patch(patch)
        file_changes = patch_file_changes(patch)
        for index, change in enumerate(file_changes):
            is_primary = index == 0
            change_patch = PatchProposal(
                file_path=change.file_path,
                action=change.action,
                code_content=change.code_content,
                test_hint=change.test_hint,
            )
            change_checks = self._validate_patch_file_change(
                change_patch,
                contract_hypothesis if is_primary else None,
                selected_surface=selected_surface_name,
                enforce_hypothesis_target=is_primary,
                patch_graph=patch_graph,
                base_file_content=base_file_content,
            )
            if is_primary:
                checks.extend(change_checks)
            else:
                checks.extend(
                    _prefix_checks(change_checks, f"additional_changes[{index - 1}]")
                )

        return _build_result(checks)

    def _validate_patch_file_change(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
        *,
        selected_surface: str | None,
        enforce_hypothesis_target: bool,
        patch_graph: PatchSetGraph | None,
        base_file_content: Callable[[str], str | None] | None = None,
    ) -> List[CheckResult]:
        checks: List[CheckResult] = []
        checks.append(self._c4_file_whitelist(patch))
        checks.append(self._c5_frozen_files(patch))
        checks.append(
            self._c4b_patch_action_target(
                patch,
                hypothesis,
                selected_surface=selected_surface,
                enforce_hypothesis_target=enforce_hypothesis_target,
            )
        )
        if not all(check.passed for check in checks[-3:]):
            return checks

        checks.append(self._c6_ast_syntax(patch))
        if not checks[-1].passed:
            return checks

        checks.append(
            self._c7_interface_signature(
                patch,
                selected_surface=selected_surface,
                enforce_public_interface=enforce_hypothesis_target,
            )
        )
        checks.append(
            self._c8_import_whitelist(
                patch,
                patch_graph=patch_graph,
                base_file_content=base_file_content,
            )
        )
        checks.append(
            self._c9_sensitive_api(
                patch,
                selected_surface=selected_surface,
            )
        )
        checks.append(self._c9b_non_rng_random(patch))
        return checks

    # ------------------------------------------------------------------
    # C1: JSON Schema (pydantic already validates, check required fields)
    # ------------------------------------------------------------------

    def _c1_schema(self, h: HypothesisProposal) -> CheckResult:
        return check_hypothesis_schema(h, self._spec)

    # ------------------------------------------------------------------
    # C2: change_locus must be a known research locus
    # ------------------------------------------------------------------

    def _c2_change_locus(self, h: HypothesisProposal) -> CheckResult:
        return check_change_locus(
            h,
            problem_spec=self._spec,
            surface_access=self._surface_access,
        )

    # ------------------------------------------------------------------
    # C3: action-target consistency
    # ------------------------------------------------------------------

    def _c3_action_target(
        self,
        h: HypothesisProposal,
        *,
        file_exists: Callable[[str], bool] | None = None,
    ) -> CheckResult:
        return check_action_target(
            h,
            surface_access=self._surface_access,
            file_exists=file_exists,
        )

    # ------------------------------------------------------------------
    # C4: file whitelist — file_path must match an editable pattern
    # ------------------------------------------------------------------

    def _c4_file_whitelist(self, patch: PatchProposal) -> CheckResult:
        return check_file_whitelist(patch, self._spec)

    # ------------------------------------------------------------------
    # C5: frozen files — file_path must NOT match any frozen pattern
    # ------------------------------------------------------------------

    def _c5_frozen_files(self, patch: PatchProposal) -> CheckResult:
        return check_frozen_files(patch, self._spec)

    # ------------------------------------------------------------------
    # C4b: patch action/target must match approved hypothesis and surface.
    # ------------------------------------------------------------------

    def _c4b_patch_action_target(
        self,
        patch: PatchProposal,
        hypothesis: HypothesisProposal | None,
        *,
        selected_surface: str | None = None,
        enforce_hypothesis_target: bool = True,
    ) -> CheckResult:
        return check_patch_action_target(
            patch,
            hypothesis,
            surface_access=self._surface_access,
            selected_surface=selected_surface,
            enforce_hypothesis_target=enforce_hypothesis_target,
        )

    # ------------------------------------------------------------------
    # C6: AST syntax check
    # ------------------------------------------------------------------

    def _c6_ast_syntax(self, patch: PatchProposal) -> CheckResult:
        t0 = time.monotonic_ns()
        if patch.action == "delete":
            return _cr("C6_ast_syntax", True, "light", "delete action — no syntax check", t0)
        try:
            filename = patch.file_path or "<patch>"
            tree = ast.parse(patch.code_content, filename=filename)
            compile(tree, filename, "exec")
            return _cr("C6_ast_syntax", True, "light", "syntax ok", t0)
        except SyntaxError as e:
            detail = (
                f"SyntaxError: {e}; "
                f"source_detail={_syntax_source_detail(patch.code_content)}"
            )
            return _cr("C6_ast_syntax", False, "light", detail, t0)

    # ------------------------------------------------------------------
    # C7: Interface signature — validate the active research-surface interface.
    # ------------------------------------------------------------------

    def _c7_interface_signature(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
        enforce_public_interface: bool,
    ) -> CheckResult:
        return check_surface_interface(
            patch,
            problem_spec=self._spec,
            selected_surface=selected_surface,
            operator_execute_signature=self._operator_signature.display,
            enforce_public_interface=enforce_public_interface,
            check_name="C7_interface",
            severity="light",
        )

    # ------------------------------------------------------------------
    # C8: Import whitelist
    # ------------------------------------------------------------------

    def _c8_import_whitelist(
        self,
        patch: PatchProposal,
        *,
        patch_graph: PatchSetGraph | None = None,
        base_file_content: Callable[[str], str | None] | None = None,
    ) -> CheckResult:
        return check_import_whitelist(
            patch,
            problem_spec=self._spec,
            patch_graph=patch_graph,
            is_editable_solver_file=self._is_solver_design_patch_path,
            relative_import_file_exists=(
                self._relative_import_file_exists(base_file_content)
            ),
            relative_import_source=(base_file_content or self._champion_file_content),
        )

    def _relative_import_file_exists(
        self,
        base_file_content: Callable[[str], str | None] | None,
    ) -> Callable[[str], bool]:
        reader = base_file_content or self._champion_file_content

        def exists(file_rel: str) -> bool:
            return reader(file_rel) is not None

        return exists

    # ------------------------------------------------------------------
    # C9: Sensitive API detection
    # ------------------------------------------------------------------

    def _c9_sensitive_api(
        self,
        patch: PatchProposal,
        *,
        selected_surface: str | None = None,
    ) -> CheckResult:
        del selected_surface
        return check_sensitive_api(patch)

    def _champion_file_content(self, file_rel: str) -> str | None:
        return self._file_content_provider()(file_rel)

    def _file_content_provider(
        self,
        snapshot_path: str | None = None,
        *,
        source_overrides: Mapping[str, str] | None = None,
    ) -> Callable[[str], str | None]:
        root_path = str(snapshot_path or "").strip() or self._current_champion_snapshot_path()
        overrides = dict(self._source_overrides)
        overrides.update(_normalize_source_overrides(source_overrides))

        def read_file(file_rel: str) -> str | None:
            try:
                normalized = normalize_relative_patch_path(file_rel)
            except ValueError:
                normalized = str(file_rel or "").replace("\\", "/").lstrip("/")
            if normalized in overrides:
                return overrides[normalized]
            return self._file_content_from_snapshot(root_path, file_rel)

        return read_file

    @staticmethod
    def _file_content_from_snapshot(
        snapshot_path: str | None,
        file_rel: str,
    ) -> str | None:
        if not snapshot_path:
            return None
        try:
            root = Path(snapshot_path).expanduser().resolve(strict=False)
            path = (root / file_rel).resolve(strict=False)
            path.relative_to(root)
        except Exception:
            return None
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _current_champion_snapshot_path(self) -> str | None:
        if self._champion_snapshot_provider is not None:
            try:
                value = self._champion_snapshot_provider()
            except Exception:
                value = None
            if value:
                return str(value)
        return self._champion_snapshot_path

    # ------------------------------------------------------------------
    # C9b: Non-rng random source detection
    # ------------------------------------------------------------------

    def _c9b_non_rng_random(self, patch: PatchProposal) -> CheckResult:
        return check_non_rng_random(patch)

    @staticmethod
    def _selected_surface_name(
        hypothesis: HypothesisProposal | None,
    ) -> str | None:
        if hypothesis is None:
            return None
        name = str(getattr(hypothesis, "change_locus", "") or "").strip()
        return name or None

    def _is_solver_design_patch_path(
        self,
        file_rel: str,
    ) -> bool:
        normalized = str(file_rel or "").replace("\\", "/").lstrip("/")
        surface = self._surface_access.surface_for_patch_path(normalized)
        if surface is None:
            return False
        kind = str(getattr(surface, "kind", "") or "").strip()
        role = str(
            getattr(getattr(surface, "algorithm", None), "role", "") or ""
        )
        return kind in {"solver_design", "solver_algorithm"} or role in {
            "solver_design",
            "solver_algorithm",
        }
