from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.qualification import QualificationOnlyConfig
from scion.core.resource_envelope import ResourceEnvelope
from scion.proposal.llm_client import LLMProviderError
from scion.tests.campaign_test_support import (
    _VALID_HYPOTHESIS,
    _campaign,
)

_K2_MODE = "bounded_hypothesis_candidates_v1"


class _NoCallClient:
    model = "k2-no-call-model"

    def call_with_tool(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("K2 composition unexpectedly dispatched a provider")


def _limits() -> CodeResearchLimits:
    return CodeResearchLimits(
        max_turns=4,
        max_hypothesis_candidates=2,
    )


def _complete_envelope() -> ResourceEnvelope:
    return ResourceEnvelope(provider_call_cap=12, outer_hardwall_sec=60)


@pytest.mark.parametrize(
    ("qualification", "envelope", "reason"),
    (
        (None, _complete_envelope(), "qualification_only"),
        (
            QualificationOnlyConfig(),
            ResourceEnvelope(outer_hardwall_sec=60),
            "provider_call_cap",
        ),
        (
            QualificationOnlyConfig(),
            ResourceEnvelope(provider_call_cap=12),
            "outer_hardwall_sec",
        ),
    ),
)
def test_k2_composition_requires_qualification_and_complete_envelope_before_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qualification: QualificationOnlyConfig | None,
    envelope: ResourceEnvelope,
    reason: str,
) -> None:
    def development_tripwire(**_kwargs: Any) -> None:
        raise AssertionError("K2 boundary ran after development closure")

    monkeypatch.setattr(
        "scion.core.campaign_composition.validate_development_closure_boundary",
        development_tripwire,
    )

    with pytest.raises(ValueError, match=reason):
        _campaign(
            tmp_path,
            llm_client=_NoCallClient(),
            qualification_only=qualification,
            resource_envelope=envelope,
            code_research_limits=_limits(),
        )

    assert not (tmp_path / "campaign").exists()


def test_k2_valid_composition_persists_config_and_projects_frozen_mode(
    tmp_path: Path,
) -> None:
    cm = _campaign(
        tmp_path,
        llm_client=_NoCallClient(),
        qualification_only=QualificationOnlyConfig(),
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )
    configured = json.loads(
        (tmp_path / "campaign" / "code_research_limits.json").read_text(
            encoding="utf-8"
        )
    )

    cm.finalize_requested_stop("operator_requested_stop")

    status = json.loads(
        (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (tmp_path / "campaign" / "campaign_summary.json").read_text(encoding="utf-8")
    )
    assert configured["max_hypothesis_candidates"] == 2
    assert cm.get_state()["proposal_runtime_mode"] == _K2_MODE
    assert status["proposal_runtime_mode"] == _K2_MODE
    assert summary["proposal_runtime_mode"] == _K2_MODE


class _K2ThenCodeFailureClient:
    model = "k2-artifact-boundary-model"

    def __init__(self, *, loser: str, selected: str) -> None:
        loser_hypothesis = deepcopy(_VALID_HYPOTHESIS)
        loser_hypothesis["hypothesis_text"] = loser
        selected_hypothesis = deepcopy(_VALID_HYPOTHESIS)
        selected_hypothesis["hypothesis_text"] = selected
        basis = {
            "read_refs": ["source-0001"],
            "nearest_prior_refs": [],
            "material_delta": "This mechanism is distinct from current history.",
            "alternatives_considered": ["Retain the current local search."],
            "observable_prediction": "The public development metric will change.",
            "falsification_condition": "Reject if that metric does not change.",
        }
        self._hypothesis_responses = [
            {"action": "read_source", "ref": "source-0001"},
            {
                "action": "stage_hypothesis_candidate",
                "slot": 1,
                "hypothesis": loser_hypothesis,
                "research_basis": deepcopy(basis),
            },
            {
                "action": "stage_hypothesis_candidate",
                "slot": 2,
                "hypothesis": selected_hypothesis,
                "research_basis": deepcopy(basis),
            },
            {"action": "select_hypothesis_candidate", "slot": 2},
        ]

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        del system_blocks
        if request_kind == "hypothesis_research_turn":
            return deepcopy(self._hypothesis_responses.pop(0))
        raise LLMProviderError("synthetic code provider stop")


def test_k2_loser_is_trace_only_and_never_authoritative(tmp_path: Path) -> None:
    loser = "K2_CAMPAIGN_TRACE_ONLY_LOSER_SENTINEL"
    selected = "K2_CAMPAIGN_SELECTED_SENTINEL"
    cm = _campaign(
        tmp_path,
        llm_client=_K2ThenCodeFailureClient(loser=loser, selected=selected),
        qualification_only=QualificationOnlyConfig(max_proposal_attempts=1),
        resource_envelope=_complete_envelope(),
        code_research_limits=_limits(),
    )

    terminal = cm.run(requested_rounds=1)

    assert terminal.stop_reason == "execution_blocked_infra"
    assert len(cm._step_history) == 1
    step = cm._step_history[0]
    assert step.hypothesis is not None
    assert step.hypothesis.hypothesis_text == selected
    assert loser not in repr(cm._step_history)
    trace_text = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "campaign" / "llm_traces").glob("*.json")
    )
    assert loser in trace_text

    authoritative_files = [
        path
        for path in (tmp_path / "campaign").rglob("*")
        if path.is_file()
        and "llm_traces" not in path.relative_to(tmp_path / "campaign").parts
    ]
    assert authoritative_files
    for path in authoritative_files:
        assert loser.encode() not in path.read_bytes(), path
    status_text = (tmp_path / "campaign" / "status.json").read_text(encoding="utf-8")
    summary_text = (tmp_path / "campaign" / "campaign_summary.json").read_text(
        encoding="utf-8"
    )
    assert selected in summary_text
    assert json.loads(status_text)["proposal_runtime_mode"] == _K2_MODE
    assert json.loads(summary_text)["proposal_runtime_mode"] == _K2_MODE
