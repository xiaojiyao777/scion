from __future__ import annotations

from scion.core.models import (
    HypothesisProposal,
    MechanismChange,
    PatchFileChange,
    PatchProposal,
)
from scion.proposal.agentic_session_patch_flow import (
    _code_context_with_required_full_integration_files,
    _code_integration_visibility_issue,
    _code_stage_identity_issue,
)
from scion.proposal.engine.code_prompts import _split_code_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest


def _hypothesis(mechanism_id: str = "nblist_or_opt1") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="Add a bounded mechanism.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        mechanism_changes=(
            MechanismChange(id=mechanism_id, change_type="add"),
        ),
    )


def _patch(
    *,
    mechanism_id: str = "nblist_or_opt1",
    code: str = "def apply(context):\n    context.record_iteration('nblist_or_opt1', 1)\n",
    additional_changes: tuple[PatchFileChange, ...] = (),
) -> PatchProposal:
    return PatchProposal(
        file_path="policies/baseline_modules/local_search.py",
        action="modify",
        code_content=code,
        mechanism_changes=(
            MechanismChange(id=mechanism_id, change_type="add"),
        ),
        additional_changes=additional_changes,
    )


def test_code_stage_identity_rejects_mechanism_rename() -> None:
    issue = _code_stage_identity_issue(
        _hypothesis("nblist_or_opt1"),
        _patch(
            mechanism_id="or_opt1_nn",
            code="def apply(context):\n    context.record_iteration('or_opt1_nn', 1)\n",
        ),
    )

    assert issue is not None
    assert "code_stage_identity_mismatch" in issue
    assert "nblist_or_opt1" in issue
    assert "or_opt1_nn" in issue


def test_code_stage_identity_allows_declared_budget_mechanism() -> None:
    issue = _code_stage_identity_issue(
        _hypothesis("alns_vns_budget_split"),
        _patch(
            mechanism_id="alns_vns_budget_split",
            code=(
                "def apply(context):\n"
                "    context.record_iteration('alns_vns_budget_split', 1)\n"
                "    context.record_phase('alns_vns_budget_split', 2)\n"
            ),
        ),
    )

    assert issue is None


def test_code_stage_identity_rejects_telemetry_for_undeclared_mechanism() -> None:
    issue = _code_stage_identity_issue(
        _hypothesis("nblist_or_opt1"),
        _patch(
            mechanism_id="nblist_or_opt1",
            code=(
                "def apply(context):\n"
                "    context.record_iteration('or_opt1_nn', 1)\n"
            ),
        ),
    )

    assert issue is not None
    assert "code_stage_telemetry_identity_mismatch" in issue
    assert "or_opt1_nn" in issue


def test_code_stage_identity_ignores_existing_baseline_telemetry_ids() -> None:
    before = (
        "def solve(self):\n"
        "    self.context.record_phase('vns_embedded', 1)\n"
        "    self.context.record_phase('vns_initial', 1)\n"
        "    return best\n"
    )
    after = before.replace(
        "    return best\n",
        "    self.context.record_iteration('vns_terminal_polish', 1)\n"
        "    return best\n",
    )

    issue = _code_stage_identity_issue(
        _hypothesis("vns_terminal_polish"),
        _patch(
            mechanism_id="vns_terminal_polish",
            code=after,
        ),
        code_context={
            "target_file": "policies/baseline_modules/local_search.py",
            "target_file_code": before,
        },
    )

    assert issue is None


def test_code_stage_identity_rejects_new_off_brief_telemetry_id() -> None:
    before = (
        "def solve(self):\n"
        "    self.context.record_phase('vns_initial', 1)\n"
        "    return best\n"
    )
    after = before.replace(
        "    return best\n",
        "    self.context.record_iteration('or_opt1_nn', 1)\n"
        "    return best\n",
    )

    issue = _code_stage_identity_issue(
        _hypothesis("nblist_or_opt1"),
        _patch(
            mechanism_id="nblist_or_opt1",
            code=after,
        ),
        code_context={
            "target_file": "policies/baseline_modules/local_search.py",
            "target_file_code": before,
        },
    )

    assert issue is not None
    assert "code_stage_telemetry_identity_mismatch" in issue
    assert "or_opt1_nn" in issue
    assert "vns_initial" not in issue


