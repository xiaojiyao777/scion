"""Typed code-edit protocol normalization tests."""

from __future__ import annotations

import json
import re

import pytest

from scion.core.models import HypothesisProposal, MechanismChange
from scion.contract.gate import ContractGate
from scion.proposal.edit_protocol import (
    PatchEditProtocolError,
    build_patch_edit_source_manifest,
    normalize_patch_typed_edits,
    source_digest_for_content,
)
from scion.proposal.edit_protocol.source_discovery import source_records_from_context
from scion.proposal.agentic_session_repair import (
    _code_edit_protocol_retry_context,
    _is_code_edit_protocol_retryable,
)
from scion.proposal.engine import ProposalValidationError, _parse_patch
from scion.proposal.engine.code_prompts import _split_code_context
from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.proposal.schemas import PATCH_PROPOSAL_SCHEMA
from scion.tests.contract_test_support import make_spec


def test_exact_replace_normalizes_to_content_after_and_patch_content() -> None:
    before = "def value():\n    return 1\n"
    digest = source_digest_for_content(before)
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": digest,
        "old_string": "return 1",
        "new_string": "return 2",
        "replace_all": False,
        "evidence_refs": ["obs-target"],
    }
    context = {
        "target_file": "policies/example.py",
        "target_file_code": before,
    }

    normalized, attribution = normalize_patch_typed_edits(raw, context=context)
    patch = _parse_patch(raw, context=context)

    assert normalized["content_after"] == "def value():\n    return 2\n"
    assert normalized["code_content"] == normalized["content_after"]
    assert patch.code_content == normalized["content_after"]
    assert attribution[0]["edit_intent"] == "exact_replace"
    assert attribution[0]["derived_diff_ref"].startswith("typed-edit-diff:")
    assert attribution[0]["evidence_refs"] == ["obs-target"]


