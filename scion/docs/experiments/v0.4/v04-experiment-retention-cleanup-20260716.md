# v0.4 experiment retention cleanup audit — 2026-07-16

## Result

Two exact, retention-aware cleanup batches removed 256 prepared-only roots
under `/home/clawd/research/scion-experiments`.

| Batch | Roots | Deleted logical bytes | GiB | Scope |
|---|---:|---:|---:|---|
| batch-1 | 136 | 4,847,322,762 | 4.514 | old names containing `preflight` |
| batch-2 | 120 | 4,113,033,342 | 3.831 | old prepared/report-only roots with other names |
| **Total** | **256** | **8,960,356,104** | **8.345** | prepared-only, never launched, superseded |

Filesystem observations:

- before batch-1: 24,302,546,944 bytes available, 81% used;
- after batch-2: 34,316,902,400 bytes available, 73% used;
- observed available-space change: +10,014,355,456 bytes (9.327 GiB).

The filesystem delta is larger than the logical size sum because other
processes may allocate or release blocks concurrently. The auditable cleanup
quantity is the per-path logical-byte sum in the manifest.

## Deletion predicate

Every deleted path passed all of these checks immediately before removal:

1. top-level root was older than 48 hours;
2. `run_status.json` reported `status=prepared`;
3. PID, start, end, and exit lifecycle fields were null;
4. `prepared_run_manifest.v1.json` reported `report_only=true`;
5. campaign, scheduler, and promotion mutation flags were all false;
6. no `.git` directory or registered git worktree was present;
7. a `/proc` cwd/open-fd scan found no active owner;
8. the root was an iterative handoff/preflight/smoke preparation superseded by later code history or formal run roots.

These roots could contain copied source, baseline caches, readiness output, or
handoff material, but did not contain a launched formal experiment transaction.
Cleanup was path-exact and was not an age-only deletion.

The complete per-path record is in
[`v04-experiment-retention-cleanup-manifest-20260716.tsv`](./v04-experiment-retention-cleanup-manifest-20260716.tsv).

## Explicit retention

The cleanup did not remove:

- the live R11c root or any path found by the active-owner scan;
- current R6–R11c formal evidence used by TASK/current-state;
- baseline-strength Phase A/B/C evidence needed for later ALNS design;
- any root less than 48 hours old;
- any git runtime or worktree;
- any unique raw scientific evidence;
- any large historical matrix whose retention status remained ambiguous.

Ten old `status=prepared` roots lacking `prepared_run_manifest.v1.json` were
retained fail-closed (353,693,897 logical bytes total):

- `v04-cvrp-postpivot-resume-ready-{preparedstatus,healthcheck,inventory,coverage,brief}-1r-gpt55-*`;
- `v04-warehouse-v2-followup-ready-{preparedstatus,healthcheck,inventory,coverage,brief}-6r-gpt55-*`.

The live-owner scan at batch-1 time resolved only R11c paths, with PIDs 2892669,
2892705, and a transient solver child 2901041. Recent roots skipped during
batch-2 included the direct open-control root and two R6 validation roots.

## Follow-up boundary

Future cleanup should repeat the same evidence-based classification and produce
another manifest. It must not infer deletion solely from age or directory size.
Large historical formal runs require a separate tracked-evidence inventory
before removal.
