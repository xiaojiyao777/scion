"""Correction feedback and read-only access in the real bounded C loop."""

from __future__ import annotations

import json
from typing import Any

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import PatchProposal
from scion.core.resource_envelope import ProviderCallBudget
from scion.proposal.code_research_session import bind_code_research_turn_tool
from scion.proposal.engine import build_prompt_turn_snapshot
from scion.tests.unit.proposal.test_code_research_session import (
    _SUPPORT_PATH,
    _TARGET_PATH,
    _UNAVAILABLE_PATH,
    _passing_development_test,
    _patch,
    _run,
    _snapshot,
)

_DEPENDENCY_PATH = "models.py"
_DEPENDENCY_SOURCE = "PUBLIC_DEPENDENCY_VALUE = 17\n"


def _dependency_snapshot(*, visible: bool = False, available: bool = True):
    context = _snapshot(include_public_test=True).structured_context
    context["editable_source_context"]["read_only_sources"] = [
        {
            "path": _DEPENDENCY_PATH,
            "content": _DEPENDENCY_SOURCE if available else None,
            "visible": visible,
        }
    ]
    return build_prompt_turn_snapshot("code", context)


def test_empty_search_path_feedback_allows_deliberate_recovery_with_exact_accounting():
    budget = ProviderCallBudget(5)
    session, client = _run(
        [
            {"action": "search_source", "query": "helper", "path": ""},
            {"action": "search_source", "query": "helper"},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
        ],
        limits=CodeResearchLimits(max_turns=5, max_search_calls=1),
        budget=budget,
    )
    session._test_patch = _passing_development_test

    result = session.run(_snapshot())

    assert isinstance(result, PatchProposal)
    assert session._budget.results[0] == {
        "action": "code_research_turn",
        "ok": False,
        "reason": "command_field_invalid",
        "field": "path",
        "correction": "omit_path_or_use_exact_listed_file",
    }
    assert session._budget.results[1]["ok"] is True
    assert session._budget.results[1]["matches"][0]["path"] == _SUPPORT_PATH
    assert session._budget.search_calls == 1  # Rejected schema did not execute a query.
    assert budget.used == session.provider_calls_used == len(client.calls) == 5
    assert all(call["request_kind"] == "code_research_turn" for call in client.calls)
    assert client.responses == []  # No automatic retry or repaired command.