def test_exact_replace_not_unique_reports_candidate_snippets() -> None:
    before = (
        "def first():\n"
        "    return value\n\n"
        "def second():\n"
        "    return value\n"
    )
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(before),
        "old_string": "return value",
        "new_string": "return other",
    }

    with pytest.raises(PatchEditProtocolError) as exc_info:
        normalize_patch_typed_edits(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    payload = json.loads(str(exc_info.value))
    assert payload["reason"] == "old_string_not_unique"
    assert payload["match_count"] == 2
    assert [item["line"] for item in payload["candidate_matches"]] == [2, 5]
    assert "unique_old_string_hint" in payload["candidate_matches"][0]
    assert "replace_all=false unless" in payload["guidance"]


def test_primary_exact_replace_missing_new_string_is_preflight_rejected() -> None:
    before = "def value():\n    return 1\n"
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(before),
        "old_string": "return 1",
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    payload = json.loads(str(excinfo.value))
    assert payload["stage"] == "schema_preflight"
    assert payload["reason"] == "exact_replace_missing_new_string"
    assert payload["json_pointer"] == "/new_string"
    assert payload["minimal_json_shape"]["action"] == "modify"
    assert payload["minimal_json_shape"]["edit_intent"] == "exact_replace"
    assert 'new_string: ""' in payload["guidance"]


def test_direct_normalization_missing_new_string_uses_schema_preflight() -> None:
    before = "def value():\n    return 1\n"
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(before),
        "old_string": "return 1",
    }

    with pytest.raises(PatchEditProtocolError) as excinfo:
        normalize_patch_typed_edits(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    payload = json.loads(str(excinfo.value))
    assert payload["stage"] == "schema_preflight"
    assert payload["reason"] == "exact_replace_missing_new_string"


def test_additional_exact_replace_missing_new_string_reports_pointer() -> None:
    helper_before = "HELPERS = []\n"
    raw = {
        "file_path": "policies/new_helper.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "def helper():\n    return 1\n",
        "full_file_reason": "new helper module",
        "additional_changes": [
            {
                "file_path": "policies/integration.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(helper_before),
                "old_string": "HELPERS = []",
            }
        ],
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            raw,
            context={
                "patch_source_files": {
                    "policies/integration.py": helper_before,
                },
            },
        )

    payload = json.loads(str(excinfo.value))
    assert payload["reason"] == "exact_replace_missing_new_string"
    assert payload["json_pointer"] == "/additional_changes/0/new_string"
    assert payload["change_pointer"] == "/additional_changes/0"


def test_exact_replace_null_new_string_rejected_but_empty_string_allowed() -> None:
    before = "VALUE = 1\nDROP = True\n"
    digest = source_digest_for_content(before)
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": digest,
        "old_string": "DROP = True\n",
        "new_string": None,
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    payload = json.loads(str(excinfo.value))
    assert payload["reason"] == "exact_replace_null_new_string"
    assert "empty string" in payload["detail"]

    raw["new_string"] = ""
    patch = _parse_patch(
        raw,
        context={
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
    )

    assert patch.code_content == "VALUE = 1\n"


def test_old_string_not_unique_feedback_enters_code_retry_prompt() -> None:
    before = (
        "def first():\n"
        "    return value\n\n"
        "def second():\n"
        "    return value\n"
    )
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(before),
        "old_string": "return value",
        "new_string": "return other",
    }
    try:
        _parse_patch(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )
    except ProposalValidationError as exc:
        failure = exc
    else:
        raise AssertionError("expected ProposalValidationError")

    retry_context = _code_edit_protocol_retry_context(
        {
            "problem_summary": "Test problem",
            "research_surface_name": "local",
            "research_surface_kind": "operator",
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
        HypothesisProposal(
            hypothesis_text="Modify one return.",
            change_locus="local",
            action="modify",
            target_file="policies/example.py",
            mechanism_changes=(
                MechanismChange(id="bounded_probe", change_type="modify"),
            ),
        ),
        failure,
    )

    _, user_prompt = _split_code_context(retry_context)
    assert "Typed Edit Retry Feedback" in user_prompt
    assert "old_string_not_unique" in user_prompt
    assert '"match_count": 2' in user_prompt
    assert '"line": 2' in user_prompt
    assert "unique_old_string_hint" in user_prompt


def test_exact_replace_shape_feedback_enters_code_retry_prompt() -> None:
    before = "def value():\n    return 1\n"
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(before),
        "old_string": "return 1",
    }
    try:
        _parse_patch(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )
    except ProposalValidationError as exc:
        failure = exc
    else:
        raise AssertionError("expected ProposalValidationError")

    assert _is_code_edit_protocol_retryable(failure)
    retry_context = _code_edit_protocol_retry_context(
        {
            "problem_summary": "Test problem",
            "research_surface_name": "local",
            "research_surface_kind": "operator",
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
        HypothesisProposal(
            hypothesis_text="Modify one return.",
            change_locus="local",
            action="modify",
            target_file="policies/example.py",
            mechanism_changes=(
                MechanismChange(id="bounded_probe", change_type="modify"),
            ),
        ),
        failure,
    )

    _, user_prompt = _split_code_context(retry_context)
    assert "Typed Edit Retry Feedback" in user_prompt
    assert "exact_replace_missing_new_string" in user_prompt
    assert "minimal_json_shape" in user_prompt
    assert 'new_string: ""' in user_prompt


def test_markdown_wrapped_target_file_code_uses_raw_source_digest() -> None:
    raw_source = "VALUE = 1\n"
    wrapped_source = f"File: policies/example.py\n```python\n{raw_source}```"
    manifest = build_patch_edit_source_manifest(
        {
            "target_file": "policies/example.py",
            "target_file_code": wrapped_source,
        }
    )

    assert source_digest_for_content(raw_source) in manifest
    assert source_digest_for_content(wrapped_source) not in manifest


def test_source_discovery_preserves_agentic_observation_provenance() -> None:
    source = "VALUE = 1\n"
    records = source_records_from_context(
        {
            "agentic_tool_observations": [
                {
                    "tool_name": "context.read_algorithm_file",
                    "is_error": False,
                    "structured_payload": {
                        "file_path": "policies/example.py",
                        "readable": True,
                        "active": True,
                        "truncated": False,
                        "content_preview": source,
                    },
                }
            ]
        }
    )

    record = records["policies/example.py"]
    assert record.content == source
    assert record.digest == source_digest_for_content(source)
    assert record.provenance == "agentic_tool_observations.context.read_algorithm_file"


def test_parse_patch_exact_replace_with_wrapped_target_uses_raw_code() -> None:
    raw_source = "VALUE = 1\n"
    wrapped_source = f"File: policies/example.py\n```python\n{raw_source}```"
    raw_digest = source_digest_for_content(raw_source)

    patch = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": raw_digest,
            "old_string": "VALUE = 1",
            "new_string": "VALUE = 2",
        },
        context={
            "target_file": "policies/example.py",
            "target_file_code": wrapped_source,
        },
    )
    result = ContractGate(
        make_spec(editable=("policies/*.py",), import_whitelist=())
    ).validate_patch(patch)
    c6 = next(check for check in result.checks if check.name == "C6_ast_syntax")

    assert patch.code_content == "VALUE = 2\n"
    assert "```python" not in patch.code_content
    assert c6.passed


def test_wrapped_source_fallbacks_accept_malformed_and_raw_text() -> None:
    raw_source = "VALUE = 1\n"
    raw_digest = source_digest_for_content(raw_source)
    malformed = "File: policies/example.py\n```python\nVALUE = 1\n"

    malformed_manifest = build_patch_edit_source_manifest(
        {
            "target_file": "policies/example.py",
            "target_file_code": malformed,
        }
    )
    raw_manifest = build_patch_edit_source_manifest(
        {
            "target_file": "policies/example.py",
            "target_file_code": raw_source,
        }
    )

    assert raw_digest in malformed_manifest
    assert source_digest_for_content(malformed) not in malformed_manifest
    assert raw_digest in raw_manifest


def test_prompt_manifest_digest_matches_displayed_target_raw_content() -> None:
    raw_source = "VALUE = 1\n"
    wrapped_source = f"File: policies/example.py\n```python\n{raw_source}```"
    _, prompt = _split_code_context(
        {
            "problem_summary": "Example problem",
            "hypothesis_detail": "Change one constant.",
            "target_file": "policies/example.py",
            "target_file_code": wrapped_source,
            "operator_interface_spec": "Expose module constants.",
            "import_whitelist": "- math",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "data/**",
        }
    )
    displayed = re.search(
        r"File: policies/example.py\n```python\n(?P<source>.*?)```",
        prompt,
        re.DOTALL,
    )

    assert displayed is not None
    displayed_source = displayed.group("source")
    assert source_digest_for_content(displayed_source) in prompt
    assert source_digest_for_content(wrapped_source) not in prompt
    assert "hard limit 85% of files over 2000 chars" in prompt
    assert "under 35% of the file" in prompt
    assert "full_file_reason` is not an authorization or replace policy" in prompt
    assert "old_string == new_string" in prompt
    assert "EOF/trailing newline edits" in prompt


