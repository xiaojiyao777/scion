"""Tests for scion.cli.main — inspect and report subcommands."""
from __future__ import annotations

import uuid
from pathlib import Path

from scion.lineage.registry import LineageRegistry








def _write_minimal_problem(tmp_path: Path) -> Path:
    root_dir = tmp_path / "workspace"
    root_dir.mkdir()
    problem_yaml = tmp_path / "problem.yaml"
    problem_yaml.write_text(
        "\n".join(
            [
                "name: cli-agentic-test",
                f"root_dir: {root_dir}",
                "description: CLI APS wiring test",
                "operator_categories: []",
                "search_space:",
                "  editable: []",
                "  frozen: []",
                "  import_whitelist: []",
            ]
        ),
        encoding="utf-8",
    )
    return problem_yaml


def _write_minimal_problem_v1_package(
    tmp_path: Path,
    *,
    required_python_modules: list[str] | None = None,
    measurement_block: str = "",
    research_surfaces_block: str = "",
) -> Path:
    root_dir = tmp_path / "workspace"
    root_dir.mkdir()
    problem_yaml = tmp_path / "problem.yaml"
    problem_yaml.write_text(
        "\n".join(
            [
                "name: fakecli",
                f"root_dir: {root_dir}",
                "description: CLI problem-v1 preflight test",
                "operator_categories: []",
                "search_space:",
                "  editable: []",
                "  frozen: []",
                "  import_whitelist: []",
            ]
        ),
        encoding="utf-8",
    )

    modules = required_python_modules or []
    module_lines = "\n".join(f"    - {module}" for module in modules)
    runtime_block = (
        "\n".join(
            [
                "runtime_dependencies:",
                "  required_python_modules:",
                module_lines,
            ]
        )
        if modules
        else ""
    )
    problem_v1_yaml = tmp_path / "problem-v1.yaml"
    problem_v1_yaml.write_text(
        "\n".join(
            line
            for line in [
                'spec_version: "problem-v1"',
                "id: fakecli",
                'display_name: "Fake CLI"',
                "root_dir: PLACEHOLDER",
                "description: CLI problem-v1 preflight test",
                "search_space:",
                "  editable: []",
                "  frozen: []",
                "  import_whitelist: []",
                "solver:",
                "  time_limit_sec: 1",
                "  max_iter: 1",
                "parameter_search:",
                "  enabled: false",
                runtime_block,
                "operator_interface:",
                '  base_class_import: "scion.problems.fakecli.operators.base:FakeOperator"',
                '  execute_signature: "execute(self, solution, rng) -> Solution"',
                "  categories: []",
                research_surfaces_block,
                "objective_policy:",
                "  mode: single",
                "objectives:",
                "  - name: cost",
                "    direction: minimize",
                "    priority: 1",
                measurement_block,
                "adapter:",
                '  import_path: "scion.problems.fakecli.adapter:FakeAdapter"',
                '  api_version: "v1"',
            ]
            if line
        ),
        encoding="utf-8",
    )
    return problem_yaml








_FORCE_SURFACE_BLOCK = "\n".join(
    [
        "research_surfaces:",
        "  - name: algorithm_blueprint",
        "    kind: config",
        "    description: Forced surface test",
        "    targets:",
        "      files:",
        "        - policies/algorithm_blueprint.py",
        "      create_new_allowed: false",
        "      modify_allowed: true",
        "      remove_allowed: false",
        "      singleton: true",
    ]
)


















def _make_campaign(tmp_path: Path) -> tuple[Path, str]:
    """Set up a minimal campaign dir with an ordinary lineage database."""
    campaign_dir = tmp_path / "campaign"
    campaign_dir.mkdir()

    # Create scion.db with some records
    registry = LineageRegistry(str(campaign_dir / "scion.db"))

    branch_id = str(uuid.uuid4())
    # Record an event
    registry.record_event({
        "branch_id": branch_id,
        "hypothesis_text": "Test hypothesis text",
        "contract_result": "passed",
        "verification_result": "passed",
        "decision": "continue_explore",
        "decision_reason": "low win rate",
    })

    return campaign_dir, branch_id












# ---------------------------------------------------------------------------
# T17b: CLI / Report Polish tests
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