def test_code_stage_identity_uses_provider_declared_structural_telemetry() -> None:
    patch = _patch(
        mechanism_id="nblist_or_opt1",
        code=(
            "def apply(context):\n"
            "    context.record_phase('construction', 1)\n"
        ),
    )

    without_provider_taxonomy = _code_stage_identity_issue(
        _hypothesis("nblist_or_opt1"),
        patch,
        code_context={},
    )
    with_provider_taxonomy = _code_stage_identity_issue(
        _hypothesis("nblist_or_opt1"),
        patch,
        code_context={
            "active_subject_taxonomy": {
                "telemetry_identity_allowlist": ("construction",),
            },
        },
    )

    assert without_provider_taxonomy is not None
    assert "code_stage_telemetry_identity_mismatch" in without_provider_taxonomy
    assert with_provider_taxonomy is None


def test_code_integration_visibility_requires_full_visible_additional_file() -> None:
    patch = _patch(
        additional_changes=(
            PatchFileChange(
                file_path="policies/baseline_modules/scheduler.py",
                action="modify",
                code_content="def schedule():\n    return None\n",
            ),
        )
    )
    manifest = {
        "code_file_visibility_ledger": {
            "target_file": {
                "file_path": "policies/baseline_modules/local_search.py",
                "full_content_visible_in_rendered_prompt": True,
            },
            "integration_files": [
                {
                    "file_path": "policies/baseline_modules/scheduler.py",
                    "full_content_visible_in_rendered_prompt": False,
                }
            ],
        }
    }

    issue = _code_integration_visibility_issue(patch, manifest)

    assert issue is not None
    assert issue["paths"] == ("policies/baseline_modules/scheduler.py",)


def test_code_prompt_manifest_records_required_full_integration_source() -> None:
    scheduler_source = "def schedule():\n    return 'old'\n"
    required_section = (
        "### policies/baseline_modules/scheduler.py\n"
        "Provenance: test\n"
        f"```python\n{scheduler_source}```"
    )
    context = {
        "problem_summary": "CVRP",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "hypothesis_detail": "Add local search mechanism.",
        "target_file": "policies/baseline_modules/local_search.py",
        "target_file_code": (
            "File: policies/baseline_modules/local_search.py\n"
            "```python\ndef local_search():\n    return None\n```"
        ),
        "operator_interface_spec": "solver design",
        "import_whitelist": "- math",
        "editable_patterns": "policies/baseline_modules/*.py",
        "frozen_patterns": "vrp/**",
        "agentic_required_full_integration_files": required_section,
        "solver_design_branch_current_integration_files": (
            "### policies/baseline_modules/scheduler.py\n"
            "```python\n"
            "def schedule():\n    return 'old'\n"
            "... <truncated solver-design branch-current integration files for compact code generation>"
            "\n```"
        ),
    }
    system_blocks, user_prompt = _split_code_context(context)
    manifest = build_api_visible_prompt_manifest(
        session_id="session",
        phase="draft_patch",
        call_kind="code",
        prompt_context=context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )
    patch = _patch(
        additional_changes=(
            PatchFileChange(
                file_path="policies/baseline_modules/scheduler.py",
                action="modify",
                code_content="def schedule():\n    return 'new'\n",
            ),
        )
    )

    ledger = manifest["code_file_visibility_ledger"]
    scheduler_record = next(
        record
        for record in ledger["integration_files"]
        if record["file_path"] == "policies/baseline_modules/scheduler.py"
    )
    assert scheduler_record["role"] == "required_full_integration_edit_source"
    assert scheduler_record["full_content_visible_in_rendered_prompt"] is True
    assert _code_integration_visibility_issue(patch, manifest) is None


def test_required_full_integration_projection_uses_full_algorithm_read_source() -> None:
    local_path = "policies/baseline_modules/local_search.py"
    local_source = "LOCAL_SEARCH_OPS = []\n"
    retry_context = _code_context_with_required_full_integration_files(
        {
            "agentic_tool_observations": [
                {
                    "observation_id": "obs-local-search",
                    "tool_name": "context.read_algorithm_file",
                    "is_error": False,
                    "structured_payload": {
                        "file_path": local_path,
                        "readable": True,
                        "active": True,
                        "truncated": False,
                        "size_chars": len(local_source),
                        "max_chars": len(local_source),
                        "content_preview": local_source,
                    },
                }
            ],
            "solver_design_branch_current_integration_files": "",
        },
        [local_path],
    )

    required = retry_context["agentic_required_full_integration_files"]
    assert f"### {local_path}" in required
    assert local_source in required