def test_exact_replace_rejects_stale_source_digest() -> None:
    before = "VALUE = 1\n"
    stale_digest = source_digest_for_content("VALUE = 0\n")

    with pytest.raises(ProposalValidationError, match="stale_source"):
        _parse_patch(
            {
                "file_path": "policies/example.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": stale_digest,
                "old_string": "VALUE = 1",
                "new_string": "VALUE = 2",
            },
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )


@pytest.mark.parametrize(
    "typed_payload",
    [
        {
            "edit_intent": "full_file",
            "content_after": "VALUE = 2\n",
        },
        {
            "content_after": "VALUE = 2\n",
        },
        {
            "code_content": "VALUE = 2\n",
        },
    ],
    ids=["explicit-full-file", "implicit-content-after", "legacy-code-content"],
)
def test_existing_modify_full_file_content_after_is_rejected_with_guidance(
    typed_payload: dict[str, str],
) -> None:
    before = "VALUE = 1\n"
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "full_file_reason": "rewrite is simpler",
        **typed_payload,
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    message = str(excinfo.value)
    assert "existing_file_full_file_modify_rejected" in message
    assert "exact_replace" in message
    assert "old_string" in message
    assert "new_string" in message
    assert source_digest_for_content(before) in message
    assert "full_file_reason is not an authorization" in message
    assert _is_code_edit_protocol_retryable(excinfo.value)


def test_existing_modify_whole_file_exact_replace_is_rejected_with_guidance() -> None:
    before = "VALUE = 1\nLIMIT = 3\n"

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            {
                "file_path": "policies/example.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(before),
                "old_string": before,
                "new_string": "VALUE = 2\nLIMIT = 4\n",
            },
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    message = str(excinfo.value)
    assert "existing_file_whole_file_exact_replace_rejected" in message
    assert "smaller exact_replace edits" in message
    assert "function, import block, registration entry, or local code block" in message


def test_existing_modify_near_whole_file_exact_replace_is_rejected() -> None:
    head = "def target():\n"
    body = "".join(f"    value_{idx} = {idx}\n" for idx in range(180))
    tail = "def untouched():\n    return 1\n"
    before = head + body + tail
    old_string = head + body

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            {
                "file_path": "policies/example.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(before),
                "old_string": old_string,
                "new_string": head + "    return 2\n",
            },
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    message = str(excinfo.value)
    assert "existing_file_near_whole_file_exact_replace_rejected" in message
    assert "coverage_ratio" in message
    assert "old_string_chars" in message
    assert "file_chars" in message
    assert "source_digest" in message
    assert "create a helper file and add a small integration edit" in message
    assert _is_code_edit_protocol_retryable(excinfo.value)

    retry_context = _code_edit_protocol_retry_context(
        {
            "problem_summary": "Test problem",
            "research_surface_name": "local",
            "research_surface_kind": "operator",
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
        HypothesisProposal(
            hypothesis_text="Modify a large file.",
            change_locus="local",
            action="modify",
            target_file="policies/example.py",
            mechanism_changes=(
                MechanismChange(id="bounded_probe", change_type="modify"),
            ),
        ),
        excinfo.value,
    )
    _, user_prompt = _split_code_context(retry_context)
    feedback = retry_context["agentic_code_edit_retry_feedback"]
    assert feedback["reason"] == "existing_file_near_whole_file_exact_replace_rejected"
    assert feedback["coverage_ratio"] > 0.85
    assert feedback["old_string_chars"] == len(old_string)
    assert feedback["file_chars"] == len(before)
    assert feedback["source_digest"] == source_digest_for_content(before)
    assert "Split the change into smaller exact_replace edits" in user_prompt
    assert "coverage_ratio" in user_prompt
    assert "old_string_chars" in user_prompt
    assert "file_chars" in user_prompt
    assert "function/block-level exact_replace edits" in user_prompt


def test_existing_modify_block_exact_replace_in_large_file_is_allowed() -> None:
    before = (
        "def prefix():\n    return 0\n\n"
        + "# filler\n" * 400
        + "def target():\n    return 1\n"
    )
    patch = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(before),
            "old_string": "def target():\n    return 1",
            "new_string": "def target():\n    return 2",
        },
        context={
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
    )

    assert "def target():\n    return 2\n" in patch.code_content


def test_existing_modify_large_fraction_small_file_exact_replace_is_allowed() -> None:
    before = "def value():\n    return 1\n"
    patch = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "source_digest": source_digest_for_content(before),
            "old_string": "def value():\n    return 1",
            "new_string": "def value():\n    return 2",
        },
        context={
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
    )

    assert patch.code_content == "def value():\n    return 2\n"


def test_create_new_file_full_file_content_after_remains_allowed() -> None:
    patch = _parse_patch(
        {
            "file_path": "policies/new_helper.py",
            "action": "create",
            "edit_intent": "full_file",
            "source_digest": None,
            "content_after": "VALUE = 2\n",
            "full_file_reason": "new helper module",
        },
        context={
            "patch_source_files": {
                "policies/example.py": "VALUE = 1\n",
            },
        },
    )

    assert patch.file_path == "policies/new_helper.py"
    assert patch.action == "create"
    assert patch.code_content == "VALUE = 2\n"


