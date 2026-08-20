from __future__ import annotations

import json
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
    PatchProposal,
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
from scion.proposal.engine.provider_call import (
    PromptTurnSnapshot,
    ProviderResponseSizeExceeded,
)

_TARGET_PATH = "operators/main.py"
_SUPPORT_PATH = "operators/helper.py"
_UNAVAILABLE_PATH = "operators/unavailable.py"
_PUBLIC_TEST_PATH = "tests/test_public.py"
_TARGET_SOURCE = "def improve(value):\n    return value\n"
_SUPPORT_SOURCE = "def helper(value):\n    return value * 2\n"
_PUBLIC_TEST_SOURCE = "def test_improve():\n    assert True\n"


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


def _snapshot(*, include_public_test: bool = False):
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
                    {
                        "path": _TARGET_PATH,
                        "content": _TARGET_SOURCE,
                        "roles": ["target"],
                        "visible": True,
                    },
                    {
                        "path": _SUPPORT_PATH,
                        "content": _SUPPORT_SOURCE,
                        "roles": ["peer"],
                        "visible": False,
                    },
                    {
                        "path": _UNAVAILABLE_PATH,
                        "content": None,
                        "roles": ["peer"],
                        "visible": False,
                    },
                ],
                "public_tests": (
                    [
                        {
                            "path": _PUBLIC_TEST_PATH,
                            "content": _PUBLIC_TEST_SOURCE,
                            "check_name": "D3_unit_tests",
                            "visible": True,
                        }
                    ]
                    if include_public_test
                    else []
                ),
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


def _passing_development_test(_patch, _remaining, _corpus):
    return {
        "outcome": "passed",
        "checks": [{"name": "D3_unit_tests", "outcome": "passed"}],
        "counts": {"total": 1, "passed": 1, "failed": 0},
    }


def test_read_search_ready_then_independent_finalize_in_order() -> None:
    session, client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "search_source", "path": _SUPPORT_PATH, "query": "* 2"},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=5),
    )
    session._test_patch = _passing_development_test

    result = session.run(_snapshot())

    assert result.code_content == _TARGET_SOURCE.replace(
        "return value", "return value + 1"
    )
    assert [call["request_kind"] for call in client.calls] == [
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "code_research_finalize",
    ]
    assert [call["tool_name"] for call in client.calls] == [
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "code_research_turn",
        "finalize_code_research",
    ]
    assert "def helper(value)" not in client.calls[0]["system_text"]
    assert "def helper(value)" in client.calls[1]["system_text"]
    assert "frozen_ready_patch" in client.calls[-1]["system_text"]
    assert session.provider_calls_used == 6


def test_read_peer_then_revise_can_bind_that_exact_source() -> None:
    session, _client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "revise", "patch": _patch(_SUPPORT_PATH)},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=4),
    )
    session._test_patch = _passing_development_test

    result = session.run(_snapshot())

    assert result.file_path == _SUPPORT_PATH
    assert result.code_content == _SUPPORT_SOURCE.replace(
        "return value * 2", "return value * 3"
    )


def test_public_development_test_is_visible_but_never_patchable() -> None:
    public_patch = {
        "file_path": _PUBLIC_TEST_PATH,
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": "assert True",
        "new_string": "assert False",
        "replace_all": False,
        "evidence_refs": [],
    }
    session, client = _run(
        [
            {"action": "revise", "patch": public_patch},
            {"outcome": "abandon", "reason": "public tests are read-only"},
        ],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(_snapshot(include_public_test=True))

    assert _PUBLIC_TEST_PATH in client.calls[0]["system_text"]
    assert "test_improve" in client.calls[0]["system_text"]
    assert "public_test_read_only" in client.calls[1]["system_text"]


def test_development_evaluator_receives_only_editable_source_corpus() -> None:
    observed_corpora: list[dict[str, str]] = []

    def test_patch(_patch_value, _remaining, corpus):
        observed_corpora.append(dict(corpus))
        return _passing_development_test(None, 1.0, {})

    session, _client = _run(
        [
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=3),
    )
    session._test_patch = test_patch

    session.run(_snapshot(include_public_test=True))

    assert observed_corpora == [
        {
            _TARGET_PATH: _TARGET_SOURCE,
            _SUPPORT_PATH: _SUPPORT_SOURCE,
        }
    ]


def test_read_cap_is_a_safe_observation_before_ready() -> None:
    session, client = _run(
        [
            {"action": "read_source", "path": _SUPPORT_PATH},
            {"action": "read_source", "path": _TARGET_PATH},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=5, max_read_calls=1),
    )
    session._test_patch = _passing_development_test

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
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=4, **limit_overrides),
    )
    session._test_patch = _passing_development_test

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
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=4, **limit_overrides),
    )
    session._test_patch = _passing_development_test

    session.run(_snapshot())

    assert '"truncated":true' in client.calls[1]["system_text"]


