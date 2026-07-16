# v0.4 experiment retention cleanup audit — 2026-07-16

## Result

Three exact, retention-aware cleanup batches removed 279 roots under
`/home/clawd/research/scion-experiments`. The first two batches were
prepared-only. The third batch extended the same evidence protections to empty
roots, pre-Protocol infrastructure failures, duplicate local resume copies, and
two superseded prepared validation roots whose formal replacements remain.

| Batch | Roots | Deleted logical bytes | GiB | Scope |
|---|---:|---:|---:|---|
| batch-1 | 136 | 4,847,322,762 | 4.514 | old names containing `preflight` |
| batch-2 | 120 | 4,113,033,342 | 3.831 | old prepared/report-only roots with other names |
| batch-3 | 23 | 1,278,214,144 | 1.190 | empty, pre-Protocol failure, duplicate, or superseded |
| **Total** | **279** | **10,238,570,248** | **9.535** | exact roots without unique retained evidence |

Filesystem observations:

- before batch-1: 24,302,546,944 bytes available, 81% used;
- after batch-2: 34,316,902,400 bytes available, 73% used;
- immediately before batch-3: 33,868,734,464 bytes available, 73% used;
- after batch-3: 35,147,063,296 bytes available, 72% used;
- batch-3 observed available-space change: +1,278,328,832 bytes (1.191 GiB).

The filesystem delta is larger than the logical size sum because other
processes may allocate or release blocks concurrently. The auditable cleanup
quantity is the per-path logical-byte sum in the manifest.

## Prepared-only deletion predicate

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

## Batch-3 deletion predicate

Batch 3 first scanned active operating, planning, and experiment-report docs
and protected 73 exact roots. Every deleted path then passed all applicable
checks immediately before removal:

1. no live PID, `/proc` cwd, command line, or open-fd owner;
2. no `.git` directory or registered worktree;
3. no active-doc protection and no remaining repository reference, except that
   a duplicate root could be deleted only when its canonical source remained;
4. no unique Protocol result, effective new round, validation result, or
   promotion evidence;
5. one positive class was proven exactly: empty root, pre-Protocol
   infrastructure failure, premise-contradicted pre-Protocol signal, local
   resume with zero effective rounds and retained source evidence, or
   report-only prepared root superseded by an identified formal root.

The batch removed four empty roots, five old pre-Protocol infrastructure
failures, one premise-contradicted pre-Protocol signal root, eleven dead local
resume copies with zero effective rounds, and two superseded prepared
validation roots. It reduced the top-level experiment-root count from 887 to
864. This was not an age-, name-, or size-only deletion.

## Explicit retention

The cleanup did not remove:

- the live R11c root or any path found by the active-owner scan;
- current R6–R11c formal evidence used by TASK/current-state;
- baseline-strength Phase A/B/C evidence needed for later ALNS design;
- any root less than 48 hours old;
- any git runtime or worktree;
- any unique raw scientific evidence;
- any large historical matrix whose retention status remained ambiguous.

Batch 3 additionally rechecked that warehouse R2/R3, R6-R11c, Phase A/B,
open-control, formal validation/expanded roots, and each duplicate local
resume's canonical source still existed after deletion. R11c wrapper/campaign
PIDs 2892669/2892705 remained live and its root/runtime were untouched.

Ten old `status=prepared` roots lacking `prepared_run_manifest.v1.json` were
retained fail-closed (353,693,897 logical bytes total):

- `v04-cvrp-postpivot-resume-ready-{preparedstatus,healthcheck,inventory,coverage,brief}-1r-gpt55-*`;
- `v04-warehouse-v2-followup-ready-{preparedstatus,healthcheck,inventory,coverage,brief}-6r-gpt55-*`.

The live-owner scan at batch-1 time resolved only R11c paths, with PIDs 2892669,
2892705, and a transient solver child 2901041. Recent roots skipped during
batch-2 included the direct open-control root and two R6 validation roots.

The batch-3 gray manifest retains 23 exact roots totaling 685,924,047 current
apparent bytes. It includes missing-manifest prepared lineages, two referenced
infrastructure failures, two referenced pre-Protocol signal roots, and one
referenced one-round formal signal. These remain fail-closed pending explicit
evidence disposition:
[`v04-experiment-retention-cleanup-gray-20260716.tsv`](./v04-experiment-retention-cleanup-gray-20260716.tsv).

## Follow-up boundary

Future cleanup should repeat the same evidence-based classification and produce
another manifest. It must not infer deletion solely from age or directory size.
Large historical formal runs require a separate tracked-evidence inventory
before removal.