@pytest.mark.parametrize(
    "action",
    ["create", "create_new", "full_file"],
)
def test_existing_file_create_actions_are_rejected_with_typed_edit_guidance(
    action: str,
) -> None:
    before = "VALUE = 1\n"

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            {
                "file_path": "policies/example.py",
                "action": action,
                "edit_intent": "full_file",
                "source_digest": None,
                "content_after": "VALUE = 2\n",
                "full_file_reason": "replace existing file",
            },
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    message = str(excinfo.value)
    assert "existing_file_create_rejected" in message
    assert "existing file requires modify exact_replace with source_digest" in message
    assert "create is only for new files" in message
    assert source_digest_for_content(before) in message
    assert _is_code_edit_protocol_retryable(excinfo.value)

    retry_context = _code_edit_protocol_retry_context(
        {
            "problem_summary": "Test problem",
            "research_surface_name": "local",
            "research_surface_kind": "operator",
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
        HypothesisProposal(
            hypothesis_text="Modify existing file.",
            change_locus="local",
            action="create_new",
            target_file="policies/example.py",
            mechanism_changes=(
                MechanismChange(id="bounded_probe", change_type="add"),
            ),
        ),
        excinfo.value,
    )
    _, user_prompt = _split_code_context(retry_context)
    assert "Typed Edit Retry Feedback" in user_prompt
    assert "existing_file_create_rejected" in user_prompt
    assert "existing file requires modify exact_replace with source_digest" in user_prompt
    assert "create is only for new files" in user_prompt


def test_additional_changes_reject_existing_file_create() -> None:
    target_before = "def solve():\n    return helper()\n"
    integration_before = "ENABLED = False\n"

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            {
                "file_path": "policies/new_helper.py",
                "action": "create",
                "edit_intent": "full_file",
                "source_digest": None,
                "content_after": "def helper():\n    return 1\n",
                "full_file_reason": "new helper module",
                "additional_changes": [
                    {
                        "file_path": "policies/integration.py",
                        "action": "create",
                        "edit_intent": "full_file",
                        "source_digest": None,
                        "content_after": "ENABLED = True\n",
                        "full_file_reason": "wire helper",
                    }
                ],
            },
            context={
                "patch_source_files": {
                    "policies/main.py": target_before,
                    "policies/integration.py": integration_before,
                },
            },
        )

    message = str(excinfo.value)
    assert "existing_file_create_rejected" in message
    assert "/additional_changes/0" in message
    assert "policies/integration.py" in message
    assert "exact_replace" in message


def test_new_module_create_with_existing_integration_exact_replace_is_allowed() -> None:
    integration_before = "HELPERS = []\n"
    patch = _parse_patch(
        {
            "file_path": "policies/new_helper.py",
            "action": "create",
            "edit_intent": "full_file",
            "source_digest": None,
            "content_after": "def helper():\n    return 1\n",
            "full_file_reason": "new helper module",
            "additional_changes": [
                {
                    "file_path": "policies/integration.py",
                    "action": "modify",
                    "edit_intent": "exact_replace",
                    "source_digest": source_digest_for_content(integration_before),
                    "old_string": "HELPERS = []",
                    "new_string": "HELPERS = ['new_helper']",
                }
            ],
        },
        context={
            "patch_source_files": {
                "policies/integration.py": integration_before,
            },
        },
    )

    assert patch.action == "create"
    assert patch.code_content == "def helper():\n    return 1\n"
    assert patch.additional_changes[0].action == "modify"
    assert patch.additional_changes[0].code_content == "HELPERS = ['new_helper']\n"


def test_additional_changes_accept_typed_exact_replace() -> None:
    main_before = "def solve():\n    return None\n"
    helper_before = "def helper():\n    return 'old'\n"
    raw = {
        "file_path": "policies/main.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(main_before),
        "old_string": "return None",
        "new_string": "return helper()",
        "additional_changes": [
            {
                "file_path": "policies/helper.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(helper_before),
                "old_string": "return 'old'",
                "new_string": "return 'new'",
            }
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "target_file": "policies/main.py",
            "target_file_code": main_before,
            "patch_source_files": {"policies/helper.py": helper_before},
        },
    )

    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].code_content == (
        "def helper():\n    return 'new'\n"
    )
    assert any(
        item.get("json_pointer") == "/additional_changes/0"
        and item.get("edit_intent") == "exact_replace"
        for item in patch.repair_attribution
    )


def test_contradicted_patch_normalizes_typed_additional_changes_before_schema() -> None:
    helper_before = "def helper():\n    return 'old'\n"
    raw = {
        "premise_check": "contradicted",
        "premise_check_reason": (
            "hard boundary: the approved premise is unsupported by visible facts"
        ),
        "file_path": "policies/main.py",
        "action": "modify",
        "additional_changes": [
            {
                "file_path": "policies/helper.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(helper_before),
                "old_string": "return 'old'",
                "new_string": "return 'new'",
            }
        ],
    }

    normalized, attribution = normalize_patch_typed_edits(
        raw,
        context={
            "patch_source_files": {"policies/helper.py": helper_before},
        },
    )
    patch = _parse_patch(
        raw,
        context={
            "patch_source_files": {"policies/helper.py": helper_before},
        },
    )

    assert normalized["premise_check"] == "contradicted"
    assert normalized["additional_changes"][0]["code_content"] == (
        "def helper():\n    return 'new'\n"
    )
    assert patch.premise_check == "contradicted"
    assert "hard boundary" in patch.premise_check_reason
    assert patch.additional_changes[0].code_content == (
        "def helper():\n    return 'new'\n"
    )
    assert any(
        item.get("json_pointer") == "/additional_changes/0"
        and item.get("repair_kind") == "typed_edit_normalization"
        for item in attribution
    )
    assert any(
        item.get("json_pointer") == "/additional_changes/0"
        and item.get("repair_kind") == "typed_edit_normalization"
        for item in patch.repair_attribution
    )


