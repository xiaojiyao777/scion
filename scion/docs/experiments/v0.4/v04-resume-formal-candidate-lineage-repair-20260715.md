# Resume Formal-Candidate Lineage Repair — 2026-07-15

## Verdict

The launcher had a deterministic multi-hop ownership defect. A first resume
moved `artifacts/formal_candidates/index.jsonl` from the copied campaign into
the new root's immutable resume snapshot. A second resume copied only that
root's `campaign/` subtree, so candidate metadata survived while the outer
snapshot index did not. The unlaunched expanded-validation root ending
`20260715T193404Z-claw` reproduced the failure and is superseded.

The repair is pushed at `94769f07`. It does not change Protocol, Decision,
solver limits, provider calls, or gate weight. It repairs launcher ownership
before an experiment can start.

## Correct ownership model

For every resume hop, the launcher now reads two possible trusted layers:

1. the source run root's inherited snapshot index, bound by its fixed manifest
   ref, source campaign identity, size, and SHA;
2. the source campaign's live index, representing candidates produced by that
   source invocation.

It validates and flattens those layers in ancestor-then-live order into one
new immutable index:

```text
NEW_ROOT/resume_snapshot/campaign/artifacts/formal_candidates/index.jsonl
```

It never restores inherited rows into
`NEW_ROOT/campaign/artifacts/formal_candidates/index.jsonl`. That live path is
reserved for candidates produced by the new invocation, preserving the
current-versus-cumulative accounting boundary.

The implementation is isolated in
`scion/scion/launcher/formal_candidate_lineage.py`; `resume.py` remains the
copy/quarantine/orchestration boundary.

## Fail-closed checks

Preparation now rejects:

- missing, duplicate, escaped, or mismatched snapshot refs;
- manifest/source-campaign mismatch or snapshot size/SHA tampering;
- malformed JSONL rows and invalid recorded/omitted status/ref combinations;
- noncanonical or formal-root-external artifact refs;
- candidate metadata that is missing, non-object, symlinked, or identity-
  inconsistent with its index row;
- conflicting ownership for either one artifact ref or one recorded candidate
  id;
- candidate metadata on disk that is not covered exactly by the trusted union.

Legacy recorded rows without `artifact_status`, legacy unbound rows, and
omitted rows remain readable. Omitted-row identity uses the recorder's
`artifact_omitted_reason`, so distinct omission reasons remain distinct while
exact duplicates deduplicate.

## Verification

- focused resume/lineage/postrun/launcher slice: `47 passed`;
- complete unit suite: `712 passed`;
- standard Scion suite: `1949 passed, 1 skipped`;
- compileall, Black check, and `git diff --check`: pass;
- two independent read-only reviews: no remaining P0/P1.

The real exact-validation source was prepared with the repaired code. Its two
historical v2 rows bind exactly to its two copied metadata files; the new union
contains both rows, the live index is absent, and postrun candidate integrity
returns `ok` with `inherited_candidates=2` and no orphan artifact.

## Compatibility boundary

Read-only historical scans found old roots whose metadata had already become
unindexed under the previous launcher. They now fail preparation instead of
silently losing ownership. Recovering one of those roots requires a separate,
explicit ancestry migration with evidence; the launcher will not infer an
index by scanning files.

The shared fixed-candidate replay CLI still expects a live index when called
directly on a campaign path. The active expanded-validation resume path does
not use that fallback: its branch evidence owns an existing candidate ref, and
the launcher/postrun path consumes the immutable snapshot correctly. A shared
read-only snapshot resolver remains follow-up robustness work, not a blocker
for this validation continuation.

## Next action

Create a clean detached runtime from the latest pushed revision, prepare a new
one-round continuation from the terminal exact-validation campaign, verify the
two-row inherited union and zero provider intent, then start `run.sh` exactly
once. The invocation must enter the preregistered 12-case expanded validation
with four seeds and 48 pairs, without a new Hypothesis or Code call.
