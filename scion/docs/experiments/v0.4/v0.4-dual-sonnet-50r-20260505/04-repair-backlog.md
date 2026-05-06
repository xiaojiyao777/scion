# Repair Backlog

This backlog is derived from the 2026-05-05 dual Sonnet 50-round analysis. It
prioritizes framework correctness and v0.4 design closure before further long
experiments.

## P0: Evidence and Lifecycle Correctness

1. Normalize runtime-failure reason codes in campaign summaries.
   CVRP round 42 is recorded as candidate runtime failure in DB decision
   lineage, but summary-level reason codes still make it look like only a
   screening win-rate failure. Summary rows should preserve the decisive
   runtime veto.

2. Close or explicitly mark residual branches at max-round termination.
   CVRP ended with one `explore` branch. Either close active branches with a
   max-round terminal status or expose a clear `residual_due_to_max_rounds`
   field so final state is not ambiguous.

3. Populate champion lineage.
   Warehouse promoted champion rows have `promotion_experiment_id=NULL`.
   Promotion paths are reconstructable, but the champion table should carry the
   direct promotion experiment id.

4. Produce final evidence refs.
   Both summaries remain `formal_ready=false`. A formal validation run should
   write final quality/runtime/failure artifacts and attach them through
   `final_evidence_refs`.

5. Separate referenced metrics from scratch metrics.
   Both campaigns contain unreferenced `v8_run*` metric files. Evidence
   manifests should either exclude scratch metrics by construction or record
   them in a separate artifact class.

## P1: CVRP Research-Surface Expansion

1. Fix singleton policy novelty.
   `C10_novelty` should not treat all modifications to
   `policies/search_policy.py` as duplicates. Add a semantic novelty signature
   for policy surfaces, such as changed function set, parameter direction, and
   intended mechanism.

2. Add more algorithm-level CVRP surfaces.
   Candidate surfaces:

   - neighborhood portfolio configuration;
   - destroy/repair mix;
   - acceptance/restart policy;
   - baseline/operator budget schedule;
   - construction seed or insertion policy;
   - staged search policy for small vs large instances.

3. Keep operator optimization as one surface.
   The conclusion is not to discard operator design. The conclusion is that
   operator design is a subset of heuristic algorithm design.

4. Improve CVRP context guidance.
   Proposal context should distinguish:

   - accepted moves but no aggregate win;
   - no accepted moves;
   - candidate timeout;
   - runtime regression without timeout;
   - verification/contract failure;
   - singleton policy blocked by novelty;
   - post-baseline surface likely exhausted.

## P1: Campaign Observability

1. Make code-generation timeout a first-class event.
   Warehouse had two LLM code timeouts. They are represented in summary rows
   and traces, but should also be consistently queryable from
   `experiment_events`.

2. Enrich contract-failure DB rows.
   Contract failures should include hypothesis id, failure detail, target file,
   and surface/action so audits do not need to reconstruct them from summaries.

3. Summarize async weight optimization state.
   Stale/discarded weight opt behavior is expected, but final summaries should
   explicitly list committed vs discarded revisions.

4. Add a closeout/readiness command.
   A dedicated command should answer:

   ```text
   did the run finish, are all metric refs complete, are final evidence refs
   present, are there residual branches, and is the campaign formal-ready?
   ```

## P2: Next Validation Sequence

After P0 repairs:

1. Run a short CVRP smoke with a policy-surface semantic novelty case.
2. Run a short warehouse smoke to ensure champion lineage still persists.
3. Run one dual short experiment with final evidence generation enabled.
4. Only then repeat long Sonnet 50-round experiments.

Expected acceptance for the next long run:

- both campaigns reach requested rounds or record explicit configured stop;
- no missing referenced metrics;
- runtime failures are visible in summary reason codes;
- promoted champion rows link directly to promotion experiments;
- final evidence refs are present;
- CVRP policy variants are not blocked merely because they edit the singleton
  policy file.