def test_unsupported_premise_only_patch_remains_diagnostic_without_full_file_error() -> None:
    raw = {
        "premise_check": "duplicate",
        "premise_check_reason": "visible facts already contain this mechanism",
        "file_path": "",
        "action": "modify",
        "code_content": "",
    }

    normalized, attribution = normalize_patch_typed_edits(raw, context={})
    patch = _parse_patch(raw, context={})

    assert normalized == raw
    assert attribution == ()
    assert patch.premise_check == "duplicate"
    assert patch.premise_check_reason == (
        "visible facts already contain this mechanism"
    )
    assert patch.file_path == ""
    assert patch.code_content == ""


def test_additional_exact_replace_uses_full_algorithm_read_source() -> None:
    local_path = "policies/baseline_modules/local_search.py"
    local_source = "LOCAL_SEARCH_OPS = []\n"
    local_digest = source_digest_for_content(local_source)
    short_digest = "d10534349d46680b"
    raw = {
        "file_path": "policies/baseline_modules/new_helper.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "def helper():\n    return 1\n",
        "full_file_reason": "new helper module",
        "additional_changes": [
            {
                "file_path": local_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": local_digest,
                "old_string": "LOCAL_SEARCH_OPS = []",
                "new_string": "LOCAL_SEARCH_OPS = ['compact_absorption']",
            }
        ],
    }
    context = {
        "solver_design_full_algorithm_file_reads": [
            {
                "file_path": local_path,
                "readable": True,
                "active": True,
                "truncated": False,
                "size_chars": len(local_source),
                "max_chars": len(local_source),
                "digest": short_digest,
                "content_preview": local_source,
            }
        ],
        "editable_patterns": "policies/**/*.py",
        "frozen_patterns": "data/**",
    }

    patch = _parse_patch(raw, context=context)
    manifest = build_patch_edit_source_manifest(context)

    assert patch.additional_changes[0].code_content == (
        "LOCAL_SEARCH_OPS = ['compact_absorption']\n"
    )
    attribution = next(
        item
        for item in patch.repair_attribution
        if item.get("json_pointer") == "/additional_changes/0"
    )
    assert attribution["source_provenance"] == "solver_design_full_algorithm_file_reads"
    assert attribution["source_record_digest"] == local_digest
    assert f"source_digest={local_digest}" in manifest
    assert short_digest not in manifest


def test_additional_exact_replace_uses_required_full_integration_source() -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    scheduler_source = "SCHEDULED = []\n"
    scheduler_digest = source_digest_for_content(scheduler_source)
    required_section = (
        f"### {scheduler_path}\n"
        "Provenance: retry required full source\n"
        f"```python\n{scheduler_source}```"
    )
    raw = {
        "file_path": "policies/baseline_modules/new_helper.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "def helper():\n    return 1\n",
        "full_file_reason": "new helper module",
        "additional_changes": [
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": scheduler_digest,
                "old_string": "SCHEDULED = []",
                "new_string": "SCHEDULED = ['new_helper']",
            }
        ],
    }

    patch = _parse_patch(
        raw,
        context={"agentic_required_full_integration_files": required_section},
    )

    assert patch.additional_changes[0].code_content == (
        "SCHEDULED = ['new_helper']\n"
    )
    attribution = next(
        item
        for item in patch.repair_attribution
        if item.get("json_pointer") == "/additional_changes/0"
    )
    assert attribution["source_provenance"] == "agentic_required_full_integration_files"
    assert attribution["source_record_digest"] == scheduler_digest


def test_unreadable_branch_current_integration_placeholder_is_not_edit_source() -> None:
    helper_path = "policies/baseline_modules/helper.py"
    missing_section = (
        f"### {helper_path}\n"
        "Provenance: missing_current_source; readable=False; "
        "source_status=missing_current_source; visibility=not_visible\n"
        "```python\n# could not read policies/baseline_modules/helper.py\n```"
    )
    placeholder_source = "# could not read policies/baseline_modules/helper.py\n"
    raw = {
        "file_path": helper_path,
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(placeholder_source),
        "old_string": "# could not read",
        "new_string": "def helper():\n    return 1",
    }

    with pytest.raises(PatchEditProtocolError) as exc_info:
        normalize_patch_typed_edits(
            raw,
            context={
                "solver_design_branch_current_integration_files": missing_section,
            },
        )

    assert "exact_replace source unavailable" in str(exc_info.value)
    manifest = build_patch_edit_source_manifest(
        {"solver_design_branch_current_integration_files": missing_section}
    )
    assert helper_path not in manifest


