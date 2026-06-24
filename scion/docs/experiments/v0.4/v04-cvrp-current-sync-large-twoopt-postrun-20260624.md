# CVRP Current-Sync Large-Twoopt Postrun

Date: 2026-06-24

## Purpose

This run is the clean current-sync CVRP continuation after the v0.4
runtime-semantics, prompt/source, guidance-contract, active-slot, target-intent,
and postrun-readiness repairs. It resumed the earlier solver-depth campaign
from a synchronized WSL checkout and focused the next solver-design ladder on
`large_instance_intra_route_two_opt_seed`.

The purpose was not to make Scion a CVRP-specific framework. The run tested
whether generic Scion control paths can support deep, evidence-aware research:
same-mechanism continuation, MDE-aware rejection, branch lessons, prompt/source
visibility, runtime semantics under `budget_exhausting`, and fail-closed
handling when the solver mechanism is weak or inactive.

## Artifacts

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-current-sync-d3efc3cb-postsolverdepth-6r-gpt55-20260623T182433Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-current-sync-d3efc3cb-postsolverdepth-6r-gpt55-20260623T182433Z-claw`
- WSL runtime commit at launch: `d3efc3cb`
- Model: `gpt-5.5`
- Requested continuation budget: `6`
- Focused mechanism family: `large_instance_intra_route_two_opt_seed`

Strict launch readiness passed before launch, including the `gpt-5.5`
completion preflight. The WSL postrun readiness artifact is authoritative for
this WSL-origin root. The local mirror was produced with
`scripts/sync_wsl_run_root.py --execute --skip-postrun-check --format json`
because the stored postrun artifacts contain WSL absolute paths.

## Lifecycle

- Wrapper exit/status: `0` / `finished`
- Campaign wrapper exit/status: `0` / `finished`
- Campaign runtime: `2026-06-23T18:26:27Z` to `2026-06-23T21:28:23Z`
- Postrun acceptance status: `ready`
- Postrun readiness: `current_run_analysis_ready=true`,
  `delegation_ready=true`
- Required readiness failures: none
- Optional readiness failures: `postrun_report_status_marker`
- Inventory source: `stored_postrun_inventory`
- Validity/completeness: `valid` / `complete`
- Stop reason: `max_rounds_exhausted`
- Effective budget counter: `6` of `6`
- Effective Protocol rows / metric rows: `7` / `7`
- Screening Protocol rows: `7`
- Validation/frozen rows: `0` / `0`
- Verification-consumed candidates: `7`
- Proposal attempts total: `8`
- Proposal quality blocks: `2`
- Active-slot blocked attempts: `0`
- Stage-transition drain: `not_selected_no_pending`

The `6` effective-budget counter and `7` Protocol metric rows differ because
the current postrun accounting distinguishes legacy max-round completion from
completed Protocol metric rows. Use Protocol rows when reading metric evidence
and the effective-budget counter when reading stop semantics.

## Measurement Signal

This is not solver progress.

- Champion stayed at version `1`.
- Promotions: `0`
- Measurement readiness: `ready`
- MDE at 80 percent power: `9.9`
- Protocol rows at or above MDE: `0`
- Rows with CI high below MDE: `7`
- Maximum effect-to-MDE ratio: `0.0`
- Mechanism-family mapped rows: `7`
- Nonpositive rows: `7`

| Mechanism family | Rows | Positive | At/above MDE | CI high below MDE | Max effect/MDE |
|---|---:|---:|---:|---:|---:|
| large_instance_intra_route_two_opt_seed | 7 | 0 | 0 | 7 | 0.0 |

Pair-level evidence was weak and non-promotable. Across current-run screening
rows, case-level gate results were all ties (`0` wins, `0` losses, `68` ties),
while pair-level results were `12` wins, `3` losses, and `257` ties across
`272` pairs. Median delta remained `0.0` for every row.

## Large-Twoopt Evidence

The postrun large-twoopt review result is
`protocol_evaluated_without_large_twoopt_signal`, with evidence gap
`missing_large_twoopt_mechanism_signal`.

The first two rows did observe activation and phase runtime for the declared
mechanism, but direct objective effect was zero. Later rows stayed in the same
declared family while the primary mechanism was reported as missing or not
triggered. The strict direct-evidence summary therefore remained not ready:
there was no positive effect at or above MDE, no complete protected-case direct
evidence, and no review-ready CMT2/CMT4 protection signal.

This distinction matters. Activation or seed selection is not solver evidence;
CVRP problem-owned validators require current-run objective effect evidence
against MDE and protected-case review inputs before a bounded two-opt conclusion
can be called review-ready.

## Research Continuity

The run does show effective research behavior at the framework level:

- Active research shape: `mixed_depth`
- Max/mean branch depth: `5` / `4.0`
- Branch depth distribution: `3=1, 5=1`
- Active branch count max: `8`
- Active mechanism-family count: `1`
- Same-mechanism follow-up selected/observed/missed: `8` / `8` / `0`
- Branch lessons satisfied/required: `3` / `2`
- Branch-lesson semantic gaps: `0`
- Research-context actionability gaps: none
- Prompt/source visibility had no missing required target-source evidence.

This is the key accepted framework signal for the current CVRP root: Scion can
follow and reject the same mechanism without active-slot blocking, broad
runtime-pressure misrouting, or prompt/source invisibility.

## Runtime And Quality

Runtime behavior was consistent with the repaired `budget_exhausting`
semantics:

- Runtime budget diagnostics: `7`
- Runtime diagnostic code: `SCREENING_RUNTIME_BUDGET_SATURATION`
- Severity: `info`
- Fresh-runtime replay drain executed: `0`
- Stage-transition drain executed: `0`

Budget saturation stayed observational. It did not create clean-fork runtime
pressure or override solver-quality evidence.

The two proposal quality blocks did not invalidate the run:

- One pre-Protocol code-generation failure came from a transient Codex API 400
  unsupported-content-type error.
- One non-counting proposal block followed a zero-win same-branch refinement
  with low cached runtime confidence.

Both blocks had `counts_toward_max_rounds=false`. They are useful taxonomy
signals, not evidence of a runaway quality loop or scheduler blocker.

## Interpretation

Accepted v0.4 interpretation:

- The current-sync CVRP root is clean evidence that the repaired framework can
  support evidence-backed CVRP continuation and rejection: branch depth reached
  5, same-mechanism selection was 8/8, active-slot blocks were 0, and runtime
  budget saturation stayed observational.
- The root is not solver improvement evidence. Champion stayed `v1`, all rows
  were below MDE, direct large-twoopt evidence was not ready, and no promotion
  occurred.
- This narrows the remaining v0.4 gap. The immediate blocker is less about
  generic Scion control-flow failure and more about problem-owned CVRP/VRP
  solver opportunity quality and how compactly that opportunity evidence
  reaches proposal contexts.
- Do not respond by adding CVRP-specific gates, CMT rules, BKS logic, ALNS/VNS
  assumptions, or two-opt semantics to generic core.

## Next Design Direction

The next design work should be subtractive and port-based:

- Generic core: split postrun/readiness growth into named lifecycle/readiness
  ports that own artifact identity, current-run evidence, fail-closed status,
  schema validation, and exposure boundaries.
- Generic core plus problem-owned providers: stabilize the measurement
  declaration consumer path for normalized runtime model, effect scale, pairing
  validity, calibration freshness, and readiness tier.
- Problem-owned CVRP/VRP layer: provide compact proposal-only opportunity
  summaries for residual gap, protected cases, mechanism activation/effect
  counters, direct objective deltas, and MDE comparison. Generic core should
  only render and audit exposure, not interpret CVRP semantics.

## Boundary

This report is postrun and planning evidence. It does not change Decision,
`DecisionFeatures`, Protocol gates, scheduler policy, promotion policy, runtime
pressure semantics, or generic Scion core. CVRP/BKS/CMT/ALNS/VNS/two-opt
semantics remain problem-owned.
