# v0.4 Warehouse Direct Control at `b1464171`

- Date: 2026-07-13
- Model: `gpt-5.6-sol`
- Requested rounds: `2`
- Runtime mode: `direct_v3`
- Run root:
`/home/clawd/research/scion-experiments/v04-warehouse-direct-control-2r-gpt56sol-20260713T144325Z-claw`

## Verdict

The formal wrapper, completion route, and both provider calls worked. The agent
also produced a materially new warehouse hypothesis and a complete 484-line
operator rather than a cosmetic edit. This run nevertheless contains zero
evaluated candidates and is invalid for algorithm conclusions.

The direct stop chain was:

```text
H generated
  -> C generated
  -> outer Contract C9 rejected local telemetry reflection
  -> no candidate workspace
  -> Verification skipped
  -> Protocol not entered
  -> research_rejected
```

The campaign stopped after that first non-evaluated outcome. It did not retry
H/C and did not schedule a replacement attempt.

## Execution Evidence

- completion preflight: authenticated HTTP 200 with a non-empty response;
- provider traces: one successful H and one successful C;
- durable attempts: H=`1`, C=`1`;
- scheduled candidate calls: `1`;
- effective Protocol rounds: `0`;
- screened experiments: `0`;
- run validity: `invalid_research_rejected_only`;
- last outcome: `research_rejected / PATCH_CONTRACT_REJECTED`;
- campaign wrapper exit: `0`; root wrapper exit: `64` because the original
  postrun readiness check failed.

No Scion output cap or truncation was active. H used 10,435 input / 367 output
tokens. C used 13,485 input / 6,919 output tokens; the provider-managed output
parameter was omitted and no transport output ceiling was set.

## Research Assessment

H targeted the primary lexicographic objective `subcategory_splits`. It
proposed a bounded best-first ejection-chain that moves a subcategory group
between compatible vehicles, relocates up to two blocking orders, resizes
affected vehicles, and accepts only a strict improvement in
`(subcategory_splits, total_cost)`. This directly addresses a weakness in the
champion's random single-order moves and shuffled first-feasible rebuild.

C created `operators/subcategory_consolidation.py` and was correctly bound to
the approved target and full `proposal_source_ledger`. C4, C4b, C5, C6, C7,
C8, C9b, and C9d passed. The only Contract rejection was:

```python
def _record(self, key, value):
    setattr(self, key, getattr(self, key) + value)
    self.validation_transfer_diagnostics[key] = getattr(self, key)
```

The prompt requested operator-instance telemetry but did not expose a ban on
this reflective bookkeeping form. C9 therefore blocked a source-bound
algorithm candidate for a style choice that did not cross the operator's local
state boundary.

## Candidate Defects That Verification Still Needed to Catch

Passing Contract would not establish that the generated operator worked.
Read-only source audit found at least one deterministic runtime defect in the
two-blocker path: the frontier score's third field changes from a tuple to a
numeric vehicle cost, after which `_score[2] + (vid,)` can raise `TypeError`.

Two additional effectiveness risks need executable coverage:

- `joins_same` is computed after the candidate order has already been inserted,
  so the intended ranking feature is effectively constant;
- H6 uses a conservative maximum observed feasible load instead of the
  problem's declared amount limit, which may reject legal consolidations and
  leave the operator inactive.

These are reasons to preserve Verification as the executable owner, not to
move algorithm-quality policy into Contract.

## Framework Findings and Repairs

1. The warehouse H/C context no longer advertises optional operator telemetry
   fields. They were diagnostic, not required for research, and were noise that
   induced the rejected helper. C9 remains fail-closed. The generic C
   implementation instruction now exposes its concise no-reflection/API rule,
   so the model is no longer asked to satisfy a hidden constraint.
2. Direct-v3 trajectory manifests store `attempts -> phases ->
   prompt_fingerprint`; the postrun reader still expected legacy `sessions ->
   trace_fingerprints`. The reader now resolves only in-root JSON traces,
   binds the three receipt identity fields to the actual H/C rendered-header
   family, verifies the exact canonical context against its SHA-256 digest, and
   derives source visibility from the persisted SourceLedger.
3. Rebuilding this root after the adapter change makes
   `prompt_source_visibility_actionability` pass with H=`1`, C=`1`, code
   protected-source-visible=`1`, missing-required-source=`0`, and receipt
   refs/loaded/normalized=`2/2/2`. It still reports `eligible=false`,
   `ineligible_zero_evaluated`, and
   `algorithm_conclusions_allowed=false`.

Independent review reports P0=`0`, P1=`0`. The final Scion collection is
`1849` tests and the full suite passes `1848 passed, 1 skipped` in `502.91s`.

The old root remains immutable and still fails strict current-run readiness on
its historical wrapper exit/status markers. It is analysis-ready but must not
be restarted or reused.

## Next Step

Commit the narrowly reviewed Contract/postrun repairs, prepare a new clean
detached root, run guarded wrapper readiness, and request explicit operator
approval before launching another warehouse control. Do not reuse the model's
rejected patch as accepted source; the next run must let Contract and
Verification evaluate a fresh candidate normally.