def test_additional_exact_replace_uses_editable_branch_workspace_fallback(
    tmp_path,
) -> None:
    local_path = "policies/baseline_modules/local_search.py"
    local_source = "LOCAL_SEARCH_OPS = []\n"
    workspace = tmp_path / "branch"
    file_path = workspace / local_path
    file_path.parent.mkdir(parents=True)
    file_path.write_text(local_source, encoding="utf-8")
    raw = {
        "file_path": "policies/baseline_modules/new_helper.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "def helper():\n    return 1\n",
        "full_file_reason": "new helper module",
        "additional_changes": [
            {
                "file_path": local_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(local_source),
                "old_string": "LOCAL_SEARCH_OPS = []",
                "new_string": "LOCAL_SEARCH_OPS = ['workspace_fallback']",
            }
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "branch_workspace": str(workspace),
            "editable_patterns": "policies/**/*.py",
            "frozen_patterns": "data/**",
        },
    )

    assert patch.additional_changes[0].code_content == (
        "LOCAL_SEARCH_OPS = ['workspace_fallback']\n"
    )
    attribution = next(
        item
        for item in patch.repair_attribution
        if item.get("json_pointer") == "/additional_changes/0"
    )
    assert attribution["source_provenance"] == "branch_workspace_fallback"
    assert attribution["source_record_digest"] == source_digest_for_content(
        local_source
    )


def test_code_prompt_uses_source_digest_hash_for_short_full_read_digest() -> None:
    source = "LOCAL_SEARCH_OPS = []\n"
    full_digest = source_digest_for_content(source)
    short_digest = "d10534349d46680b"
    context = {
        "problem_summary": "Example problem",
        "research_surface_name": "solver_design",
        "research_surface_kind": "solver_design",
        "hypothesis_detail": "Wire a variant.",
        "target_file": "policies/baseline_modules/new_helper.py",
        "target_file_code": "(new file — will be created)",
        "operator_interface_spec": "solver design",
        "import_whitelist": "- math",
        "editable_patterns": "policies/**/*.py",
        "frozen_patterns": "data/**",
        "agentic_tool_observations": [
            {
                "observation_id": "obs-local-search",
                "tool_name": "context.read_algorithm_file",
                "digest": short_digest,
                "structured_payload": {
                    "file_path": "policies/baseline_modules/local_search.py",
                    "readable": True,
                    "active": True,
                    "truncated": False,
                    "size_chars": len(source),
                    "max_chars": len(source),
                    "digest": short_digest,
                    "content_preview": source,
                },
            }
        ],
    }

    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n\n".join(
        str(block.get("text", "")) for block in system_blocks
    ) + user_prompt
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

    assert full_digest in rendered
    assert "source_digest_hash" in rendered
    assert f'"source_digest": "{short_digest}"' not in rendered
    assert f"source_digest={full_digest}" in rendered
    ledger_records = manifest["code_file_visibility_ledger"]["algorithm_file_reads"]
    assert (
        ledger_records[0]["file_path"]
        == "policies/baseline_modules/local_search.py"
    )
    assert ledger_records[0]["full_content_visible_in_rendered_prompt"] is True


def test_duplicate_additional_exact_replace_changes_are_composed() -> None:
    scheduler_before = "def schedule():\n    window = 4\n    penalty = 1\n"
    scheduler_path = "policies/baseline_modules/scheduler.py"
    digest = source_digest_for_content(scheduler_before)
    raw = {
        "file_path": "policies/main.py",
        "action": "modify",
        "code_content": "def solve():\n    return None\n",
        "additional_changes": [
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "window = 4",
                "new_string": "window = 5",
                "evidence_refs": ["scheduler-window"],
            },
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "penalty = 1",
                "new_string": "penalty = 2",
                "evidence_refs": ["scheduler-penalty"],
            },
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "patch_source_files": {scheduler_path: scheduler_before},
            "allow_host_internal_full_file_modify": True,
        },
    )

    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].file_path == scheduler_path
    assert patch.additional_changes[0].code_content == (
        "def schedule():\n    window = 5\n    penalty = 2\n"
    )
    assert any(
        item.get("repair_kind") == "patch_set_composition"
        and item.get("file_path") == scheduler_path
        and item.get("source_json_pointers")
        == ["/additional_changes/0", "/additional_changes/1"]
        for item in patch.repair_attribution
    )


