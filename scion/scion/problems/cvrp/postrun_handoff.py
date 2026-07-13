"""CVRP-owned report-only prepared handoff metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from scion.postrun.handoff.prompt_context_readiness import ProblemPromptBridgeSpec
from scion.problems.cvrp.prompt_bridge import CVRP_PROMPT_BRIDGE_SPEC


CoverageItemFactory = Callable[[int, str], dict[str, Any]]


class CvrpPreparedHandoffReviewPort:
    """Expose CVRP guidance as report-only context, never as launch policy."""

    problem_family = "cvrp"

    def prepared_contract_checks(
        self,
        manifest: Mapping[str, Any],
        *,
        manifest_run_root: str = "",
        local_run_root: Path | None = None,
        repo_dir: Path,
        scion_project_dir: Path,
    ) -> dict[str, dict[str, Any]]:
        del manifest_run_root, local_run_root, repo_dir, scion_project_dir
        if manifest.get("problem_family") != self.problem_family:
            return {}
        return {
            "cvrp_problem_guidance_non_gating": {
                "passed": True,
                "detail": {
                    "report_only": True,
                    "decision_features_excluded": True,
                    "content_required_for_launch": False,
                },
            }
        }

    def phase4_requirements(
        self,
        manifest: Mapping[str, Any],
        coverage_item: CoverageItemFactory,
    ) -> dict[str, Any]:
        del manifest, coverage_item
        return {}

    def prepared_prompt_context_signals(
        self,
        manifest: Mapping[str, Any],
        research_focus: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        if manifest.get("problem_family") != self.problem_family:
            return {}
        return {
            "cvrp_problem_guidance_context": {
                "available": bool(research_focus),
                "required": False,
                "source": "prepared_run_manifest.research_focus",
                "detail": {
                    "report_only": True,
                    "decision_features_excluded": True,
                    "field_count": len(research_focus),
                },
                "runtime_generated_after_launch": False,
            }
        }

    def prompt_bridge_spec(self) -> ProblemPromptBridgeSpec:
        return CVRP_PROMPT_BRIDGE_SPEC
