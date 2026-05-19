from __future__ import annotations

"""Shared support for split tests."""

import scion.proposal.tools.preview as preview_tools
from scion.proposal.solver_design_smoke import _runtime_algorithm_smoke_preview
from scion.proposal.tools.active_solver import algorithm_file_path_guidance

from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalSessionState,
    AgenticToolLoopConfig,
    CapturingToolClient,
    ChampionState,
    CreativeLayer,
    FakeCreative,
    HypothesisProposal,
    PatchProposal,
    Path,
    PlanningCreative,
    ProposalObservation,
    ProposalToolRegistry,
    RunResult,
    SeedLedgerConfig,
    SimpleNamespace,
    SplitManifest,
    _CVRP_ROOT,
    _algorithm_smoke_failure_detail,
    _code_observation_prompt_payload,
    _code_prompt_observations,
    _compact_algorithm_smoke_observation,
    _context,
    _cvrp_context,
    _cvrp_context_with_champion,
    _json_size,
    _latest_preview_failure_detail,
    _observation_prompt_payload,
    _resolve_smoke_instance_path,
    _solver_design_low_effort_issue,
    _solver_run_failure_detail,
    _tool_enabled_policy,
    _valid_hypothesis_payload,
    json,
    legacy_problem_spec_from_v1,
    pytest,
    replace,
    shutil,
)




__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