def test_not_serializable_exact_replace_enters_code_retry_feedback() -> None:
    before = "def target():\n    value = 1\n\ndef other():\n    value = 1\n"
    digest = source_digest_for_content(before)
    raw = {
        "file_path": "policies/example.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": digest,
        "old_string": "def target():\n    value = 1\n",
        "new_string": "def target():\n    value = 2\n",
        "additional_changes": [
            {
                "file_path": "policies/example.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": before,
                "new_string": before.replace("value = 1", "value = 3", 1),
            }
        ],
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(
            raw,
            context={
                "target_file": "policies/example.py",
                "target_file_code": before,
            },
        )

    message = str(excinfo.value)
    assert "exact_replace_not_serializable" in message
    assert "prior_json_pointers" in message
    assert "no-op exact_replace" in message
    assert _is_code_edit_protocol_retryable(excinfo.value)

    retry_context = _code_edit_protocol_retry_context(
        {
            "problem_summary": "Test problem",
            "research_surface_name": "local",
            "research_surface_kind": "operator",
            "target_file": "policies/example.py",
            "target_file_code": before,
        },
        HypothesisProposal(
            hypothesis_text="Modify same file twice.",
            change_locus="local",
            action="modify",
            target_file="policies/example.py",
            mechanism_changes=(
                MechanismChange(id="bounded_probe", change_type="modify"),
            ),
        ),
        excinfo.value,
    )
    _, user_prompt = _split_code_context(retry_context)
    feedback = retry_context["agentic_code_edit_retry_feedback"]
    assert feedback["reason"] == "exact_replace_not_serializable"
    assert feedback["json_pointer"] == "/additional_changes/0"
    assert feedback["prior_json_pointers"] == ["/"]
    assert "single blocker" in feedback["current_blocker_only"]
    assert "one change per file" in feedback["same_file_retry_policy"]
    assert "Use one file change for this file" in user_prompt
    assert "the retry must use one change per file" in user_prompt
    assert "old_string == new_string" in user_prompt
    assert "no-op EOF/trailing newline" in user_prompt
    assert "C8_import_whitelist" not in user_prompt


def test_noop_eof_exact_replace_additional_change_is_dropped_with_audit() -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    scheduler_before = "A = 1\nB = 1"
    digest = source_digest_for_content(scheduler_before)
    raw = {
        "file_path": "policies/baseline_modules/new_helper.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "def helper():\n    return 1\n",
        "full_file_reason": "new helper module",
        "additional_changes": [
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "A = 1",
                "new_string": "A = 2",
            },
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "B = 1\n",
                "new_string": "B = 1",
            },
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "B = 1",
                "new_string": "B = 1",
            },
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "patch_source_files": {
                scheduler_path: scheduler_before,
            },
        },
    )

    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].file_path == scheduler_path
    assert patch.additional_changes[0].code_content == "A = 2\nB = 1"
    noop_audits = [
        item
        for item in patch.repair_attribution
        if item.get("repair_kind") == "typed_edit_noop_dropped"
    ]
    assert [item["json_pointer"] for item in noop_audits] == [
        "/additional_changes/1",
        "/additional_changes/2",
    ]
    assert {item["noop_kind"] for item in noop_audits} == {
        "identical_old_and_new",
        "trailing_whitespace_only",
    }
    assert all(item["reason"] == "exact_replace_noop" for item in noop_audits)
    assert all(item["source_digest"] == digest for item in noop_audits)
    assert all(
        "EOF/trailing-whitespace-only edits" in item["guidance"]
        for item in noop_audits
    )


def test_eof_newline_exact_replace_selector_drift_is_tolerated_with_audit() -> None:
    scheduler_path = "policies/baseline_modules/scheduler.py"
    scheduler_before = "A = 1\nB = 1"
    digest = source_digest_for_content(scheduler_before)
    raw = {
        "file_path": "policies/baseline_modules/new_helper.py",
        "action": "create",
        "edit_intent": "full_file",
        "source_digest": None,
        "content_after": "def helper():\n    return 1\n",
        "full_file_reason": "new helper module",
        "additional_changes": [
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "A = 1",
                "new_string": "A = 2",
            },
            {
                "file_path": scheduler_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "B = 1\n",
                "new_string": "B = 2\n",
            },
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "patch_source_files": {
                scheduler_path: scheduler_before,
            },
        },
    )

    assert len(patch.additional_changes) == 1
    assert patch.additional_changes[0].file_path == scheduler_path
    assert patch.additional_changes[0].code_content == "A = 2\nB = 2"
    eof_repairs = [
        item
        for item in patch.repair_attribution
        if item.get("selector_repair") == "eof_final_newline_tolerated"
    ]
    assert [item["json_pointer"] for item in eof_repairs] == [
        "/additional_changes/1"
    ]
    assert eof_repairs[0]["eof_final_newline_tolerated"] is True
    assert eof_repairs[0]["source_digest"] == digest


def test_duplicate_full_file_conflict_is_rejected_before_schema_loop() -> None:
    helper_path = "policies/baseline_modules/helper.py"
    raw = {
        "file_path": "policies/main.py",
        "action": "modify",
        "code_content": "def solve():\n    return None\n",
        "additional_changes": [
            {
                "file_path": helper_path,
                "action": "modify",
                "edit_intent": "full_file",
                "content_after": "VALUE = 1\n",
            },
            {
                "file_path": helper_path,
                "action": "modify",
                "edit_intent": "full_file",
                "content_after": "VALUE = 2\n",
            },
        ],
    }

    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(raw, context={"allow_host_internal_full_file_modify": True})

    message = str(excinfo.value)
    assert "patch_edit_protocol" in message
    assert "full_file_conflict" in message
    assert "/additional_changes/1" in message
    assert "additional_changes must not repeat file_path" not in message


def test_primary_and_additional_same_file_exact_replace_are_composed() -> None:
    target_before = "VALUE = 1\nLIMIT = 3\n"
    digest = source_digest_for_content(target_before)
    target_path = "policies/baseline_modules/scheduler.py"
    raw = {
        "file_path": target_path,
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": digest,
        "old_string": "VALUE = 1",
        "new_string": "VALUE = 2",
        "additional_changes": [
            {
                "file_path": target_path,
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": digest,
                "old_string": "LIMIT = 3",
                "new_string": "LIMIT = 4",
            }
        ],
    }

    patch = _parse_patch(
        raw,
        context={
            "target_file": target_path,
            "target_file_code": target_before,
        },
    )

    assert patch.file_path == target_path
    assert patch.additional_changes == ()
    assert patch.code_content == "VALUE = 2\nLIMIT = 4\n"
    assert any(
        item.get("repair_kind") == "patch_set_composition"
        and item.get("canonical_json_pointer") == "/"
        and item.get("source_json_pointers") == ["/", "/additional_changes/0"]
        for item in patch.repair_attribution
    )


