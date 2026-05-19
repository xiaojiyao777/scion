from __future__ import annotations

"""Shared fixtures/helpers for agentic session behavior tests."""

import scion.proposal.tools.preview as preview_tools
from scion.core.public_refs import contains_absolute_path
from scion.proposal.agentic_artifacts import inspect_agentic_session_artifact
from scion.proposal.agentic_session import AgenticProposalOutput, AgenticTranscriptEvent
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import (
    LLM_TRANSIENT_API_ERROR_CATEGORY,
    LLMRetryExhaustedError,
    LLMTransientProviderError,
)
from scion.proposal.tools import ProposalToolPermission
from scion.proposal.tools.models import ReadSurfaceInput
from scion.proposal.tools.preview import AlgorithmSmokeInput, ContractPreviewInput
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticProposalPhase,
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalSessionState,
    AgenticProposalStatus,
    AgenticSessionStore,
    AgenticTerminationReason,
    AgenticToolLoopConfig,
    Branch,
    BranchState,
    CapturingToolClient,
    ContextExposurePolicy,
    CreativeLayer,
    FakeCreative,
    FileAgenticSessionArtifactStore,
    HangingContractPreviewTool,
    HypothesisProposal,
    LargeObservationTool,
    NonCallableRenderMemory,
    PatchProposal,
    Path,
    PlanningCreative,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolRegistry,
    SequentialPatchCreative,
    SimpleNamespace,
    TimeoutThenPatchCreative,
    ToolSelectionClient,
    UnsafeMemory,
    _COMPACT_FEEDBACK_TOOL_NAMES,
    _compact_feedback_observation_for_budget,
    _context,
    _cvrp_context_with_champion,
    _json_size,
    _observation_prompt_payload,
    _research_diagnosis_from_observations,
    _tool_enabled_policy,
    _valid_hypothesis_payload,
    _valid_policy_patch_payload,
    agentic_session_module,
    compute_agentic_idempotency_key,
    json,
    pytest,
    replace,
    resume_from_artifact,
    validate_agentic_session_artifact,
)


class _PatchGraphContractPreviewTool:
    name = "proposal.contract_preview"
    input_schema = ContractPreviewInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    read_only = True
    concurrency_safe = True
    max_result_chars = 60000

    def call(self, args, context: ProposalToolContext) -> ProposalObservation:
        del args
        return ProposalObservation(
            observation_id="contract-patch-graph-failure",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type="contract_preview",
            summary="Contract preview failed: C8 import graph boundary.",
            structured_payload={
                "passed": False,
                "contract": {"failed_checks": ["C8_import_graph_boundary"]},
                "errors": ["C8 import graph boundary failed"],
            },
        )


class _FailingAlgorithmSmokeTool:
    name = "proposal.algorithm_smoke"
    input_schema = AlgorithmSmokeInput
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    read_only = True
    concurrency_safe = True
    max_result_chars = 60000

    def call(self, args, context: ProposalToolContext) -> ProposalObservation:
        del args
        return ProposalObservation(
            observation_id="algorithm-smoke-failure",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type="algorithm_smoke",
            summary="Algorithm smoke failed on synthetic runtime smoke.",
            structured_payload={
                "passed": False,
                "runtime_smoke": {"issues": ["synthetic runtime smoke failed"]},
                "errors": ["synthetic runtime smoke failed"],
            },
        )


class _BudgetAwareReadSurfaceTool:
    name = "context.read_surface"
    input_schema = ReadSurfaceInput
    permission = ProposalToolPermission.READ_CHAMPION_ARTIFACT
    read_only = True
    concurrency_safe = True
    max_result_chars = 200000

    def call(self, args: ReadSurfaceInput, context: ProposalToolContext):
        target_file = args.target_file or "policies/search_policy.py"
        requested_chars = int(args.max_code_chars or 0)
        payload_chars = 90000 if args.detail == "full" else min(requested_chars, 800)
        return ProposalObservation(
            observation_id=f"surface-{args.detail}-{requested_chars}",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type="surface_interface",
            summary=f"Returned {args.detail} surface payload.",
            structured_payload={
                "surface": {"name": args.surface},
                "detail": args.detail,
                "section": args.section,
                "declared_targets": [target_file],
                "target_file": target_file,
                "current_artifact": {
                    "readable": True,
                    "max_chars": requested_chars,
                    "truncated": args.detail != "full",
                    "content": "x" * payload_chars,
                },
                "support_artifacts": [],
            },
            exposure_level=ProposalExposureLevel.CHAMPION_CODE,
        )


def _algorithm_read_observation(
    tool_name: str,
    payload: dict,
) -> ProposalObservation:
    return ProposalObservation(
        observation_id=f"{tool_name}-obs",
        session_id="session-algorithm-read",
        tool_name=tool_name,
        tool_call_id="tool-0001",
        observation_type=tool_name.rsplit(".", 1)[-1],
        summary="Returned algorithm source.",
        structured_payload=payload,
        exposure_level=ProposalExposureLevel.CHAMPION_CODE,
    )


def _algorithm_file_payload(
    file_path: str,
    *,
    max_chars: int,
    preview_chars: int,
    size_chars: int,
    truncated: bool = False,
) -> dict:
    return {
        "file_path": file_path,
        "readable": True,
        "source": "champion_snapshot",
        "content_preview": "x" * preview_chars,
        "truncated": truncated,
        "size_chars": size_chars,
        "max_chars": max_chars,
    }


def _algorithm_symbol_payload(
    file_path: str,
    symbol: str,
    *,
    preview_chars: int,
    truncated: bool = False,
) -> dict:
    return {
        "file_path": file_path,
        "symbol": symbol,
        "readable": True,
        "source": "champion_snapshot",
        "content_preview": "x" * preview_chars,
        "truncated": truncated,
    }


class _HypothesisSchemaFailureCreative(FakeCreative):
    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        raise ProposalValidationError("malformed hypothesis structured output")


class _PatchThenRetryExhaustedCreative(FakeCreative):
    def __init__(self, patch: PatchProposal) -> None:
        super().__init__(patch=patch)
        self._returned_initial_patch = False

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        if not self._returned_initial_patch:
            self._returned_initial_patch = True
            return self.patch
        raise LLMRetryExhaustedError("structured patch output retry exhausted")


class _PatchThenTransientApiErrorCreative(FakeCreative):
    def __init__(self, patch: PatchProposal) -> None:
        super().__init__(patch=patch)
        self._returned_initial_patch = False

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        if not self._returned_initial_patch:
            self._returned_initial_patch = True
            return self.patch
        provider_error = LLMTransientProviderError(
            "Transient provider error: HTTP 502 Bad Gateway "
            "<html><title>502 Bad Gateway</title></html>"
        )
        raise LLMRetryExhaustedError(
            "Tool call failed after 2 transient API attempt(s). "
            f"Last error: {provider_error}",
            last_error=provider_error,
            failure_category=LLM_TRANSIENT_API_ERROR_CATEGORY,
        )


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