@pytest.mark.parametrize(
    ("command", "field", "correction"),
    [
        ({"action": "read_source", "path": ""}, "path", "use_exact_listed_file"),
        (
            {"action": "search_source", "query": "", "path": "PRIVATE_PATH_SENTINEL"},
            "query",
            "provide_nonempty_literal_query",
        ),
        (
            {"action": "search_source", "query": "x" * 257},
            "query",
            "shorten_literal_query",
        ),
        (
            {"action": "search_source", "query": "x", "path": None},
            "path",
            "omit_path_or_use_exact_listed_file",
        ),
        (
            {"action": "read_source", "path": "x", "PRIVATE_FIELD_SENTINEL": "secret"},
            "command",
            "use_declared_action_fields",
        ),
    ],
)
def test_query_schema_feedback_is_fixed_and_does_not_echo_provider_input(
    command: dict[str, Any], field: str, correction: str
):
    session, client = _run(
        [command, {"outcome": "abandon", "reason": "stop"}],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(_snapshot())

    result = session._budget.results[0]
    assert result["field"] == field
    assert result["correction"] == correction
    assert set(result) == {"action", "ok", "reason", "field", "correction"}
    assert "PRIVATE_PATH_SENTINEL" not in client.calls[1]["system_text"]
    assert "PRIVATE_FIELD_SENTINEL" not in client.calls[1]["system_text"]
    assert session._budget.read_calls == session._budget.search_calls == 0


@pytest.mark.parametrize("action", ["read_source", "search_source"])
def test_unavailable_and_directory_queries_share_safe_feedback_without_filesystem_probe(
    action: str, monkeypatch: pytest.MonkeyPatch
):
    from pathlib import Path

    def forbidden_probe(*_args, **_kwargs):
        raise AssertionError("source research must use only the frozen corpus")

    monkeypatch.setattr(Path, "read_text", forbidden_probe)
    monkeypatch.setattr(Path, "exists", forbidden_probe)
    monkeypatch.setattr(Path, "is_dir", forbidden_probe)
    paths = [_UNAVAILABLE_PATH, "operators", "PRIVATE_PATH_SENTINEL.py"]
    queries = [
        {
            "action": action,
            "path": path,
            **({"query": "x"} if action == "search_source" else {}),
        }
        for path in paths
    ]
    session, client = _run(
        [*queries, {"outcome": "abandon", "reason": "stop"}],
        limits=CodeResearchLimits(max_turns=3),
    )

    session.run(_snapshot())

    results = session._budget.results
    assert results[0] == results[1] == results[2]
    assert results[0]["reason"] == "source_not_visible"
    assert results[0]["field"] == "path"
    assert session._budget.read_calls + session._budget.search_calls == 3
    assert "PRIVATE_PATH_SENTINEL" not in client.calls[-1]["system_text"]


@pytest.mark.parametrize("action", ["read_source", "search_source"])
def test_unsafe_path_feedback_never_echoes_raw_path(action: str):
    command = {"action": action, "path": "../PRIVATE_PATH_SENTINEL"}
    if action == "search_source":
        command["query"] = "x"
    session, client = _run(
        [command, {"outcome": "abandon", "reason": "stop"}],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(_snapshot())

    assert session._budget.results[0]["reason"] == "invalid_path"
    assert "PRIVATE_PATH_SENTINEL" not in client.calls[-1]["system_text"]


@pytest.mark.parametrize("action", ["read_source", "search_source"])
def test_query_correction_does_not_reset_the_action_limit(action: str):
    extra = {"query": "helper"} if action == "search_source" else {}
    session, _client = _run(
        [
            {"action": action, "path": "operators", **extra},
            {"action": action, "path": _SUPPORT_PATH, **extra},
            {"outcome": "abandon", "reason": "limit reached"},
        ],
        limits=CodeResearchLimits(max_turns=2, max_read_calls=1, max_search_calls=1),
    )

    session.run(_snapshot())

    assert session._budget.results[0]["reason"] == "source_not_visible"
    expected = (
        "read_call_cap_exhausted"
        if action == "read_source"
        else "search_call_cap_exhausted"
    )
    assert session._budget.results[1]["reason"] == expected
    assert session._budget.read_calls + session._budget.search_calls == 1
    assert session.provider_calls_used == 3


def test_read_only_dependency_is_queryable_but_never_enters_editable_test_corpus():
    observed_corpora = []

    def test_patch(patch, remaining, corpus, falsifier):
        observed_corpora.append(dict(corpus))
        return _passing_development_test(patch, remaining, corpus, falsifier)

    session, client = _run(
        [
            {
                "action": "search_source",
                "path": _DEPENDENCY_PATH,
                "query": "PUBLIC_DEPENDENCY_VALUE",
            },
            {"action": "read_source", "path": _DEPENDENCY_PATH},
            {"action": "revise", "patch": _patch()},
            {"action": "test_patch"},
            {"action": "ready"},
        ],
        limits=CodeResearchLimits(max_turns=5),
    )
    session._test_patch = test_patch

    result = session.run(_dependency_snapshot())

    assert isinstance(result, PatchProposal)
    assert "PUBLIC_DEPENDENCY_VALUE" not in client.calls[0]["system_text"]
    assert "PUBLIC_DEPENDENCY_VALUE" in client.calls[2]["system_text"]
    assert session._budget.results[0]["matches"][0]["path"] == _DEPENDENCY_PATH
    assert session._budget.results[1]["ok"] is True
    assert len(observed_corpora) == 1
    assert set(observed_corpora[0]) == {_TARGET_PATH, _SUPPORT_PATH}
    assert session._budget.read_calls == session._budget.search_calls == 1


@pytest.mark.parametrize("action", ["read_source", "search_source"])
def test_unavailable_read_only_dependency_does_not_become_an_empty_source(action: str):
    command = {"action": action, "path": _DEPENDENCY_PATH}
    if action == "search_source":
        command["query"] = "PUBLIC_DEPENDENCY_VALUE"
    session, client = _run(
        [command, {"outcome": "abandon", "reason": "unavailable"}],
        limits=CodeResearchLimits(max_turns=1),
    )

    session.run(_dependency_snapshot(available=False))

    assert session._budget.results[0]["reason"] == "source_not_visible"
    assert "PUBLIC_DEPENDENCY_VALUE = 17" not in client.calls[-1]["system_text"]
    assert '"path":"models.py","visible":false' in client.calls[-1]["system_text"]


@pytest.mark.parametrize("action", ["modify", "create", "delete"])
@pytest.mark.parametrize("additional", [False, True])
@pytest.mark.parametrize("available", [False, True])
def test_read_only_dependency_cannot_be_patched_even_if_unavailable(
    action: str, additional: bool, available: bool
):
    readonly_change = {**_patch(), "file_path": _DEPENDENCY_PATH, "action": action}
    patch = (
        {**_patch(), "additional_changes": [readonly_change]}
        if additional
        else readonly_change
    )
    session, _client = _run(
        [
            {"action": "revise", "patch": patch},
            {"action": "ready"},
            {"outcome": "abandon", "reason": "readonly"},
        ],
        limits=CodeResearchLimits(max_turns=2),
    )

    session.run(_dependency_snapshot(visible=available, available=available))

    assert session._budget.results[0]["reason"] == "source_read_only"
    assert session._budget.results[1]["reason"] == "draft_required"
    assert session._test_calls == 0


def test_tool_schema_explains_exact_file_and_omitted_search_path():
    tool = bind_code_research_turn_tool(CodeResearchLimits())
    rendered = json.dumps(tool)
    assert "omit path" in tool["description"]
    assert "not directories" in tool["description"]
    assert "read_only_sources" in tool["description"]
    search = next(
        option
        for option in tool["input_schema"]["oneOf"]
        if option["properties"]["action"]["enum"] == ["search_source"]
    )
    assert search["required"] == ["action", "query"]
    assert search["properties"]["path"]["minLength"] == 1
    assert "Omit this field" in rendered
