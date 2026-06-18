# CVRP Construction-Pivot Guidance Infra Failures

Date: 2026-06-18
Commit: `867f5de`

## Conclusion

No research evidence was produced. Both attempted follow-up checks failed
before any interpretable CVRP candidate evidence:

- WSL `127.0.0.1:8080` proxy: authentication/session failure.
- Server fallback through `https://aihubmix.com`: account balance/quota failure.

Do not interpret either run as solver-design evidence.

## WSL Attempt

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-constructionpivot-guidance-agentic-1r-867f5de-20260618T072547Z`

WSL source root:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-constructionpivot-guidance-agentic-1r-867f5de-20260618T072547Z`

Status:

- `campaign_summary.json`: `run_validity_status=invalid_no_effective_rounds`
- `completed_requested_rounds=false`
- `last_stop_reason=circuit_breaker`
- `proposal_quality_blocks=3`
- `0` effective rounds

Failure:

- Scion hit three consecutive LLM failures.
- The proxy returned `401 invalid_api_key` / `Not authenticated. Please login first at /`.
- Direct proxy diagnosis showed the configured local proxy key was accepted,
  but the upstream account failed with `refresh_token_invalidated`.

Operational note: `/v1/models` on this proxy is not a sufficient preflight.
Before another WSL campaign, `/v1/chat/completions` must return HTTP `200`
and non-empty text/tool content for `gpt-5.5`.

## Server Fallback Attempt

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-constructionpivot-guidance-local-agentic-1r-867f5de-20260618T073729Z`

Status:

- `run_status.json`: `run_validity_status=invalid_infra_only`
- `campaign_exit_status=incomplete_infra_stop`
- `last_stop_reason=api_balance_exhausted`
- `wrapper_exit_status=20`
- `0` effective rounds

Failure:

- The local aihubmix probe could authenticate and return normal text for
  `gpt-5.5` with a sufficiently large output cap.
- The real Scion campaign failed immediately with a `403`
  `insufficient_user_quota` response.
- A separate official OpenAI endpoint probe using `OPENAI_API_KEY` failed with
  `429 insufficient_quota`.

## Resume Criteria

Before relaunching the construction-pivot guidance check:

1. Restore a `gpt-5.5` completion path that returns HTTP `200` and non-empty
   output from `/v1/chat/completions`.
2. For WSL, prefer the synchronized runner worktree at
   `/home/xjy-ubuntu/research/or-autoresearch-agent` and keep
   `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`.
3. Rerun the same one-round construction-pivot guidance check from a clean
   synced commit.
4. Interpret candidate evidence only after live `hypothesis_target_intent` and
   `hypothesis` traces show the construction-pivot lesson and the run completes
   at least one effective round.
