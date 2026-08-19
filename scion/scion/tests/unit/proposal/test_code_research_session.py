from __future__ import annotations

import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from scion.core.code_research_limits import (
    CodeResearchLimits,
    load_code_research_limits,
)
from scion.core.models import (
    Branch,
    BranchState,
    ChampionState,
    HypothesisProposal,
)
from scion.core.proposal_pipeline import ProposalPipeline
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ProviderCallCapExhausted,
)
from scion.proposal.code_research_session import (
    CodeResearchAbandon,
    CodeResearchSession,
)
from scion.proposal.engine import (
    CreativeLayer,
    ProposalValidationError,
    build_prompt_turn_snapshot,
)
from scion.proposal.engine.provider_call import ProviderResponseSizeExceeded

_TARGET_PATH = "operators/main.py"
_SUPPORT_PATH = "operators/helper.py"
_UNAVAILABLE_PATH = "operators/unavailable.py"
_TARGET_SOURCE = "def improve(value):\n    return value\n"
_SUPPORT_SOURCE = "def helper(value):\n    return value * 2\n"


def _patch(path: str = _TARGET_PATH) -> dict[str, Any]:
    old = "return value" if path == _TARGET_PATH else "return value * 2"
    new = "return value + 1" if path == _TARGET_PATH else "return value * 3"
    return {
        "file_path": path,
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": old,
        "new_string": new,
        "replace_all": False,
        "evidence_refs": [],
    }


def _snapshot():
    return build_prompt_turn_snapshot(
        "code",
        {
            "problem_summary": "Generic optimization subject.",
            "branch_id": "code-research-branch",
            "approved_hypothesis": {
                "hypothesis_text": "Improve one bounded generic operation."
            },
            "editable_source_context": {
                "approved_target": _TARGET_PATH,
                "sources": [
                    {"path": _TARGET_PATH, "content": _TARGET_SOURCE},
                    {"path": _SUPPORT_PATH, "content": _SUPPORT_SOURCE},
                    {"path": _UNAVAILABLE_PATH, "content": None},
                ],
                "target_api_guidance": "Preserve the public callable.",
            },
            "operator_interface_spec": "",
            "editable_patterns": "operators/*.py",
            "frozen_patterns": "",
        },
    )


class _SequenceClient:
    model = "fake-code-research-model"

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def call_with_tool(
        self,
        prompt: str,
        tool: dict[str, Any],
        _model: str,
        *,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "request_kind": request_kind,
                "tool_name": tool["name"],
                "prompt": prompt,
                "system_text": "\n".join(
                    str(block.get("text") or "") for block in system_blocks
                ),
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


def _run(
    responses: list[Any],
    *,
    limits: CodeResearchLimits | None = None,
    budget: ProviderCallBudget | None = None,
    trace_dir: str | None = None,
):
    client = _SequenceClient(responses)
    creative = CreativeLayer(
        client,
        trace_dir=trace_dir,
        provider_call_budget=budget,
    )
    session = CodeResearchSession(creative, limits or CodeResearchLimits())
    return session, client


def test_read_search_ready_then_independent_finalize_in_order() -> None:
    session, client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "search_source", "path": _SUPPORT_PATH, "query": "* 2"},
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=3),
    )

    result = session.run(_snapshot())

    assert result.code_content == _TARGET_SOURCE.replace(
        "return value", "return value + 1"
    )
    assert [call["request_kind"] for call in client.calls] == [
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "code_research_finalize",
    ]
    assert [call["tool_name"] for call in client.calls] == [
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "finalize_code_research",
    ]
    assert "def helper(value)" not in client.calls[0]["system_text"]
    assert "def helper(value)" in client.calls[1]["system_text"]
    assert "frozen_ready_patch" in client.calls[-1]["system_text"]
    assert session.provider_calls_used == 4


def test_read_cap_is_a_safe_observation_before_ready() -> None:
    session, client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "read_source", "path": _TARGET_PATH},
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=3, max_read_calls=1),
    )

    session.run(_snapshot())

    assert "read_call_cap_exhausted" in client.calls[2]["system_text"]