def test_search_treats_regex_metacharacters_as_literal_text() -> None:
    session, client = _run(
        [
            {"action": "search_source", "query": "return.*value"},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=4),
    )
    session._test_patch = _passing_development_test

    session.run(_snapshot())

    assert '"matches":[]' in client.calls[1]["system_text"]


def test_cumulative_prompt_bound_blocks_before_provider_dispatch() -> None:
    session, client = _run(
        [{"action": "ready"}],
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
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=4),
    )
    session._test_patch = _passing_development_test

    session.run(_snapshot())

    assert "invalid_path" in client.calls[1]["system_text"]
    assert "def helper(value)" not in client.calls[1]["system_text"]


def test_hidden_and_missing_sources_have_the_same_tool_result() -> None:
    responses = [
        {"action": "read_source", "path": _UNAVAILABLE_PATH},
        {"action": "read_source", "path": "operators/not-listed.py"},
        {"action": "revise", "patch": _patch()},
        {"action": "test_patch"},
        {"action": "ready"},
        {"outcome": "finalize_patch"},
    ]
    session, client = _run(responses, limits=CodeResearchLimits(max_turns=5))
    session._test_patch = _passing_development_test

    session.run(_snapshot())

    assert "source_not_visible" in client.calls[1]["system_text"]
    assert client.calls[2]["system_text"].count("source_not_visible") == 2
    assert "def helper(value)" not in client.calls[2]["system_text"]


def test_search_excerpt_does_not_make_an_unread_file_patchable() -> None:
    session, client = _run(
        [
            {"action": "search_source", "path": _SUPPORT_PATH, "query": "helper"},
            {"action": "revise", "patch": _patch(_SUPPORT_PATH)},
            {"outcome": "abandon", "reason": "source must be read first"},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    session.run(_snapshot())

    assert len(client.calls) == 3
    assert "def helper" in client.calls[1]["system_text"]
    assert _SUPPORT_SOURCE not in client.calls[1]["system_text"]
    assert "source_not_read" in client.calls[2]["system_text"]


@pytest.mark.parametrize(
    "path",
    ["/operators/main.py", "operators/../main.py", r"operators\main.py"],
)
def test_ready_patch_rejects_every_noncanonical_file_path(path: str) -> None:
    session, client = _run(
        [
            {"action": "revise", "patch": _patch(path)},
            {"outcome": "abandon", "reason": "invalid path"},
        ],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(_snapshot())

    assert "invalid_patch_path" in client.calls[1]["system_text"]


def test_final_turn_can_explicitly_abandon_the_frozen_candidate() -> None:
    session, _client = _run(
        [
            {"action": "revise", "patch": _patch()},
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
            {"action": "revise", "patch": _patch()},
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
        [
            {"action": "revise", "patch": too_many_files},
            {"outcome": "abandon", "reason": "file cap"},
        ],
        limits=CodeResearchLimits(max_turns=1, max_patch_files=1),
    )
    file_session.run(_snapshot())
    assert "patch_file_cap_exhausted" in file_client.calls[1]["system_text"]

    large_patch = {
        "file_path": _TARGET_PATH,
        "action": "modify",
        "edit_intent": "full_file",
        "content_after": "x" * 1500,
        "full_file_reason": "bounded test",
        "evidence_refs": [],
    }
    char_session, char_client = _run(
        [
            {"action": "revise", "patch": large_patch},
            {"outcome": "abandon", "reason": "character cap"},
        ],
        limits=CodeResearchLimits(max_turns=1, max_patch_chars=1000),
    )
    char_session.run(_snapshot())
    assert "patch_char_cap_exhausted" in char_client.calls[1]["system_text"]


def test_invalid_duplicate_file_draft_is_actionable_and_can_be_revised() -> None:
    duplicate = _patch()
    duplicate["additional_changes"] = [_patch()]
    session, client = _run(
        [
            {"action": "revise", "patch": duplicate},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=4),
    )
    session._test_patch = _passing_development_test

    result = session.run(_snapshot())

    assert isinstance(result, PatchProposal)
    assert "duplicate_file_path" in client.calls[1]["system_text"]


def test_transcript_accounting_counts_provider_wire_not_trace_metadata() -> None:
    session, _client = _run(
        [],
        limits=CodeResearchLimits(max_turns=1, max_transcript_chars=2_000),
    )
    snapshot = PromptTurnSnapshot(
        render_kind="code_research",
        system_blocks=({"type": "text", "text": "small"},),
        user_prompt="small",
        provider_tool={"name": "small", "input_schema": {"type": "object"}},
        structured_context_json=json.dumps({"trace_only": "x" * 10_000}),
    )

    result = session._call_provider(snapshot, lambda: {"action": "ready"})

    assert result == {"action": "ready"}


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
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=3),
    )

    class _DevelopmentRun:
        def provider_projection(self) -> dict[str, Any]:
            return _passing_development_test(None, 1.0, {})

    class _DevelopmentEvaluator:
        def evaluate(self, **_kwargs: Any) -> _DevelopmentRun:
            return _DevelopmentRun()

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
        code_research_limits=CodeResearchLimits(max_turns=3),
        code_development_evaluator=_DevelopmentEvaluator(),
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
        "code_research_turn",
        "code_research_turn",
        "code_research_finalize",
    ]


def test_failed_test_cannot_ready_until_revised_draft_passes() -> None:
    outcomes = iter(("failed", "passed"))

    def test_patch(_patch_value, _remaining, _corpus):
        outcome = next(outcomes)
        return {
            "outcome": outcome,
            "checks": [{"name": "D3_unit_tests", "outcome": outcome}],
            "counts": {"total": 1, "passed": 0, "failed": 1},
        }

    session, client = _run(
        [
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
            {"outcome": "finalize_patch"},
        ],
        limits=CodeResearchLimits(max_turns=6),
    )
    session._test_patch = test_patch

    session.run(_snapshot())

    assert "latest_draft_not_passing" in client.calls[3]["system_text"]


def test_development_projection_drops_host_only_fields() -> None:
    secret = "/host/private/sentinel-token"

    def test_patch(_patch_value, _remaining, _corpus):
        return {
            "outcome": "failed",
            "checks": [{"name": "D3_unit_tests", "outcome": "failed"}],
            "counts": {"total": 1, "passed": 0, "failed": 1},
            "stdout": secret,
            "path": secret,
        }

    session, client = _run(
        [
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "revise", "patch": _patch()},
            {"outcome": "abandon", "reason": "bounded failure"},
        ],
        limits=CodeResearchLimits(max_turns=3),
    )
    session._test_patch = test_patch

    session.run(_snapshot())

    assert secret not in client.calls[2]["system_text"]


