# External Proposal / Workspace Ingest

## Status

Implemented in this slice:

- `scion.external_ingest` manifest schema.
- Host-side conversion from external workspace, unified diff, or inline changes to
  Scion `HypothesisProposal` and `PatchProposal`.
- Canonical host-generated `content_after` files and unified diff audit.
- Host-materialized candidate workspace from the declared base champion.
- ContractGate validation for hypothesis and patch.
- Optional generic mock smoke and optional `external_proposal_ingest` lineage event.
- Resolved `safe_data_roots` artifact written outside candidate code under the
  ingest output and `.scion/external_ingest/workspace_manifest.json`.

Not implemented in this slice:

- Direct campaign-runner hook that continues from ingest into canary, screening,
  decision, and archive.
- Real problem-owned algorithm smoke invocation from the CLI.
- Promotion/decision from external text. External text remains tainted and only
  enters proposal/audit records.

## CLI

```bash
scion external-ingest path/to/external_manifest.yaml \
  --problem path/to/problem.yaml \
  --split path/to/split_manifest.yaml \
  --output-dir campaign/external_ingest \
  --campaign-dir campaign \
  --record-lineage \
  --mock-smoke
```

`--problem` is required because ContractGate must be authoritative. The base
workspace comes from `--base-workspace`, then `manifest.base_champion.workspace_path`,
then `problem.root_dir`.

## Manifest

```yaml
schema_version: scion.external_proposal.v1
hypothesis:
  hypothesis_text: "External hypothesis text."
  change_locus: dispatch_policy
  action: modify
  target_file: policies/dispatch.py
  predicted_direction: exploratory
  mechanism_changes:
    - id: external_dispatch_policy
      change_type: modify
source:
  type: workspace
  workspace_path: /abs/path/to/external/workspace
  changed_files:
    - policies/dispatch.py
base_champion:
  champion_id: champion_v1
  workspace_path: /abs/path/to/base/champion
  branch_id: optional_branch
  lineage_id: optional_lineage
provenance:
  external_agent: external-aps
  run_id: run-20260602
  source_uri: file:///experiment/root
declared_boundary:
  objective_digest: sha256:...
  constraint_digest: sha256:...
  problem_spec_digest: sha256:...
```

`source.type` may be `workspace`, `unified_diff`, or `inline`. Workspace and
unified-diff sources must declare `changed_files`; Scion reads those paths from
the external candidate after applying the diff or inspecting the workspace.

## Audit

The ingest host writes:

- `audit/canonical.diff`
- `audit/content_after/<path>.content_after`
- `audit/external_ingest_audit.json`
- `ingest_result.json`
- `split_manifest.resolved.yaml` when `--split` is supplied
- `workspaces/<ingest_id>/.scion/external_ingest/workspace_manifest.json`

The audit records provenance, declared objective/constraint boundary digests,
base lineage, resolved absolute `safe_data_roots`, canonical per-file hashes,
and the materialized workspace hash. External descriptions or external diffs are
not trusted as canonical evidence.

## Runner Hook Still Needed

The next integration point should accept `ingest_result.json` as a campaign
input and create a branch step whose proposal and patch are already known. That
hook should reuse the existing flow after `generate_code`:

1. ContractGate results from ingest may be reused only if the same problem spec,
   base snapshot hash, and patch hash match.
2. Verification and canary run against the host-materialized workspace.
3. Screening, safe feature extraction, deterministic decision, and archive use
   existing campaign services.
4. The external provenance and canonical diff refs are copied into lineage
   audit payloads, never into `DecisionFeatures`.

This keeps Scion core generic: problem-specific smoke/canary/verification stays
behind problem adapters or provider hooks.
