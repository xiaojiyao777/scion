# Scion v0.4 Current State

*Last updated: 2026-07-15*

Read `scion/TASK.md` first. Use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

## Operational State

No experiment is running. The latest launched root is the terminal, complete,
valid, read-only R6-R2 exact validation root ending
`20260715T180743Z-claw`. Its only branch is `validating_expand`; the same
candidate must next run the preregistered 12-case expanded validation in a
distinct copied-state continuation, with no H/C/provider call.

The prepare-only roots ending `20260715T175626Z-claw` and
`20260715T193404Z-claw` were never launched and are superseded. The latter
proved that a second resume copied both candidate metadata files but lost the
inherited index held in the source root's outer snapshot. Do not start either
superseded root.

Do not resume or relaunch R4, R5, R6, or the completed validation in place. Do
not use R6's round-2 v2 artifact alone to reconstruct the candidate. Copy the
complete terminal validation campaign workspace into a fresh root.

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

## Exact Validation Identity and Result

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-exact-validation-1r-gpt56sol-20260715T180743Z-claw`;
- campaign: `<root>/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-5a441e4`;
- runtime commit: `5a441e4488cc2d6d19ae7c92878ffb3864976e53`;
- branch/hypothesis: `ccc5d6df... / 2a988064...`;
- branch state/status: `validating_expand / clean`;
- candidate hash: `0d9c2ce5...6535a`, unchanged;
- champion: v1, unchanged;
- data identity: 81 files, `ca7e470e...30743`.

The one requested validation round completed with `32/32` valid fresh-runtime
pairs and no candidate/champion/infra failure. Current-invocation H/C/provider/
trace deltas are all zero; copied cumulative totals must not be attributed to
this invocation. Postrun readiness is 28 `ok`, three optional `skipped`, and no
failure.

- case W/L/T: `6/1/1`;
- pair W/L/T: `25/5/2`;
- median/CI: `+7.75 / [0,77]`;
- runtime ratio/delta: `1.0111 / +287.5 ms` across 32 fresh pairs;
- Decision: `expand_validation / VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`.

The candidate is promising but unvalidated. `tai150a` loses by median `-84.5`;
ALNS iterations fall `1202 -> 604`, while initial VNS time rises
`138836 -> 299320 ms`. Formal validation has no swap-star-specific telemetry,
so neither gains nor losses can yet be causally assigned to that operator.

## Current Runtime Repair

Branch: `v0.4-dev`.

The formal-artifact, replay, feedback, protocol-projection, postrun, and
multi-hop resume repairs are pushed through `94769f07`. The current revision
adds:

- one atomic current/latest/per-stage branch protocol evidence projection;
- validation/frozen continue and frozen-promotion lifecycle coverage;
- transitive inherited formal-candidate ownership flattening in a dedicated
  launcher module;
- canonical row/ref/metadata identity validation, exact metadata coverage, and
  snapshot size/SHA binding before launch;
- inherited/live separation so old candidates remain cumulative lineage and a
  new invocation's live index remains current-only;
- exact validation terminal report;
- compact `TASK.md` and this resume document;
- focused multi-hop, conflict, tamper, legacy, and omitted-row tests.

The resume/lineage/launcher slice passes `47`, the complete unit suite passes
`712`, and the standard Scion suite passes `1949` with `1` skipped. Compileall,
Black check, and `git diff --check` pass. Two independent final reviews found
no remaining P0/P1. The exact-validation source's two v2 candidate rows and
two metadata files pass the stricter real-root preparation and postrun checks.

Excluded and preserved:

- tracked user change: `scion/docs/v0.4-measurement-readiness.md`;
- unrelated untracked historical/future docs shown by `git status`.

## Immediate Resume Actions

1. Create a clean detached runtime worktree at `94769f07` or its
   documentation-only successor.
2. Prepare one diagnostic continuation with:
   `launch_cvrp_direct_campaign.py --rounds 1 --resume-from-campaign <exact-validation/campaign>`.
   Keep model `gpt-5.6-sol`, solver limit `30`, data root
   `/home/clawd/research/or-autoresearch-agent/vrp`, and key source
   `SCION_SHARED_PROXY_KEY`.
3. Do not pass `--launch`, `--completion-preflight`, force flags, or
   `--skip-postrun-reports`; resume and completion-preflight are intentionally
   incompatible. Inspect the prepared root, then start its `run.sh` manually
   exactly once.
4. Poll at low frequency. Early progress must show `stage=validation`,
   `expand=true`, `expand_round=1`, 12 cases, four seeds, and 48 pairs.
5. At terminal, verify no new H/C/provider/trace, unchanged candidate hash,
   `48/48` valid pairs, fresh champion runtime, `validation_expand_count=1`,
   and campaign-scoped postrun integrity.
6. Write the expanded-validation report and update these two resume docs.
7. Only after the same candidate reaches a terminal validation/frozen result,
   prepare a separate clean four-round generative root. Expand to eight only if
   the four-round evidence is still insufficient.

## Continuation Prelaunch Checks

- source validation PID is absent and source root is terminal complete/valid;
- SQLite `PRAGMA integrity_check` is `ok`;
- the only branch is `validating_expand`, clean, has
  `validation_expand_count=0`, and hash `0d9c2ce5...`;
- source branch workspace exists and recomputes to the same editable hash;
- copied campaign preserves branch id/state/workspace/hash;
- `resume_snapshot/resume_source_manifest.v1.json` exists;
- its fixed inherited formal-candidate index contains exactly the two source
  rows, has manifest-bound size/SHA, covers both copied metadata files, and no
  live index is present before the new invocation;
- copied old status/summary/run markers are isolated as resume evidence;
- `launch.env` has correct resume source, `COMPLETION_PREFLIGHT=0`, `ROUNDS=1`,
  `TIME_LIMIT_SEC=30`, model, base URL, and key-env name;
- generated `run.sh` hash equals both launch and prepared-manifest anchors;
- data identity remains `ca7e470e...`;
- no provider call is expected; copied cumulative H/C counters are not counted
  as current invocation activity.

During the expanded run, the in-memory expand count becomes one before the DB
row is persisted; use `current_progress.expand=true/expand_round=1` and the
48-pair partial metric as the early authority. A successful terminal run must
persist count one. The expanded gate must not request a second expansion.

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
- R6-R2 exact validation report:
  `scion/docs/experiments/v0.4/v04-cvrp-r6-r2-exact-validation-postrun-20260715.md`
- Multi-hop lineage repair report:
  `scion/docs/experiments/v0.4/v04-resume-formal-candidate-lineage-repair-20260715.md`
