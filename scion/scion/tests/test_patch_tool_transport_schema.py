"""Provider-free regressions for the C edit schema sent over OpenAI transport."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scion.proposal.llm_client import LLMClient
from scion.proposal.schemas import PATCH_TOOL, PatchProposalInput
from scion.proposal.schemas.patch import EXACT_LINE_REPLACE_EXAMPLE

_LOCALIZED_REQUIRED = {
    "edit_intent",
    "old_string",
    "new_string",
}
_OPENAI_TOOL_SNAPSHOT = (
    Path(__file__).resolve().parent / "fixtures" / "patch_tool_openai_payload.json"
)


def _intent_branches(schema: dict) -> list[dict]:
    conditional = schema["allOf"]
    assert len(conditional) == 1
    assert conditional[0]["if"] == {"required": ["edit_intent"]}
    return conditional[0]["then"]["oneOf"]


def _intent_branch(schema: dict, edit_intent: str, action: str = "modify") -> dict:
    return next(
        branch
        for branch in _intent_branches(schema)
        if branch["properties"]["edit_intent"]["enum"] == [edit_intent]
        and (action in branch["properties"]["action"]["enum"])
    )


def test_patch_schema_discriminates_local_edits_at_root_and_nested_levels() -> None:
    root = PATCH_TOOL["input_schema"]
    nested = root["properties"]["additional_changes"]["items"]

    assert root["required"] == ["file_path", "action"]
    assert nested["required"] == ["file_path", "action"]
    assert "additional_changes" not in root["required"]
    assert "additional_changes" not in nested["properties"]

    common_root_properties = {
        key: value
        for key, value in root["properties"].items()
        if key != "additional_changes"
    }
    assert nested["properties"] == common_root_properties

    for schema in (root, nested):
        assert len(_intent_branches(schema)) == 4
        exact = _intent_branch(schema, "exact_replace")
        exact_line = _intent_branch(schema, "exact_line_replace")
        assert set(exact["required"]) == _LOCALIZED_REQUIRED
        assert set(exact_line["required"]) == _LOCALIZED_REQUIRED
        assert exact_line["examples"] == [EXACT_LINE_REPLACE_EXAMPLE]
        assert "illustrates only the JSON shape" in exact_line["description"]
        assert "does not require this edit intent" in exact_line["description"]
        assert _intent_branch(schema, "full_file", "create")["required"] == [
            "edit_intent",
            "content_after",
        ]
        assert _intent_branch(schema, "full_file", "delete")["required"] == [
            "edit_intent"
        ]


def test_patch_schema_keeps_legacy_flat_pydantic_shapes_compatible() -> None:
    exact = PatchProposalInput.model_validate(
        {
            "file_path": "module.py",
            "action": "modify",
            "edit_intent": "exact_replace",
            "old_string": "before",
            "new_string": "after",
            "code_content": "after",
        }
    )
    created = PatchProposalInput.model_validate(
        {
            "file_path": "new_module.py",
            "action": "create",
            "edit_intent": "full_file",
            "content_after": "VALUE = 1\n",
        }
    )
    deleted = PatchProposalInput.model_validate(
        {
            "file_path": "obsolete.py",
            "action": "delete",
        }
    )

    assert exact.replace_all is False
    assert created.code_content == "VALUE = 1\n"
    assert deleted.edit_intent is None


def test_openai_transport_sends_complete_patch_schema_without_projection() -> None:
    client = LLMClient(model="gpt-5.6-terra", timeout_sec=60)
    response = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name=PATCH_TOOL["name"],
                                arguments=json.dumps(
                                    {
                                        "file_path": "obsolete.py",
                                        "action": "delete",
                                    }
                                ),
                            )
                        )
                    ]
                ),
            )
        ],
    )
    fake_openai_client = MagicMock()
    fake_openai_client.chat.completions.create.return_value = response

    with patch.object(
        client,
        "_get_openai_client",
        return_value=fake_openai_client,
    ):
        result = client.call_with_tool(
            "provider-free transport capture",
            PATCH_TOOL,
            request_kind="code",
        )

    assert result == {"file_path": "obsolete.py", "action": "delete"}
    assert fake_openai_client.chat.completions.create.call_count == 1
    request = fake_openai_client.chat.completions.create.call_args.kwargs
    expected_function = {
        "name": PATCH_TOOL["name"],
        "description": PATCH_TOOL["description"],
        "parameters": PATCH_TOOL["input_schema"],
    }
    assert request["tools"] == [{"type": "function", "function": expected_function}]
    assert request["tools"][0] == json.loads(
        _OPENAI_TOOL_SNAPSHOT.read_text(encoding="utf-8")
    )
    assert request["tool_choice"] == {
        "type": "function",
        "function": {"name": PATCH_TOOL["name"]},
    }
    assert "strict" not in request["tools"][0]["function"]

    transported = request["tools"][0]["function"]["parameters"]
    transported_nested = transported["properties"]["additional_changes"]["items"]
    for schema in (transported, transported_nested):
        line_branch = _intent_branch(schema, "exact_line_replace")
        assert line_branch["examples"] == [EXACT_LINE_REPLACE_EXAMPLE]
    example_json = json.dumps(EXACT_LINE_REPLACE_EXAMPLE, separators=(",", ":"))
    assert example_json in request["tools"][0]["function"]["description"]
    assert "illustrating only the JSON shape" in PATCH_TOOL["description"]
    assert "without requiring this edit intent" in PATCH_TOOL["description"]
