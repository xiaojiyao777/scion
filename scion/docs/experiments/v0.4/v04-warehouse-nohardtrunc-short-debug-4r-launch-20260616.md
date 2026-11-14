# Warehouse No-Hard-Truncation Short Debug 4R Launch - 2026-06-16

## Purpose

Run the first live campaign after the W4/P2 prompt signal-density repair and
the no-hard-truncation follow-up. This is a field check for prompt/context
rendering on real warehouse traces, not a longrun research-efficiency claim and
not a governance on/off comparison.

The primary question is whether real `gpt-5.5` hypothesis contexts under the
current v0.4 research-stage policy preserve useful projected research signal
without provider-visible truncation, fixed item caps, synthetic ellipses, or
raw audit/template noise.

## Launch

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `061eba0` (`docs: record no hard prompt truncation policy`)
- Code repair commit: `fd185cf` (`fix: remove prompt research signal hard caps`)
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z`
- WSL tmux session: `scion_wh_nohardtrunc_short4r_155951`
- Started at UTC: `2026-06-16T16:00:59Z`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model: local `gpt-5.5`
- API base: `http://127.0.0.1:8080`
- API key source: WSL-local `codex-proxy/data/local.yaml:server.proxy_api_key`
  read at runtime; the key is not written into artifacts.

## Shape

- Problem: warehouse production package
- Protocol: experiment-local copy of `protocol_prod.yaml`
- Split: experiment-local copy of `split_manifest_prod.yaml`
- Safe data root: `/home/xjy-ubuntu/research/scion-data`
- Rounds: `4`
- Cells: `1`
- Measurement governance: `on`
- Context profile: `compact-measurement-diagnostics`
- Time limit: `30s`
- Early stop: disabled
- Agentic proposal: enabled
- Agentic session timeout: `900s`
- Wrapper timeout: `5h`

## Launch Health

Initial checks passed:

- WSL checkout fast-forwarded to `061eba0`.
- WSL Python, `gpt-5.5` `/v1/models`, warehouse data roots, and surrogate root
  were present.
- A direct proxy probe with the WSL-local `server.proxy_api_key` returned HTTP
  `200` for `gpt-5.5`.
- The formal run entered `status=running` and created
  `agentic_session_trace_index.json` with one pending hypothesis session.
- `run.log` reached campaign startup:
  `Starting campaign: warehouse_delivery (max_rounds=4, mock_llm=False, disable_early_stop=True)`.

Invalid first attempt:

- Root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155433Z`
- Server sync:
  `/home/clawd/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155433Z`
- Status: invalid launch-env failure. It reached campaign startup but APS failed
  with missing LLM credentials because the script did not pass `SCION_API_KEY`.
  It was stopped and must not be interpreted as research evidence.

## Acceptance

Accept this field check only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- requested rounds, proposal attempts, Protocol rows, fresh-runtime replay rows,
  and formal candidate artifacts reconcile;
- all LLM traces use `gpt-5.5` and have no auth/API failure;
- code-stage target/current source visibility remains intact;
- prompt manifests for hypothesis contexts show `compact_research_signals`,
  `branch_lesson_usage_context`, and `cross_branch_research_map`, when present,
  are included/non-truncated;
- rendered prompt text does not contain `<truncated agentic context>`,
  `... [truncated]`, or synthetic ellipsis from research-signal projection;
- later branch lesson ids and evidence summaries are visible when projected,
  not hidden by fixed list caps;
- raw audit rows, session metadata, and per-lesson `required_response` payloads
  remain excluded from provider-visible research context.

Postrun must separate prompt-rendering field validity from research-quality
results. A 4R run can validate the prompt/context repair path; it cannot prove
warehouse continuous-improvement recovery by itself.