@pytest.mark.parametrize(
    "unsafe_check",
    [
        {
            "name": "D4_regression_tests",
            "outcome": "failed",
            "reason_code": "raw_traceback",
        },
        {
            "name": "D4_regression_tests",
            "outcome": "failed",
            "test_path": "/host/private_test.py",
        },
    ],
)
def test_development_projection_rejects_unapproved_diagnostic_values(
    unsafe_check: dict[str, str],
) -> None:
    def test_patch(_patch_value, _remaining, _corpus):
        return {
            "outcome": "failed",
            "checks": [unsafe_check],
            "counts": {"total": 1, "passed": 0, "failed": 1},
        }

    session, _client = _run(
        [
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )
    session._test_patch = test_patch

    with pytest.raises(ProposalValidationError, match="development check"):
        session.run(_snapshot())


def test_global_provider_cap_blocks_test_before_evaluator_dispatch() -> None:
    calls: list[int] = []

    def test_patch(_patch_value, _remaining, _corpus):
        calls.append(1)
        return _passing_development_test(None, 1.0, {})

    session, _client = _run(
        [
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
        ],
        limits=CodeResearchLimits(max_turns=2),
        budget=ProviderCallBudget(1),
    )
    session._test_patch = test_patch

    with pytest.raises(ProviderCallCapExhausted):
        session.run(_snapshot())

    assert calls == []
    assert session.provider_calls_used == 1


def test_test_call_cap_blocks_second_evaluator_dispatch() -> None:
    calls: list[int] = []

    def test_patch(_patch_value, _remaining, _corpus):
        calls.append(1)
        return _passing_development_test(None, 1.0, {})

    session, client = _run(
        [
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "test_patch"},
            {"outcome": "abandon", "reason": "test cap reached"},
        ],
        limits=CodeResearchLimits(max_turns=3, max_test_calls=1),
    )
    session._test_patch = test_patch

    session.run(_snapshot())

    assert calls == [1]
    assert "test_call_cap_exhausted" in client.calls[-1]["system_text"]
