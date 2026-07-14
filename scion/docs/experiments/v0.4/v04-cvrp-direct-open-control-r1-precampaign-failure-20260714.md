# CVRP Direct Open Control R1 Pre-Campaign Failure

Date: 2026-07-14
Status: infrastructure-only failure; no proposal or solver evidence

## Run

- root: `/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r1-2r-gpt56sol-20260714T151358Z-claw`;
- runtime: detached clean worktree at `64137fc3`;
- model: `gpt-5.6-sol`;
- requested rounds: `2`;
- forced surface/action/target: none;
- parameter search: disabled;
- automatic retry: disabled and not used;
- launcher PID: `2579855`.

The actual initial hypothesis context was rendered locally before launch. It
contained the complete active CVRP algorithm surface and no successor ID,
target intent, forced target, mechanism ranking/denylist, telemetry gate,
candidate cap, retry/backoff, truncation, or semantic agent budget.

## Failure

The guarded wrapper made its single completion preflight. Authentication was
healthy, HTTP status was `200`, and the response was non-empty. Before any
hypothesis call, campaign initialization then rejected all 40 external formal
CVRPLIB cases because `SCION_PROBLEM_DATA_ROOT` pointed at the detached
worktree's partial `vrp/` tree. The gitignored `cvrplib/` data exists only in
the main checkout.

Consequently:

- no campaign proposal transition exists;
- no H or C call occurred;
- no candidate workspace or solver pair was created;
- this root contains no scientific CVRP result;
- the wrapper stopped and was not retried.

The failure also exposed that `/auth/status` was copied too broadly into the
preflight receipt. The receipt unnecessarily persisted the proxy API key and
account identity. Those fields were removed from this failed root with an
explicit `scion.security_redaction.v1` marker before any commit.

## Repair

The launcher repair is deliberately narrow:

1. `--data-root` selects the exact external read-only data root written into
   the prepared contract.
2. Prepare validates every split case against only that explicit root before
   creating a run root. Ambient environment variables cannot make a missing
   explicit root pass.
3. Prepare records a deterministic 81-file identity in the launch environment,
   prepared manifest, and a per-file receipt. Generated `run.sh` requires that
   exact identity before completion preflight, so prepare-to-launch deletion or
   mutation fails before any provider request.
4. Completion receipts retain only `authenticated` and non-sensitive pool
   counts. API keys are read from the environment and are absent from child
   process argv. Receipt creation uses `umask 077`.
5. After campaign execution, the wrapper recomputes the same identity. Any
   missing file, unsafe path, or content drift makes the outer run fail closed.
6. Guarded readiness recognizes the CVRP split-data failure path as required.

The main checkout's ignored dataset is writable, so existence alone is not a
formal identity guarantee. Before a corrected launch, pin the 40 `.vrp` files,
their 40 sibling `.sol` files, and the package canary. The audited ordered
identity digest for that 81-file set is
`ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.
The repaired wrapper performs that before/after comparison automatically; any
drift invalidates the experiment.

Validation completed with `134` focused launcher/data-root/proxy/readiness
tests and the standard full suite at `1872 passed, 1 skipped` in `496.65s`.
`compileall`, `git diff --check`, generated-script `bash -n`, a real 81-file
identity build, and independent P0/P1/P2 review also pass. The final independent
review reports P0=`0`, P1=`0`, P2=`0` for the formal env-based path.

## First Corrected Prepare Audit

After `6ec0db55` was pushed, a distinct clean root was prepared but not launched:

`/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r2-2r-gpt56sol-20260714T161411Z-claw`

Its 81-file identity was correct, but guarded readiness rejected three static
checks before any provider call. Two causes were new generator-auditor drift:

- prepared-contract path validation treated `data_identity_sha256` as a path;
- the canonical completion-receipt reference allowlist did not recognize the
  new `chmod 600 "$PREFLIGHT_DETAIL"` hardening line.

The analysis-brief failure was downstream of the same config-path error. The
minimal follow-up marks SHA/digest config scalars as non-path metadata and
accepts only the exact owner-only receipt chmod form. Focused prepared-contract,
readiness, launcher, handoff, and identity coverage passes `124` tests; the
standard full suite passes `1875 passed, 1 skipped` in `502.33s`. Negative tests
confirm appended shell operations are rejected, and independent P0/P1/P2
review is green. This R2 root remains prepared-only and must not be edited or
launched; create another clean root after the follow-up commit.

## Disposition

Keep this root as infrastructure evidence only. Do not resume or relaunch it.
After the repair is committed and pushed, prepare a distinct clean root at the
new exact commit with the explicit data root and pinned data identity. Because
automatic retry is prohibited, the corrected root must not be started as an
implicit retry of this failure.