@pytest.mark.parametrize(
    ("limit_overrides", "reason"),
    [
        ({"max_read_chars": 10}, "read_char_cap_exhausted"),
        ({"max_read_bytes": 10}, "read_byte_cap_exhausted"),
        ({"max_read_lines": 1}, "read_line_cap_exhausted"),
    ],
)
def test_read_character_and_line_totals_are_bounded(
    limit_overrides: dict[str, int],
    reason: str,
) -> None:
    session, client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=2, **limit_overrides),
    )

    session.run(_snapshot())

    assert reason in client.calls[1]["system_text"]
    assert "def helper(value)" not in client.calls[1]["system_text"]


@pytest.mark.parametrize(
    "limit_overrides",
    [{"max_search_matches": 1}, {"max_search_bytes": 1}],
)
def test_search_totals_are_bounded_and_reported_as_truncated(
    limit_overrides: dict[str, int],
) -> None:
    session, client = _run(
        [
            {"action": "search_source", "query": "return"},
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=2, **limit_overrides),
    )

    session.run(_snapshot())

    assert '"truncated":true' in client.calls[1]["system_text"]


def test_search_treats_regex_metacharacters_as_literal_text() -> None:
    session, client = _run(
        [
            {"action": "search_source", "query": "return.*value"},
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    session.run(_snapshot())

    assert '"matches":[]' in client.calls[1]["system_text"]


def test_cumulative_prompt_bound_blocks_before_provider_dispatch() -> None:
    session, client = _run(
        [{"action": "ready", "patch": _patch()}],
        limits=CodeResearchLimits(max_turns=1, max_transcript_chars=2000),
    )

    with pytest.raises(ProposalValidationError, match="before dispatch"):
        session.run(_snapshot())

    assert client.calls == []
    assert session.provider_calls_used == 0


@pytest.mark.parametrize(
    "path",
    ["../../etc/passwd", "/etc/passwd", r"operators\helper.py", "a\x00b.py"],
)
def test_read_rejects_noncanonical_paths_without_filesystem_access(path: str) -> None:
    session, client = _run(
        [
            {"action": "read_source", "path": path},
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    session.run(_snapshot())

    assert "invalid_path" in client.calls[1]["system_text"]
    assert "def helper(value)" not in client.calls[1]["system_text"]


def test_hidden_and_missing_sources_have_the_same_tool_result() -> None:
    responses = [
        {"action": "read_source", "path": _UNAVAILABLE_PATH},
        {"action": "read_source", "path": "operators/not-listed.py"},
        {"action": "ready", "patch": _patch()},
        {"outcome": "finalize_patch"},
    ]
    session, client = _run(responses, limits=CodeResearchLimits(max_turns=3))

    session.run(_snapshot())

    assert "source_not_visible" in client.calls[1]["system_text"]
    assert client.calls[2]["system_text"].count("source_not_visible") == 2
    assert "def helper(value)" not in client.calls[2]["system_text"]


def test_search_excerpt_does_not_make_an_unread_file_patchable() -> None:
    session, client = _run(
        [
            {"action": "search_source", "path": _SUPPORT_PATH, "query": "helper"},
            {"action": "ready", "patch": _patch(_SUPPORT_PATH)},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    with pytest.raises(ProposalValidationError, match="was not read"):
        session.run(_snapshot())

    assert len(client.calls) == 2
    assert "def helper" in client.calls[1]["system_text"]
    assert _SUPPORT_SOURCE not in client.calls[1]["system_text"]


@pytest.mark.parametrize(
    "path",
    ["/operators/main.py", "operators/../main.py", r"operators\main.py"],
)
def test_ready_patch_rejects_every_noncanonical_file_path(path: str) -> None:
    session, client = _run(
        [{"action": "ready", "patch": _patch(path)}],
        limits=CodeResearchLimits(max_turns=1),
    )

    with pytest.raises(ProposalValidationError, match="canonical relative path"):
        session.run(_snapshot())

    assert len(client.calls) == 1


def test_final_turn_can_explicitly_abandon_the_frozen_candidate() -> None:
    session, _client = _run(
        [
            {"action": "ready", "patch": _patch()},
            {"outcome": "abandon", "reason": "Evidence is insufficient."},
        ],
        limits=CodeResearchLimits(max_turns=1),
    )

    result = session.run(_snapshot())

    assert result == CodeResearchAbandon(reason="Evidence is insufficient.")


def test_finalize_without_ready_is_rejected() -> None:
    session, _client = _run(
        [
            {"action": "search_source", "query": "improve"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=1),
    )

    with pytest.raises(ProposalValidationError, match="prior ready"):
        session.run(_snapshot())


def test_global_cap_rejection_does_not_increment_local_used() -> None:
    budget = ProviderCallBudget(1)
    session, client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "ready", "patch": _patch()},
        ],
        limits=CodeResearchLimits(max_turns=2),
        budget=budget,
    )

    with pytest.raises(ProviderCallCapExhausted):
        session.run(_snapshot())

    assert budget.used == 1
    assert session.provider_calls_used == 1
    assert len(client.calls) == 1


def test_patch_file_and_character_caps_fail_before_finalize() -> None:
    too_many_files = _patch()
    too_many_files["additional_changes"] = [_patch(_SUPPORT_PATH)]
    file_session, file_client = _run(
        [{"action": "ready", "patch": too_many_files}],
        limits=CodeResearchLimits(max_turns=1, max_patch_files=1),
    )
    with pytest.raises(ProposalValidationError, match="max_patch_files"):
        file_session.run(_snapshot())
    assert len(file_client.calls) == 1

    large_patch = {
        "file_path": _TARGET_PATH,
        "action": "modify",
        "edit_intent": "full_file",
        "content_after": "x" * 1500,
        "full_file_reason": "bounded test",
        "evidence_refs": [],
    }
    char_session, char_client = _run(
        [{"action": "ready", "patch": large_patch}],
        limits=CodeResearchLimits(max_turns=1, max_patch_chars=1000),
    )
    with pytest.raises(ProposalValidationError, match="max_patch_chars"):
        char_session.run(_snapshot())
    assert len(char_client.calls) == 1


def test_oversized_provider_action_is_not_written_to_terminal_trace(
    tmp_path: Path,
) -> None:
    sentinel = "OVERSIZED_SENTINEL_" * 100
    session, _client = _run(
        [{"action": "search_source", "query": sentinel}],
        limits=CodeResearchLimits(max_turns=1, max_action_bytes=1000),
        trace_dir=str(tmp_path),
    )

    with pytest.raises(ProviderResponseSizeExceeded):
        session.run(_snapshot())

    trace_text = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json")
    )
    assert "OVERSIZED_SENTINEL_OVERSIZED_SENTINEL" not in trace_text
    assert "ProviderResponseSizeExceeded" in trace_text
    assert session.provider_calls_used == 1


def test_limits_json_is_strict_and_enables_by_file_presence(tmp_path: Path) -> None:
    path = tmp_path / "limits.json"
    path.write_text('{"max_turns":2,"max_read_calls":1}', encoding="utf-8")

    limits = load_code_research_limits(path)

    assert limits.max_turns == 2
    assert limits.max_read_calls == 1
    assert limits.max_search_calls == 3
    bad = tmp_path / "bad.json"
    bad.write_text('{"max_turns":2,"workspace":"/tmp"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        load_code_research_limits(bad)


def test_enabled_limits_reach_the_normal_proposal_pipeline() -> None:
    _session, client = _run(
        [
            {"action": "ready", "patch": _patch()},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=1),
    )

    class _Runtime:
        def build_code_context(self, **_kwargs: Any) -> dict[str, Any]:
            return _snapshot().structured_context

    branch = Branch(
        branch_id="code-research-branch",
        state=BranchState.EXPLORE,
        base_champion_id=1,
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path="/unused-by-source-only-session",
    )
    pipeline = ProposalPipeline(
        creative=CreativeLayer(client),
        problem_runtime=_Runtime(),
        branch_workspaces={},
        champion_lock=threading.Lock(),
        get_champion=lambda: champion,
        step_history=[],
        mark_balance_exhausted=lambda: None,
        code_research_limits=CodeResearchLimits(max_turns=1),
    )
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve one bounded generic operation.",
        change_locus="generic",
        action="modify",
        target_file=_TARGET_PATH,
    )

    attempt = pipeline.generate_code(branch, hypothesis)

    assert attempt.proposal is not None
    assert attempt.proposal.code_content.endswith("return value + 1\n")
    assert [call["request_kind"] for call in client.calls] == [
        "code_research_turn",
        "code_research_finalize",
    ]
