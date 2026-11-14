# LLM Transport: Codex Proxy Notes

*Date: 2026-05-24*

This note records the current Scion decision for using local Codex
subscription-backed models through `/home/clawd/research/codex-proxy`.

## Decision

Keep Scion's default OpenAI-compatible transport on `/v1/chat/completions` for
now. When `SCION_BASE_URL=http://127.0.0.1:8080` and `SCION_MODEL=gpt-5.5`,
codex-proxy translates the chat request to the Codex Responses backend while
preserving function tools and usage metadata. This is enough for current Scion
APS experiments and avoids changing the proposal/session contract.

For routine short experiments in the current v0.4 framework-debug stage, do
not set `SCION_REASONING_EFFORT`; use the provider/model default for faster
iteration. Explicit `SCION_REASONING_EFFORT=xhigh` remains available only for
targeted transport or model-quality diagnostics.

Do not switch the default Scion transport to `/v1/responses` yet. Add Responses
later as an opt-in wire API only when Scion needs native Codex turn state such
as `previous_response_id`, prompt cache keys, Responses event metadata, or
hosted tool payloads. Scion tools must remain APS-controlled structured
outputs; hosted Codex tools should not bypass Scion's v3 boundary.

## Implemented

- GPT/Codex model IDs now forward `SCION_REASONING_EFFORT` as
  `reasoning_effort` when using the OpenAI-compatible chat transport.
- Allowed GPT/Codex efforts are `low`, `medium`, `high`, and `xhigh`.
- DeepSeek behavior is unchanged: `xhigh` normalizes to `max`, `low` and
  `medium` normalize to `high`, and DeepSeek still receives
  `extra_body.thinking`.
- OpenAI-compatible usage parsing now reads
  `prompt_tokens_details.cached_tokens` and derives uncached prompt tokens when
  explicit miss tokens are absent.
- OpenAI-compatible usage metadata now records
  `completion_tokens_details.reasoning_tokens` as `reasoning_output_tokens`.

## Validation

Unit validation:

```bash
python -m pytest scion/scion/tests/test_llm_client.py -q
```

Result: `55 passed`.

Live local transport validation used:

```bash
SCION_MODEL=gpt-5.5 \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY=pwd \
python - <<'PY'
from scion.proposal.llm_client import LLMClient

client = LLMClient(max_retries=0, sdk_max_retries=0, max_tokens=128)
result = client.call_with_tool(
    "Compute (19*23) - 17 and call the tool with the answer.",
    {
        "name": "report",
        "input_schema": {
            "type": "object",
            "properties": {"answer": {"type": "integer"}},
            "required": ["answer"],
            "additionalProperties": False,
        },
    },
)
print(result, client.get_last_usage_metadata())
PY
```

Observed result: the tool call returned `{"answer": 420}`, confirming that
`gpt-5.5` can use Scion's required structured tool path through codex-proxy's
chat compatibility route. Separate targeted transport checks may set
`SCION_REASONING_EFFORT=xhigh` to verify reasoning-token accounting, but that
is not the routine short-experiment launch mode.

## Future Responses Transport

If added, `/v1/responses` should be implemented as a transport option such as
`SCION_LLM_WIRE_API=responses`, not as a semantic proposal-layer change. The
public `LLMClient.call()` and `LLMClient.call_with_tool()` behavior should stay
stable. First support should be limited to:

- plain structured text responses;
- one required function tool call;
- normalized usage metadata;
- provider timeout/error classification aligned with the existing transport.

Avoid enabling hosted web/image/code tools in the first pass. Those capabilities
would need separate v3 boundary decisions.
