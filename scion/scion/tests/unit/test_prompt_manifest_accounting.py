from __future__ import annotations

from scion.proposal.prompt_manifest import build_api_visible_prompt_manifest
from scion.proposal.prompt_manifest_accounting import (
    _cacheability_summary,
    _json_chars,
    _provider_prompt_hash,
    _system_block_records,
    _system_text_chars,
    _text_digest,
)


def test_prompt_manifest_accounting_uses_rendered_provider_prompt() -> None:
    system_blocks = (
        {
            "text": "## Cacheable Instructions\nUse visible constraints only.",
            "cache_control": {
                "type": "ephemeral",
                "raw_metrics_ref": "internal-validation-ref",
            },
        },
        {"text": "## Live Instructions\nKeep output concise."},
    )
    user_prompt = "## User Request\nReturn a proposal based on visible context."
    prompt_context = {
        "visible_hint": "safe aggregate",
        "raw_validation_payload": "secret_validation must stay audit-only",
    }

    manifest = build_api_visible_prompt_manifest(
        session_id="accounting-session",
        phase="draft_hypothesis",
        call_kind="hypothesis",
        prompt_context=prompt_context,
        observations=[],
        call_index=1,
        system_blocks=system_blocks,
        user_prompt=user_prompt,
    )

    system_records = _system_block_records(system_blocks)
    expected_cacheability = _cacheability_summary(
        system_block_records=system_records,
        user_prompt_chars=len(user_prompt),
    )
    expected_prompt_hash = _provider_prompt_hash(system_blocks, user_prompt)

    assert manifest["provider_visible_prompt"]["system_text_chars"] == (
        _system_text_chars(system_blocks)
    )
    assert manifest["provider_visible_prompt"]["user_prompt_chars"] == len(user_prompt)
    assert manifest["provider_visible_prompt"]["cacheability"] == expected_cacheability
    assert manifest["provider_visible_prompt"]["prompt_hash"] == expected_prompt_hash
    assert manifest["prompt_hash"] == expected_prompt_hash
    assert manifest["raw_context_audit"]["json_char_count"] == _json_chars(
        {
            "visible_hint": "safe aggregate",
            "raw_validation_payload": "",
        }
    )
    assert system_records[0]["content_hash"] == _text_digest(system_blocks[0]["text"])
    assert "raw_metrics_ref" not in system_records[0]["cache_control"]
