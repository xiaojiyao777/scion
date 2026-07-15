# Scion v0.4 Current State

*Last updated: 2026-07-15*

Read `scion/TASK.md` first. Use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

## Operational State

No experiment is running. The latest live root, CVRP R6, is terminal,
complete, valid, and read-only. Its only branch is `ready_validate`; its
cumulative candidate must be evaluated in a distinct copied-state continuation
after the current evidence-integrity repair is committed and pushed.

Do not resume or relaunch R4, R5, or R6 in place. Do not use R6's round-2 v2
formal artifact to reconstruct the candidate. Copy the complete R6 campaign
workspace.

## R6 Identity

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw`;
- campaign:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-56ba4851`;
- exact runtime commit:
  `56ba4851c92ef8e925a5d5e368d988a138c80286`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- branch id: `ccc5d6df-642e-4f78-adc3-46d15b1b99ac`;
- branch state/status: `ready_validate / clean`;
- current and last-clean code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- champion: v1, unchanged;
- data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.

Wrapper and campaign exits are `0`; requested/effective/evaluated rounds are
`2/2/2`; all are screening. Provider accounting is exactly `2H/2C`, four
successful durable attempts, retry/replacement=`0`. Formal pairs are `64/64`
valid with no candidate, champion, solver, Contract, Verification, Canary, or
infrastructure failure. Postrun readiness is 28 `ok`, 3 optional problem-owned
`skipped`, and no failure.

## R6 Scientific Result

### Round 1

The agent changed `destroy_repair.py` and `scheduler.py` to make regret repair
route-cap-aware and mildly noise-perturbed.

- case W/L/T: `0/4/4`;
- pair W/L/T: `9/16/7`;
- median/CI: `-3.25 / [-9.25,0]`;
- Decision: `continue_explore / SCREENING_FAIL_WIN_RATE`;
- route-limit: candidate/champion `32/98`;
- repair-error: candidate/champion `5/0`;
- fresh runtime median ratio: `1.0021`.

The mechanism reduced route-cap rejection but did not improve final quality.

### Round 2

H2 received exactly one complete R1 observation with all eight case rows, 32
pair rows, objective/CI/runtime facts, route-limit `-66`, repair-error `+5`,
and verified current source. It explicitly used the negative result and moved
to a different mechanism: capacity-feasible swap-star in `local_search.py`.
C2 exercised two ordered same-file `exact_replace` edits successfully.

The evaluated candidate is cumulative R1 repair plus R2 swap-star:

- case W/L/T: `5/1/2`;
- pair W/L/T: `20/11/1`;
- median/CI: `+3.5 / [-11,12]`;
- Decision: `queue_validate / SCREENING_PASS`;
- statistical status: `uncertain`;
- X-n110-k13 median: `-55`; CMT4 median: `-11`;
- ALNS iterations: `1857 -> 789`;
- initial VNS: `25639 -> 75078 ms`;
- embedded VNS: `778603 -> 798764 ms`.

All round-2 champion results were cached, so comparative runtime status is
`insufficient` and no runtime-ratio conclusion is allowed. The search-allocation
shift is descriptive risk that fresh validation must resolve.

## R6 Artifact Caveat

R6's live branch workspace is internally correct, but its old v2 R2 artifact is
not cumulative:

- declared base: `champions/champion_v1`;
- stored R2 files: only `local_search.py`;
- declared code hash: cumulative `0d9c2ce5...`;
- champion plus stored R2 patch hash: `0cc21753...`;
- missing inherited files: `destroy_repair.py`, `scheduler.py`.

The old postrun `git apply --check` accepted this incomplete artifact. Treat the
R6 report's formal-integrity check as superseded by the explicit audit. The
exact candidate remains safely available through the complete campaign
workspace.

## Current Worktree

Branch: `v0.4-dev`.

Owned changes in progress:

- formal artifact v3 cumulative replay closure;
- exact champion snapshot resolution and editable identity manifest;
- fixed replay and postrun fail-closed materialization validation;
- canonical feedback attribution/scope/deduplication repairs;
- CVRP ALNS evidence-scope labels;
- R6 terminal report;
- compact `TASK.md` and this resume document;
- focused and boundary tests.

Verification is green: the final formal-artifact/postrun slice is `17 passed`,
the complete unit suite is `705 passed`, and the standard repository-root suite
is `1926 passed, 1 skipped`. The final review's partial-index crash-window P1
has been repaired and independently retested; no substantive P0/P1 remains.
Compileall and `git diff --check` pass.

Excluded and preserved:

- tracked user change: `scion/docs/v0.4-measurement-readiness.md`;
- unrelated untracked historical/future docs shown by `git status`.

## Immediate Resume Actions

1. Stage only the owned code/tests/docs, commit, and push `v0.4-dev`.
2. Create a clean detached runtime worktree at that pushed commit.
3. Prepare one diagnostic continuation with:
   `launch_cvrp_direct_campaign.py --rounds 1 --resume-from-campaign <R6/campaign>`.
   Keep model `gpt-5.6-sol`, solver limit `30`, data root
   `/home/clawd/research/or-autoresearch-agent/vrp`, and key source
   `SCION_SHARED_PROXY_KEY`.
4. Do not pass `--launch`, `--completion-preflight`, force flags, or
   `--skip-postrun-reports`; resume and completion-preflight are intentionally
   incompatible. Inspect the prepared root, then start its `run.sh` manually
   exactly once.
7. Poll at low frequency and verify one validation result, no new H/C
   transition or trace, unchanged candidate hash, fresh champion runtime, and
   campaign-scoped postrun integrity.
8. Write the validation report and update these two resume docs.
9. Then prepare a separate clean four-round generative CVRP root. Expand to
   eight only if the four-round evidence is still insufficient.

## Continuation Prelaunch Checks

- source R6 PID is absent and source root is terminal complete/valid;
- SQLite `PRAGMA integrity_check` is `ok`;
- the only branch is `ready_validate`, clean, and has hash `0d9c2ce5...`;
- source branch workspace exists and recomputes to the same editable hash;
- copied campaign preserves branch id/state/workspace/hash;
- `resume_snapshot/resume_source_manifest.v1.json` exists;
- copied old status/summary/run markers are isolated as resume evidence;
- `launch.env` has correct resume source, `COMPLETION_PREFLIGHT=0`, `ROUNDS=1`,
  `TIME_LIMIT_SEC=30`, model, base URL, and key-env name;
- generated `run.sh` hash equals both launch and prepared-manifest anchors;
- data identity remains `ca7e470e...`;
- no provider call is expected; copied cumulative H/C counters are not counted
  as current invocation activity.

## Runner Notes

Server `claw`:

- repo: `/home/clawd/research/or-autoresearch-agent`;
- Python: `/home/clawd/miniconda3/envs/claw/bin/python`;
- use for focused tests and one experiment at a time.

WSL `scion` remains the large/concurrent runner only after a fresh connectivity
and preflight check.

Proxy key handling: `SCION_SHARED_PROXY_KEY` is the local proxy credential;
inject the value through process environment only. Do not print it, persist it,
or place it in argv.

## Pointers

- Active task: `scion/TASK.md`
- V3 architecture: `scion/design/scion-architecture-v3.md`
- Direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- R5 terminal report:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-causal-feedback-r5-postrun-20260715.md`
- R6 terminal report:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-causal-feedback-r6-postrun-20260715.md`