@pytest.mark.parametrize(
    "raw",
    [
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "code_content": "VALUE = 3\n",
        },
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "full_file",
            "content_after": "VALUE = 4\n",
        },
    ],
    ids=["legacy-code-content", "typed-full-file"],
)
def test_no_source_full_file_modify_is_rejected(raw: dict[str, str]) -> None:
    with pytest.raises(ProposalValidationError) as excinfo:
        _parse_patch(raw)

    message = str(excinfo.value)
    assert "existing_file_full_file_modify_source_required" in message
    assert "exact_replace" in message
    assert "source_digest" in message


def test_host_internal_full_file_modify_compatibility_requires_flag() -> None:
    legacy = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "code_content": "VALUE = 3\n",
        },
        context={"allow_host_internal_full_file_modify": True},
    )
    typed = _parse_patch(
        {
            "file_path": "policies/example.py",
            "action": "modify",
            "edit_intent": "full_file",
            "content_after": "VALUE = 4\n",
        },
        context={"allow_host_internal_full_file_modify": True},
    )

    assert legacy.code_content == "VALUE = 3\n"
    assert legacy.repair_attribution == ()
    assert typed.code_content == "VALUE = 4\n"


def test_rendered_code_prompt_prefers_typed_edits_not_mandatory_full_file() -> None:
    _, prompt = _split_code_context(
        {
            "problem_summary": "Example problem",
            "hypothesis_detail": "Change one constant.",
            "target_file": "policies/example.py",
            "target_file_code": "VALUE = 1\n",
            "operator_interface_spec": "Expose module constants.",
            "import_whitelist": "- math",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "data/**",
        }
    )

    assert "default to `edit_intent: exact_replace`" in prompt
    assert "Do not emit unified diffs" in prompt
    assert '"code_content": "<complete file contents>"' not in prompt
    assert "code_content" not in prompt or "Legacy `code_content`" in prompt


def test_previous_patch_retry_context_omits_full_file_bodies() -> None:
    previous_body = (
        "def apply(context):\n"
        "    context.record_iteration('mechanism_x', 1)\n"
        + "    value += 1\n" * 1400
    )
    old_text = "def apply(context):\n    return 1\n" + "# old\n" * 300
    new_text = (
        "def apply(context):\n"
        "    context.record_iteration('mechanism_x', 1)\n"
        "    return 2\n"
        + "# new\n" * 300
    )

    _, prompt = _split_code_context(
        {
            "problem_summary": "Example problem",
            "hypothesis_detail": "Repair telemetry.",
            "target_file": "policies/example.py",
            "target_file_code": "def apply(context):\n    return 1\n",
            "operator_interface_spec": "Expose apply(context).",
            "import_whitelist": "- math",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "data/**",
            "prior_code_failure": "algorithm smoke telemetry failure",
            "previous_patch": {
                "file_path": "policies/example.py",
                "action": "modify",
                "edit_intent": "exact_replace",
                "source_digest": source_digest_for_content(
                    "def apply(context):\n    return 1\n"
                ),
                "old_string": old_text,
                "new_string": new_text,
                "content_after": previous_body,
                "code_content": previous_body,
                "derived_diff_ref": "typed-edit-diff:abc123",
                "additional_changes": [
                    {
                        "file_path": "policies/helper.py",
                        "action": "modify",
                        "edit_intent": "full_file",
                        "content_after": "VALUE = 1\n" * 2000,
                        "full_file_reason": "helper module rewrite",
                    }
                ],
            },
        }
    )
    previous_section = prompt.split("## Hypothesis to Implement", maxsplit=1)[0]

    assert "Previous Patch Attempt" in previous_section
    assert '"code_content"' not in previous_section
    assert '"content_after"' not in previous_section
    assert "    value += 1\n" * 20 not in previous_section
    assert "legacy_full_file_sha256" in previous_section
    assert "result_content_sha256" in previous_section
    assert "old_string_snippet" in previous_section
    assert "new_string_snippet" in previous_section
    assert "typed-edit-diff:abc123" in previous_section
    assert "context.record_iteration('mechanism_x', ...)" in previous_section
    assert len(previous_section) < 8000


def test_patch_schema_keeps_legacy_code_content_supported_without_encouraging_it() -> None:
    properties = PATCH_PROPOSAL_SCHEMA["properties"]

    assert "code_content" in properties
    assert "full_file_reason" in properties
    code_content_description = properties["code_content"]["description"].lower()
    assert "compatibility" in code_content_description
    assert "exact_replace" in code_content_description

    _, prompt = _split_code_context(
        {
            "problem_summary": "Example problem",
            "hypothesis_detail": "Change one constant.",
            "target_file": "policies/example.py",
            "target_file_code": "VALUE = 1\n",
            "operator_interface_spec": "Expose module constants.",
            "import_whitelist": "- math",
            "editable_patterns": "policies/*.py",
            "frozen_patterns": "data/**",
        }
    )

    assert '"code_content":' not in prompt
    assert "rejected for model-facing existing-file modifies" in prompt
    assert '"full_file_reason"' in prompt
