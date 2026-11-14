# CVRP M28 seen-bank qualification autonomous-continuation preregistration

**State:** `TERMINAL_STOPPED_RESOURCE_EXHAUSTED / VALID_INCOMPLETE / NOT_QUALIFIED`

**Label:**
`v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-20260824`

**Campaign root:**
`/home/clawd/research/scion-experiments/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-20260824`

**Frozen metadata-selection base:**
`6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1`

**Preparation and live carrier:**
`6b082e04878c74863b2cdcaff6e877e9ce9a75fe`

The Git revisions are ordinary source references, not identities, digests,
authorization or proof objects. M28 changed no production source. This
document, the three M28 YAML controls, the strict aggregate input, the exact
M27 history copy and provider-/solver-free replay were committed and
independently reviewed before launch. The command below remains the frozen
one-shot command; its explicit authorization has been consumed.

## Terminal result

The authorized command ran exactly once and exited 21. The preserved public
terminal is `stopped / execution_resource_exhausted`, with
`run_validity=valid_incomplete` and last execution outcome
`resource_exhausted / PROVIDER_CALL_CAP_EXHAUSTED` at `proposal_code`. It
scheduled four attempts but completed only one of the two requested formal
rounds. The terminal counters are one evaluated screening, two
`research_rejected` outcomes, one resource-exhausted outcome and zero unknown
outcomes. This is an ordinary valid-incomplete campaign, not the declared M28
qualification terminal.

The run consumed the exact 34/34 provider-call allowance: 25 H research turns,
eight C research turns and one independent C final decision. The safe
action-only H projections, grouped by scheduled attempt, were:

1. `read_source(source-0001) -> read_source(source-0010) ->
   read_source(source-0006) -> finalize_hypothesis ->
   read_history(history-0043) -> finalize_hypothesis ->
   read_history(history-0044) -> abstain`;
2. `read_source(source-0010) -> finalize_hypothesis ->
   read_history(history-0008) -> finalize_hypothesis`, accepted;
3. `read_source(source-0010) -> read_source(source-0004) ->
   read_source(source-0009) -> finalize_hypothesis ->
   read_history(history-0039) -> finalize_hypothesis`, accepted; and
4. `read_source(source-0006) -> finalize_hypothesis ->
   read_history(history-0043) -> search_source(source-0010) ->
   finalize_hypothesis -> read_history(history-0017) ->
   finalize_hypothesis`, accepted.

These are action/ref projections only; no provider response body is reproduced
here. The first path's `HYPOTHESIS_RESEARCH_ABSTAINED` classification was a
safe-public live observation. The terminal counters retain both research
rejections, but terminal `steps` and ordinary history each contain only three
rows and durably represent only one rejected row. The missing rejected row's
specific H reason therefore cannot be reconstructed from terminal-only
ordinary history.

The first accepted H had action `modify`. C proceeded
`revise -> revise -> test_patch -> ready -> finalize_patch`; the probe action
was observed, but its body remains tainted and is neither reproduced nor used
as evidence. Patch Contract, Verification and canary passed. Initial
screening then completed all `6/6` pairs valid with every failure class zero.
Case win/loss/tie was `1/1/1`, pair win/loss/tie was `2/1/3`, median
total-distance delta was `0.0` and CI was `[-2.5, 206.0]`. Protocol returned
`fail / SCREENING_FAIL_CASE_QUALITY`, and Decision returned
`continue_explore`. The candidate did not expand.

The second accepted H also had action `modify`; its C used four `revise`
turns, after which the host recorded
`research_rejected / PATCH_PROPOSAL_INVALID`. The fourth scheduled-attempt H
(the third accepted H) was accepted as `modify`, but the shared provider cap
was exhausted before any corresponding C trace could be dispatched. Thus
formal counts are initial screening `1`, expanded screening `0`, validation
`0` and frozen `0`; promotion and retained comparison are also zero.

Exactly 16 solver subprocesses ran serially with observed maximum concurrency
one: two Verification, two canary and twelve formal initial-screening
subjects. The interval from campaign-root birth
`2026-08-24T13:22:27.972508217Z` to terminal `status.updated_at`
`2026-08-24T13:41:30.552102Z` was `1142.579593783s` (about `1142.580s`). This
is a root-birth-to-status-publication interval, not complete shell lifetime or
a hardwall measurement; the 15,000-second hardwall was not reached.

At terminal there were three durable branch records: one `blocked_infra` from
the provider-cap stop and two `explore` branches. `active_slots` was
used/max/available `2/3/1`; these are logical branch slots, not live processes.
There was no `READY_VALIDATE` branch. One durable candidate workspace and one
artifact file in the `metrics` directory remain as evidence for the sole
evaluated candidate; scratch `workspaces`, `archive` and `champions` were
empty. Scoped campaign, solver, bubblewrap and prlimit process counts were zero
after exit, and the preserved campaign root remained mode `0700`.

M28 therefore does not satisfy `6/6 -> 24/24`, `pass`, `queue_validate`, the
two-screening-record carrier join or any later-stage condition. The conditional
M29 selector expired without materialization: no M29 identity, input bundle,
candidate carrier or launch is authorized.

Independent terminal review found no P0, one P1 design defect and one P2
observability defect. The frozen carrier audit incorrectly asserts that total
branch-record count equals active-branch count and both equal one. The intended
scientific requirement is uniqueness of the `READY_VALIDATE` branch; preserved
non-ready records can make that assertion a structural false negative in a
hypothetical otherwise-qualified run. It did not change this result: M28 had no
expanded screen, no pass, no `queue_validate` and zero `READY_VALIDATE`
branches before the carrier audit was relevant. The P2 is the missing ordinary
step/history row for the live-observed H abstention described above. Neither
finding upgrades or downgrades the scientific terminal, and neither permits a
retry, repair or M29 preparation.

The remaining scientific design, population, carrier predicate, conditional
selector, resource envelope and command are retained as the pre-launch frozen
record. Their prospective wording describes the design that governed the
consumed invocation; it is not current launch authority.

## Scientific question

Can Scion autonomously select and implement one further CVRP solver candidate
from complete ordinary M7--M27 evidence, while the generic nearest-history
audit continues to require candidate-specific evidence read/citation, and can
that exact verified candidate qualify for a later fixed-candidate formal funnel
by completing both of these stages on the declared seen bank?

1. Initial screening: three cases by the two old screening seeds, all `6/6`
   pairs valid, every failure class and fleet regression zero, Protocol
   `expand`, Decision `expand_screening`.
2. Expanded screening: the strict six-case superset by four seeds, all `24/24`
   pairs valid, every candidate/champion/shared/bilateral/subject failure and
   fleet regression zero, Protocol `pass`, Decision `queue_validate`.

The host supplies no mechanism, target file, action, patch, repair direction or
falsifier body. H chooses the candidate; C remains bound to the accepted H.
Contract, Verification and the problem-owned Protocol -> Safe Features ->
Decision chain retain authority. The optional sandboxed falsifier remains a
non-evidentiary C hint and nearest-history routing remains an evidence-routing
control rather than a novelty or quality gate.

M28 is an **adaptive seen-bank qualification**, not a fresh-population screen.
The six cases and old seeds are outcome-exposed through earlier candidates.
The two added expansion seeds were selected before the M28 candidate exists,
but that fact does not make the case population fresh, independent or suitable
for a generalization claim. M27-to-M28 is sequential, non-randomized and
non-causal.

## Why this is a new bounded experiment

M27 is terminal `completed / valid / requested_rounds_completed` at its
preserved, consumed root. Its exact candidate completed a `6/6` initial screen
and requested expansion, but expanded screening had two candidate-only
timeouts and only `10/12` valid pairs. Protocol failed case quality and
Decision abandoned for runtime failure. Validation, frozen, promotion and
retained comparison were zero.

M28 is neither a retry nor repair of that candidate. It has a new label, absent
root, a strict aggregate M27 observation, the two canonical M27 ordinary
records and a future candidate authored anew through H/C. The two extra seeds
increase expanded-stage feasibility coverage without changing cases, gates,
time limits or later-stage reservations. No M27 workspace, raw provider trace,
probe source or raw solver output is imported.

There is no automatic retry, resume, replacement, root reuse or M29 launch,
regardless of M28 outcome.

## Ordinary research context

The sole problem-owned research input is
`inputs/v04-cvrp-m28-m27-terminal-research-input.json`. Its first six
observations are exactly the ordered M27 input: M7, M18, M23, M24, M25 and M26.
Its seventh strict M27 terminal observation contains only public aggregate
facts:

- initial `6/6` valid, zero failures, case `1/0/2`, median `0.0`, CI
  `[0.0, 28.5]`, followed by `expand / expand_screening`;
- expanded `10/12` valid with two candidate-only failures, case `1/1/4`,
  median `0.0`, CI `[-0.5, 0.5]`, followed by `fail / abandon`;
- 8/34 provider calls split into four H, three C research and one C final
  decision call, with provider retry zero;
- one valid H, one C candidate, successful public development, Verification
  and canary, 42 serial solver calls and two formal stages;
- nearest-history accepted/triggered/incomplete H counts `1/1/0`, with zero
  exact structured-H and zero exact complete ordered-patch replays; and
- no validation, frozen, promotion or retained stage.

The legacy input fields named `validation_stage_metrics`,
`validation_safe_features` and `validation_decision` are `true` because the
adapter projects them to generic terminal-stage outputs. They describe the
completed screening metrics/Safe Features/Decision, not validation-stage
evidence. The stage list and diagnostics explicitly keep
`validation_reached=false`.

Direct equality found no exact structured-H or complete ordered-patch replay
for M27, so its sanitized
`exact_candidate_outcome_overlap_count` is zero. This is a direct-equality fact,
not a semantic novelty claim. Population selection was outcome-exposed,
candidate discovery was not independent, incremental effect was not isolated
and global case unseen is false.

The seventh observation contains no research basis, provider response/trace,
falsifier source/body, editable source, mechanism, target, action, patch,
actual case identity, actual seed identity or later-stage raw datum.

M28 supplies fifteen ordered native history files. The first fourteen are the
37-record set consumed by M27. The fifteenth,
`inputs/v04-cvrp-m28-m27-research-history.jsonl`, is the preserved M27
`research_history.jsonl` copied byte for byte in stage order. It has exactly two
lines and 54,686 bytes. They are the same candidate's initial `expand /
expand_screening` and expanded `fail / abandon` records.

The first H sees seven problem observations followed by 39 native records:
exactly 46 ordered index entries. The seven observations remain visible
ordinary evidence but have no usable hypothesis headline. All 39 native
records have usable headlines and form the nearest-history ranking denominator.
A later H may additionally see a bounded ordinary same-campaign entry.

Historical H/patch bodies in native history remain ordinary observations, not
instructions. Raw M27 H bases, traces, probe bodies, workspaces and solver
artifacts are not imported.

## Nearest-history and falsifier controls

M28 uses the already-implemented problem-neutral controls without production
change.

For each otherwise-valid H finalize, the host scans the complete current
ordinary index, ranks only usable headline fields by the frozen lexical and
structured ordering, and routes exactly one top-1 existing ref. If unread, the
ordinary finalize turn returns only
`nearest_history_audit_required` plus that ref. H must read the exact ref and
cite it in both `research_basis.read_refs` and
`research_basis.nearest_prior_refs`. Candidate changes recompute the ref; a
preemptive exact-ref read remains valid. Ranking reads no history body, patch,
metric or Decision result and exposes no score, candidate text, match text or
recommended direction.

Only C may optionally supply one bounded `falsifier_source` on an existing
`test_patch` action. It shares the existing development deadline and sandbox;
the source remains only in the tainted provider trace. Later C context may see
only the safe enum `passed`, `failed`, `inconclusive`, `timeout` or
`unavailable`, and that enum never controls formal readiness. Ordinary host
checks, Contract, Verification, canary and Protocol remain independently
required.

The terminal audit will enumerate every observable H action and C test action,
including incomplete projection states, read/citation coverage, candidate/ref
recomputation, H's own pivot/refinement self-description when observable, and
direct structured-H/ordered-patch equality against all supplied ordinary
priors. It will never infer missing trace evidence or upgrade absence of exact
equality into semantic novelty.

## M28 population and metadata-only change

The M28 split is value-equal to M24 except its version string. Initial cases
are exactly:

- `cvrplib/B/B-n57-k7.vrp`
- `cvrplib/P/P-n60-k15.vrp`
- `cvrplib/X/X-n261-k13.vrp`

Expanded screening strictly contains those three and adds exactly:

- `cvrplib/A/A-n53-k7.vrp`
- `cvrplib/X/X-n167-k10.vrp`
- `cvrplib/X/X-n411-k19.vrp`

Initial seeds are the old `4358`, `1868`. Expanded screening uses those plus
the pre-frozen new seeds `10684`, `14577`, in that ledger order. The protocol
is value-equal to M24 except its version and
`screening.expand_n_seeds: 4`; `screening.n_seeds` stays `2`. Gates, priority
order, case counts, runtime rules and `require_expanded_for_pass=true` are
unchanged.

The three coherent M28 controls are:

- `inputs/v04-cvrp-m28-seen-bank-qualification-protocol.yaml`
- `inputs/v04-cvrp-m28-seen-bank-qualification-split.yaml`
- `inputs/v04-cvrp-m28-seen-bank-qualification-seeds.yaml`

The split and ledger retain M24's validation and frozen identities as
schema-valid reserved controls. `--rounds 2` makes them unreachable. M28 does
not open, parse, evaluate or otherwise consume the reserved raw cases or their
outcomes.

### Reproducible selection of the two new seeds

Seed selection uses only metadata frozen at base
`6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1` and salt
`v04-cvrp-m28-seen-bank-seed-expansion-20260824|seeds-v1`.

1. Enumerate the base's tracked paths as `git ls-files -z` would. Retain paths
   whose case-folded name contains `cvrp`, plus exact `scion/TASK.md`.
2. For each retained `.json`, parse JSON; for each `.yaml`/`.yml`, parse YAML.
   Recursively collect every integer below any ancestor mapping key containing
   `seed` case-insensitively, excluding booleans. If the basename itself
   contains `seed`, collect every integer in the parsed object.
3. Independently scan every text line containing `seed` case-insensitively and
   collect decimal integers matching
   `(?<![A-Za-z0-9])([0-9]{1,9})(?![A-Za-z0-9])`.
4. Union the values. The frozen scan has 2,784 distinct values, 73 within
   integer domain `[10000, 19999]`.
5. For every non-excluded domain integer `s`, rank the tuple
   `(sha256(utf8(salt) + NUL + ascii_decimal(s)).digest(), s)` ascending.
   Select the first two, without fallback or resalting.

The selected values and raw digest bytes rendered as hex are:

- `10684` ->
  `0000d16694b890e464f92532b1b74a077ec559bb959a41b58a9ae55e9d4db5cd`
- `14577` ->
  `0008d3a0ec70657cd8cfe8e6af5c84b8b9da45df94adc802bedd085e1c9467f6`

The digest is only a deterministic ranking calculation. It is not an input
identity, acceptance check, receipt or authorization artifact.

## Legal trajectories and qualification terminal

`--rounds 2` counts completed formal Protocol stages, not H/C attempts.

- If candidate 1 receives `expand_screening`, stage 2 must reuse that exact
  verified branch on the expanded matrix. No second H or C is called.
- If candidate 1 returns to exploration after an evaluated initial stage, a
  later H/C may consume remaining provider resources, but two initial screens
  cannot satisfy M28 qualification.
- Contract, Verification, research rejection or canary veto does not count as
  a formal stage. Provider/transport error, resource exhaustion, interrupt,
  comparator-incomplete evidence, other `NOT_EVALUATED`, unknown outcome or an
  evaluated result without formal evidence stops the invocation.

The sole qualification result is
`QUALIFIED_FOR_FIXED_CANDIDATE_FUNNEL`, interpreted from the ordinary terminal
artifacts after completion. It requires one exact H/C candidate to satisfy both
stage conditions in the scientific question, exact initial and expanded
case/seed coverage, all `30/30` formal pairs across the two stages valid,
zero failures of every class, zero fleet regressions, and the exact Protocol /
Decision progression `expand -> expand_screening -> pass -> queue_validate`.
Because the already-frozen fixed-funnel driver evaluates only action `modify`,
qualification additionally requires the accepted H action to be `modify`, a
nonempty actual B0-to-candidate changed-file set, and identical complete
ordinary-source file sets. An M28 `create_new` result remains ordinary M28
evidence but cannot qualify and cannot authorize M29.

`30/30` is the sum of the two distinct stage matrices (`6 + 24`); the expanded
matrix intentionally re-evaluates the three initial cases and two old seeds.
It is not a claim of 30 unique case-seed cells.

Any other terminal is preserved but is not qualified. In particular, an
expanded quality pass with any failed pair, an incomplete comparator, a
different Decision, two independently screened candidates, or shell exit zero
without the exact artifacts cannot qualify. M28 itself never executes
validation, frozen, promotion or retained comparison.

## Exact post-terminal candidate carrier audit

`queue_validate` is not itself sufficient to identify an M29 source. The
following provider-/solver-free audit is mandatory after an otherwise positive
M28 terminal and before any M29 identity or external input is materialized. It
is a future, separately reviewed M29 preparation action, not a tail step of the
M28 live command.

The current lifecycle has no initial `champions/v1` snapshot: initial v1 is the
declared production package and `accept_candidate` replaces and cleans the
mutable branch workspace. Therefore the only frozen carrier rule is:

1. mechanically materialize the exact 99 tracked ordinary files under
   `scion/scion/problems/cvrp` from base
   `6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1` as B0;
2. require exactly one terminal `READY_VALIDATE` branch, the same branch in
   `last_result` and both screening records, and exactly one durable direct
   child `candidate_workspaces/candidate-*`;
3. preserve any legal pre-formal rejection records, require summary/history
   length and order alignment, then select exactly two screening-aligned
   canonical records on the final branch. Those two must have byte/value-equal
   H and complete ordered patch, with H action `modify`, every change action
   `modify`, and identical initial/expanded selected-surface and candidate
   evidence;
4. apply that one canonical ordered patch mechanically to scratch B0 and
   require its complete ordinary-source path/byte projection to equal the
   actual durable candidate. Runtime-derived `__pycache__`, `.pytest_cache`
   and `.pyc` entries are not source and use the fixed-funnel driver's existing
   projection rule; symlinks and other non-regular entries always fail;
5. mechanically recompute the editable-source digest and require equality to
   the sole branch's `current_code_hash` only as a consistency check. Direct
   complete path/byte equality, not the digest, is source authority.

This frozen read-only audit is executable from the repository's `scion/`
directory after M28 terminates:

```bash
env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B - <<'PY'
import json
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from run_fixed_candidate_funnel import _source_bytes
from scion.core.paths import normalize_relative_patch_path
from scion.core.research_history import load_research_histories
from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.runtime.workspace import WorkspaceMaterializer

BASE = "6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1"
REPOSITORY = Path("/home/clawd/research/or-autoresearch-agent")
PREFIX = "scion/scion/problems/cvrp"
CAMPAIGN = Path(
    "/home/clawd/research/scion-experiments/"
    "v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-20260824"
)
EXPECTED_CASES = (
    "cvrplib/B/B-n57-k7.vrp",
    "cvrplib/P/P-n60-k15.vrp",
    "cvrplib/X/X-n261-k13.vrp",
    "cvrplib/A/A-n53-k7.vrp",
    "cvrplib/X/X-n167-k10.vrp",
    "cvrplib/X/X-n411-k19.vrp",
)
EXPECTED_SEEDS = (4358, 1868, 10684, 14577)


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)


status = load_json(CAMPAIGN / "status.json")
summary = load_json(CAMPAIGN / "campaign_summary.json")
run = status["run_result"]
assert run["status"] == "completed"
assert run["stop_reason"] == "requested_rounds_completed"
assert run["requested_rounds"] == run["evaluated_rounds"] == 2
assert run["run_validity"] == {"valid": True, "status": "valid", "reason": "valid"}
assert run["protocol_stage_counts"] == {"screening": 2, "validation": 0, "frozen": 0}
assert run["unknown_outcome_count"] == 0
assert summary["run_result"] == run

branches = status["branches"]
assert len(branches) == status["n_active_branches"] == 1
branch = branches[0]
assert branch["state"] == "ready_validate"
branch_id = branch["id"]
assert status["last_result"]["branch_id"] == branch_id
assert status["last_result"]["decision"] == "queue_validate"
assert summary["branches"] == branches

steps = summary["steps"]
history = load_research_histories(
    (CAMPAIGN / "research_history.jsonl",), expected_problem_id="cvrp"
)
assert len(steps) == len(history) == status["n_steps"]
for step, record in zip(steps, history, strict=True):
    projected_h = {
        "text": record["hypothesis"]["text"],
        "action": record["hypothesis"]["action"],
        "change_locus": record["hypothesis"]["change_locus"],
        "target_file": record["hypothesis"]["target_file"],
    }
    assert step["hypothesis"] == projected_h
    execution = step["execution_outcome"]
    assert record["outcome"]["outcome"] == execution["outcome"]
    assert record["outcome"]["reason_code"] == execution["reason_code"]
    assert (record["decision"]["value"] if record["decision"] else None) == step["decision"]
    assert (record["protocol"] is not None) == (step.get("protocol_result") is not None)

formal_indexes = [
    index
    for index, step in enumerate(steps)
    if (step.get("protocol_result") or {}).get("stage") == "screening"
]
assert len(formal_indexes) == 2
formal_steps = [steps[index] for index in formal_indexes]
formal_history = [history[index] for index in formal_indexes]
assert [step["branch_id"] for step in formal_steps] == [branch_id, branch_id]
assert [step["decision"] for step in formal_steps] == [
    "expand_screening",
    "queue_validate",
]
assert [step["protocol_result"]["gate_outcome"] for step in formal_steps] == [
    "expand",
    "pass",
]
assert [step["protocol_result"]["case_ids"] for step in formal_steps] == [
    list(EXPECTED_CASES[:3]),
    list(EXPECTED_CASES),
]
assert [step["protocol_result"]["seed_set"] for step in formal_steps] == [
    list(EXPECTED_SEEDS[:2]),
    list(EXPECTED_SEEDS),
]
for step, expected_pairs in zip(formal_steps, (6, 24), strict=True):
    protocol = step["protocol_result"]
    assert protocol["stage"] == "screening"
    assert protocol["total_pairs"] == protocol["attempted_pairs"] == expected_pairs
    assert protocol["valid_pairs"] == expected_pairs
    for field in (
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
        "shared_failed_pairs",
        "bilateral_failed_pairs",
    ):
        assert protocol[field] == 0
    fleet = next(item for item in protocol["metric_stats"] if item["metric_name"] == "fleet_violation")
    assert fleet["median_delta"] == fleet["ci_low"] == fleet["ci_high"] == 0

assert [record["decision"]["value"] for record in formal_history] == [
    "expand_screening",
    "queue_validate",
]
assert [record["protocol"]["evidence"]["protocol_outcome"]["gate_outcome"] for record in formal_history] == [
    "expand",
    "pass",
]
assert formal_history[0]["hypothesis"] == formal_history[1]["hypothesis"]
assert formal_history[0]["patch"] == formal_history[1]["patch"]
assert formal_history[0]["hypothesis"]["action"] == "modify"
surfaces = [step["protocol_result"]["selected_surface"] for step in formal_steps]
assert surfaces == [formal_history[0]["hypothesis"]["change_locus"]] * 2

candidate_parent = CAMPAIGN / "candidate_workspaces"
children = list(candidate_parent.iterdir())
assert len(children) == 1
candidate = children[0]
assert candidate.name.startswith("candidate-") and candidate.is_dir() and not candidate.is_symlink()
for path in (candidate, *candidate.rglob("*")):
    mode = path.lstat().st_mode
    assert not stat.S_ISLNK(mode)
    assert stat.S_ISDIR(mode) or stat.S_ISREG(mode)
    assert mode & 0o222 == 0

with tempfile.TemporaryDirectory(prefix="m28-carrier-audit-") as temporary:
    temp = Path(temporary)
    baseline = temp / "baseline"
    baseline.mkdir()
    raw = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", BASE, "--", PREFIX], cwd=REPOSITORY
    )
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, _object = metadata.decode("ascii").split()
        tracked = raw_path.decode("utf-8")
        assert kind == "blob" and mode in {"100644", "100755"}
        assert tracked.startswith(PREFIX + "/")
        entries.append(tracked)
    assert len(entries) == len(set(entries)) == 99
    for tracked in entries:
        target = baseline / tracked.removeprefix(PREFIX + "/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            subprocess.check_output(["git", "show", f"{BASE}:{tracked}"], cwd=REPOSITORY)
        )
    assert len(_source_bytes(baseline)) == 99

    changes = formal_history[0]["patch"]["changes"]
    assert changes and all(change["action"] == "modify" for change in changes)
    changed_files = [change["file_path"] for change in changes]
    assert len(changed_files) == len(set(changed_files))
    rebuilt = temp / "rebuilt"
    shutil.copytree(baseline, rebuilt)
    for change in changes:
        canonical = normalize_relative_patch_path(change["file_path"])
        assert canonical == change["file_path"]
        target = (rebuilt / canonical).resolve()
        assert target.is_relative_to(rebuilt.resolve())
        assert target.is_file() and not target.is_symlink()
        target.write_bytes(change["source"].encode("utf-8"))

    base_source = _source_bytes(baseline)
    rebuilt_source = _source_bytes(rebuilt)
    candidate_source = _source_bytes(candidate)
    assert set(base_source) == set(rebuilt_source) == set(candidate_source)
    assert len(candidate_source) == 99
    assert rebuilt_source == candidate_source
    actual_changed = sorted(
        path for path in base_source if base_source[path] != candidate_source[path]
    )
    assert actual_changed == sorted(changed_files)
    assert actual_changed

    problem = load_problem_spec_v1_from_yaml(baseline / "problem-v1.yaml")
    materializer = WorkspaceMaterializer(
        str(temp / "hash-check"),
        frozen_patterns=frozenset(problem.search_space.frozen),
        editable_patterns=problem.search_space.editable,
    )
    current_code_hash = branch["current_code_hash"]
    assert isinstance(current_code_hash, str) and re.fullmatch(r"[0-9a-f]{64}", current_code_hash)
    assert materializer.compute_code_hash(str(candidate)) == current_code_hash

print(json.dumps({
    "status": "QUALIFIED_CARRIER",
    "branch_id": branch_id,
    "selected_surface": surfaces[0],
    "changed_files": actual_changed,
    "ordinary_source_files": 99,
}, sort_keys=True))
PY
```

Missing/multiple branches or workspaces, non-`modify` action, a duplicate
changed-file path or empty patch, source-set change, selected-surface mismatch,
non-regular entry, reconstruction mismatch or digest inconsistency is
interpreted as `QUALIFICATION_CARRIER_UNAVAILABLE`. M28 is then preserved as
ordinary seen-bank evidence but is not qualified; M29 selection and
materialization are forbidden. There is no human candidate choice, patch
repair, alternate reapplication, workspace substitution or fallback.

Only after this audit passes may an independently authorized M29 preparation
copy the exact 99-file base projection to external `baseline/` and the exact
99-file durable-workspace projection to external `candidate/`, verify both
copies again by complete path/byte equality, and make both read-only. The exact
mechanically observed `changed_files` list supplies every future
`--changed-file`; the common accepted `change_locus`/`selected_surface`
supplies future `--selected-surface`. Neither value may be chosen manually.
The fixed-funnel driver then makes its own private stable snapshots.

## Candidate-independent conditional M29 selector

The future formal selector is frozen now, before any M28 candidate or outcome
exists. It is a conditional rule only. No M29 case or seed identity is
calculated, printed, written or supplied to H/C during M28. The rule may be
materialized once, in a separate reviewed M29 input bundle, only if M28 reaches
the sole qualification result above. Otherwise it expires without selection.

### Candidate pool and case rule

The selector base is `6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1`. The
candidate case pool is the exact union of
`validation` and `frozen` from only these three files:

- `inputs/v04-cvrp-m19-fresh-development-split.yaml`;
- `inputs/v04-cvrp-m20-frontier-development-split.yaml`;
- `inputs/v04-cvrp-m22-provider-recovery-development-split.yaml`.

The corresponding `validation` and `frozen` fields in
`v04-cvrp-m19-fresh-development-seeds.yaml`,
`v04-cvrp-m20-frontier-development-seeds.yaml` and
`v04-cvrp-m22-provider-recovery-development-seeds.yaml` must contain 12
distinct reserve seeds. All cases declared
by `inputs/v04-cvrp-m21-strict-expansion-development-split.yaml` and the
`validation`/`frozen` reserve in
`inputs/v04-cvrp-m24-autonomous-direction-research-development-split.yaml` are
exclusion sets; any overlap is a preparation failure. M24 validation/frozen
cases and the matching M24 seed fields remain fixed for M29's respective stages
and are not members of its screening or retained selector pool.

Canonicalize each raw pool string as
`raw.strip().replace('\\', '/')`, then `PurePosixPath(...).as_posix()`. Require
a relative path under `cvrplib/`, no `.` or `..` segment, and basename full
match `^(A|B|P|X)-n([1-9][0-9]*)-k([1-9][0-9]*)\.vrp$`. Deduplicate by exact
canonical relative path. The post-exclusion pool must have exactly 18 cases,
families `A=3, B=1, P=3, X=11`, and M24 time bands
`30s=7, 45s=2, 60s=5, 90s=3, 120s=1`. Each `.vrp` and same-stem `.sol` must be
regular non-symlinks and load through the production parser when M29 is
materialized; M28 does not open them.

Rank a case by
`(sha256(utf8(case_salt) + NUL + utf8(relative_path)).digest(), relative_path)`
ascending, where `case_salt` is
`v04-cvrp-m29-fixed-candidate-full-funnel-20260824|cases-v1`.

Select one minimum in each screening stratum, in order:

1. family A, dimension 20--100;
2. family B, dimension 20--100;
3. family P, dimension 20--100;
4. family X, dimension 101--200;
5. family X, dimension 201--350;
6. family X, dimension 351--700.

Remove those six, then select one minimum in each retained stratum, in order:

1. union of families A/B/P, dimension 20--100;
2. family X, dimension 201--350;
3. family X, dimension 351--700.

### M29 seed rule

Use salt
`v04-cvrp-m29-fixed-candidate-full-funnel-20260824|seeds-v1` and integer domain
`[20000, 39999]`. Apply the exact M28 tracked-seed scan above at base
`6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1`, additionally excluding M28 seeds
`10684`, `14577` and every M24 seed. Rank each remaining integer by the same
`(raw_digest, integer)` tuple.
The first four become screening seeds, the next two retained seeds and the
seventh the strict-canary seed. M24's fixed validation/frozen seeds remain
unchanged.

Any insufficient stratum, duplicate, overlap, aggregate mismatch, parser or
companion failure terminates M29 preparation. There is no fallback, resalting,
substitution, extra candidate, case/seed addition or alternate population.

The M28 provider-/solver-free replay performs a metadata-only feasibility
check now, without ranking or recording any selected case identity and without
opening `.vrp` or `.sol` content. It mechanically requires the 18-case/12-seed
source inventories, family/time-band aggregates, M21 and M24 exclusions, all
six screening strata nonempty, and enough members that removing one screen
case from each overlapping stratum still leaves all three retained strata
nonempty. This prevents an otherwise positive M28 terminal from discovering
that the already-frozen conditional selector is structurally impossible.

### Frozen M29 driver, sources and control derivation

If and only if the exact carrier audit passes, the only future live entry is
the already-tracked `scion/run_fixed_candidate_funnel.py`. Its action remains
the driver's fixed `modify`; provider, H, C, patch generation, Contract and
Verification are zero. The original comparator at screening, validation,
frozen and retained is the same exact B0 materialized from base
`6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1`. The candidate is only the sole
qualified M28 durable-workspace source projection. Retained never compares to
a promoted or intervening champion.

The future M29 Protocol is mechanically derived from the tracked M28 Protocol.
Only these Protocol fields may differ:

- `version` becomes the future M29 bundle version;
- `screening.priority_case_ids` becomes the first three cases in the six-case
  screening selector result, preserving selector order;
- `canary.seeds` becomes the seventh selector seed.

Every other Protocol value, including aggregation, all screening/validation/
frozen counts, expansion requirements, gates, runtime ratios and complete
time-limit rules, must be value-equal to M28. The M29 main split may differ
from M28 only in `version`, its sole external `safe_data_roots` value and the
six selector-produced `screening` paths; `validation`, `frozen` and `canary`
remain value-equal to M28/M24. The main seed ledger may differ only in
`version`, the four selector-produced `screening` seeds and the selector-
produced `canary`; its validation/frozen fields remain value-equal to M28/M24.

The separately generated retained split has the same M29 version and sole
external safe data root, empty screening/validation/canary arrays and exactly
the three selector-produced retained paths in `frozen`. Its retained seed
ledger has that version, empty screening/validation/canary arrays and exactly
the next two selector seeds in `frozen`. The driver arguments are fixed at
fallback `30s`, timeout communicate guard `15s`, outer hardwall `8000s`, memory
`4096 MB`; `--changed-file` and `--selected-surface` come only from the carrier
audit above. Driver source, threshold, control, comparator, source, ordering or
argument differences outside this whitelist fail M29 preparation closed.

The conditional M29 maximum is 86 serial solver subprocesses: strict canary 2,
screening 48, M24 validation 12, M24 frozen 12 and retained 12. Nominal seconds
are `20 + 2280 + 720 + 1080 + 720 = 4820`; adding the runner's `86 * 15 =
1290` pre-kill communicate guards gives `6110`. That is accounting at dispatch,
not a strict elapsed bound. Conservatively adding the runner's possible `5s`
post-timeout kill wait and `1s` output-drain wait for every subprocess gives
`6110 + 86 * 6 = 6626`, leaving `1374s` under the `8000s` hardwall. This
explicitly includes the strict canary; an earlier draft arithmetic of
`4800 / 6090` omitted its 20 nominal subject-seconds and is not the frozen
bound.

Even a positive M29 would support only the exact fixed-candidate funnel claim
allowed by its future preregistration. Freezing this selector before candidate
existence makes population choice outcome-blind relative to that exact
candidate, but does not make historically reserved cases globally unseen or
establish independent discovery, isolated mechanism causality or global CVRP
generalization.

## M28 resource envelope and typed stops

The unchanged M11 research limits permit at most eight H turns, eight C
research turns, one independent C final decision per H/C attempt and zero
through three count-consuming `test_patch` actions per C session. Provider SDK
retry is zero. Nearest-history routing consumes an ordinary H turn and adds no
call allowance.

The independently recomputed conservative envelope is:

- provider calls `<=34`; H timeout `120s`, C research/final timeout `240s`;
- structured-provider timeout `<=7080s`;
- public development work, including optional probes, `<=450s`;
- Verification pytest `<=480s`;
- Protocol/Safe-Feature/Decision formal stages `<=2`;
- serial solver subprocesses `<=72`: Verification `8`, canary `4`, formal
  screening `60`;
- formal nominal seconds `480 + 2280 = 2760` for initial and expanded stages;
- solver nominal subject-seconds `<=3040`; adding the `15s` pre-kill
  communicate guard per subprocess gives dispatch accounting `<=4120s`, not a
  strict elapsed bound;
- all known dispatch-accounted work `<=12130s`
  (`7080 + 450 + 480 + 4120`);
- conservatively adding the runner's possible `5s` post-timeout kill wait and
  `1s` output-drain wait for all 72 subprocesses gives solver elapsed
  `<=4120 + 72 * 6 = 4552s`;
- all known conservative elapsed work `<=12562s`
  (`7080 + 450 + 480 + 4552`);
- outer hardwall `15000s`, leaving `2438s`; solver concurrency `1`.

The component maxima are deliberately conservative and need not co-occur.
Nothing in the metadata-only seed expansion changes provider, development or
Verification maxima.

Provider-cap exhaustion is typed `resource_exhausted /
PROVIDER_CALL_CAP_EXHAUSTED` before another dispatch. H transcript/turn/result
exhaustion and provider-balance exhaustion stop the invocation. C test/time
exhaustion remains bounded tool feedback; C transcript/turn/result exhaustion
becomes `RESEARCH_REJECTED` and may move to another H only inside the same
remaining envelope. Outer hardwall exit 124 terminates children. Shell exit
zero alone is not scientific success.

## Claim boundary

1. **Framework:** observable H/C, nearest-history, optional-probe, Contract,
   Verification and formal routing may support bounded framework claims only.
2. **Research direction:** accepted H basis, citations, C alignment and exact
   replay audit support descriptive analysis only. They do not establish a
   causal research improvement.
3. **Algorithm:** complete paired Protocol results support candidate-versus-
   champion description only on the outcome-exposed M28 bank. The sole positive
   M28 claim is qualification to materialize the separately governed M29
   fixed-candidate funnel.

No M28 result is fresh-population evidence, confirmation, generalization,
validation, frozen success, promotion, retained improvement, production
readiness or v0.4 completion.

## Frozen preflight and one-shot command

Preparation requires a clean tracked worktree/index after the carrier commit,
no production-source difference from base
`6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1`, all named inputs and
tests tracked, the preserved M27 root readable, the M28 root absent, functional
bubblewrap/prlimit, provider metadata available and no concurrent Scion or
candidate run. Provider-/solver-free tests confer mechanical evidence only.

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
git diff --quiet
git diff --cached --quiet
test "$(git rev-parse --show-toplevel)" = /home/clawd/research/or-autoresearch-agent

git diff --quiet 6d8b53a56b056c71420d8a35b7d34b3f3ab8e5f1 HEAD -- \
  ':(top)scion/scion' ':(top,exclude)scion/scion/tests'
test -z "$(git status --porcelain=v1 --untracked-files=all -- \
  scion/problems/cvrp)"
test -z "$(git ls-files --others --exclude-standard -- \
  ':(top)scion/scion')"

for INPUT in \
  docs/experiments/v0.4/inputs/v04-cvrp-m28-seen-bank-qualification-protocol.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m28-seen-bank-qualification-split.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m28-seen-bank-qualification-seeds.yaml \
  docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  docs/experiments/v0.4/inputs/v04-cvrp-m28-m27-terminal-research-input.json \
  docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m21-m20-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m22-m21-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m24-m22-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-research-history.jsonl \
  docs/experiments/v0.4/inputs/v04-cvrp-m28-m27-research-history.jsonl \
  scion/tests/fixtures/m28_seen_bank_qualification_replay.json \
  scion/tests/unit/core/test_m28_seen_bank_qualification_replay.py \
  docs/experiments/v0.4/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-preregistration-20260824.md
do
  git ls-files --error-unmatch "$INPUT" >/dev/null
done

M27_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-m27-nearest-history-audit-autonomous-continuation-20260821/research_history.jsonl
M28_HISTORY=docs/experiments/v0.4/inputs/v04-cvrp-m28-m27-research-history.jsonl
test -f "$M27_HISTORY"
cmp -s "$M27_HISTORY" "$M28_HISTORY"
test "$(wc -l < "$M28_HISTORY")" -eq 2
test "$(wc -c < "$M28_HISTORY")" -eq 54686

M28_CAMPAIGN_DIR=/home/clawd/research/scion-experiments/v04-cvrp-m28-seen-bank-qualification-autonomous-continuation-20260824
test ! -e "$M28_CAMPAIGN_DIR"
test -x /usr/bin/bwrap
test -x /usr/bin/prlimit

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B - <<'PY'
from pathlib import Path

import scion
import scion.cli.commands.init_run as init_run
import scion.config.problem as config_problem
import scion.core.research_history as research_history
import scion.proposal.hypothesis_research_session as hypothesis_session
import scion.protocol.experiment as protocol_experiment
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.code_research_limits import load_code_research_limits
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml

project = Path("/home/clawd/research/or-autoresearch-agent/scion")
package = (project / "scion").resolve()
assert {Path(origin).resolve() for origin in scion.__path__} == {package}
for module in (
    init_run,
    config_problem,
    research_history,
    hypothesis_session,
    protocol_experiment,
):
    origin = Path(module.__file__).resolve()
    assert origin.is_relative_to(package), (module.__name__, origin)

inputs = project / "docs/experiments/v0.4/inputs"
history_names = (
    "v04-cvrp-m10-m9-research-history.jsonl",
    "v04-cvrp-m11-m10-research-history.jsonl",
    "v04-cvrp-m12-m11-research-history.jsonl",
    "v04-cvrp-m13-m12-research-history.jsonl",
    "v04-cvrp-m14-m13-research-history.jsonl",
    "v04-cvrp-m15-m14-research-history.jsonl",
    "v04-cvrp-m16-m15-research-history.jsonl",
    "v04-cvrp-m19-m16-research-history.jsonl",
    "v04-cvrp-m20-m19-research-history.jsonl",
    "v04-cvrp-m21-m20-research-history.jsonl",
    "v04-cvrp-m22-m21-research-history.jsonl",
    "v04-cvrp-m24-m22-research-history.jsonl",
    "v04-cvrp-m26-m25-research-history.jsonl",
    "v04-cvrp-m27-m26-research-history.jsonl",
    "v04-cvrp-m28-m27-research-history.jsonl",
)
research_input = init_run._load_research_input(
    inputs / "v04-cvrp-m28-m27-terminal-research-input.json"
)
prior_input = init_run._load_research_input(
    inputs / "v04-cvrp-m27-m26-terminal-research-input.json"
)
legacy_problem = config_problem.ProblemSpec.from_yaml(
    str(project / "scion/problems/cvrp/problem.yaml")
)
problem_v1 = load_problem_spec_v1_from_yaml(project / "scion/problems/cvrp/problem-v1.yaml")
problem_spec = legacy_problem_spec_from_v1(problem_v1)
histories = init_run._load_research_histories(
    [inputs / name for name in history_names],
    problem_spec=problem_spec,
)
limits = load_code_research_limits(inputs / "v04-cvrp-m11-code-research-limits.json")
protocol = ProtocolConfig.from_yaml(
    inputs / "v04-cvrp-m28-seen-bank-qualification-protocol.yaml"
)
split = SplitManifest.from_yaml(
    inputs / "v04-cvrp-m28-seen-bank-qualification-split.yaml"
)
seeds = SeedLedgerConfig.from_yaml(
    inputs / "v04-cvrp-m28-seen-bank-qualification-seeds.yaml"
)
envelope = ResourceEnvelope(provider_call_cap=34, outer_hardwall_sec=15000)

assert research_input["observations"][:6] == prior_input["observations"]
assert len(research_input["observations"]) == 7
assert legacy_problem.name == "cvrp"
assert len(history_names) == 15
assert len(histories) == 39
assert len(research_input["observations"]) + len(histories) == 46
assert protocol.version == split.version == seeds.version == (
    "0.4-cvrp-m28-seen-bank-qualification"
)
assert protocol.screening.n_cases_modify == 3
assert protocol.screening.expand_to_modify == 6
assert protocol.screening.n_seeds == 2
assert protocol.screening.effective_expand_n_seeds == 4
assert len(split.screening) == 6
assert tuple(split.screening[:3]) == protocol.screening.priority_case_ids
assert seeds.screening == [4358, 1868, 10684, 14577]
assert seeds.validation == [5405, 4354]
assert seeds.frozen == [2959, 6748]
assert seeds.canary == [6746]
assert limits.max_turns == 8 and limits.max_read_calls == 4
assert protocol.screening.require_expanded_for_pass is True
assert envelope.to_primitive() == {
    "provider_call_cap": 34,
    "outer_hardwall_sec": 15000,
}
PY

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  scion/tests/unit/core/test_m28_seen_bank_qualification_replay.py \
  scion/tests/test_campaign_formal_expansion_wiring.py::test_formal_screening_expansion_reuses_exact_candidate_then_enters_validation \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_nearest_history_headline_uses_only_index_headline_fields \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_invalid_first_basis_cannot_oracle_the_ranked_history_ref \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_m24_unseen_nearest_ref_can_be_grounded_and_revised \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_arbitrary_history_read_does_not_satisfy_ranked_audit \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_ranked_history_must_be_in_both_basis_ref_arrays \
  scion/tests/unit/proposal/test_hypothesis_research_session.py::test_last_shared_read_call_is_reserved_for_unread_history \
  scion/tests/unit/core/test_resource_envelope_boundary.py \
  scion/tests/unit/core/test_resource_envelope.py::test_resource_exhaustion_has_a_nonzero_cli_completion_status \
  scion/tests/unit/test_code_development.py::test_test_patch_falsifier_hides_framework_and_leaves_no_host_residue \
  scion/tests/unit/test_code_development.py::test_invalid_falsifier_is_inconclusive_but_host_checks_still_run \
  scion/tests/unit/test_code_development_redteam.py::test_c9_bypass_cannot_read_host_or_masked_framework_or_write_work

test -z "$(ps -eo comm=,args= | awk '
  ($1 ~ /^python/ || $1 == "bwrap" || $1 == "prlimit") &&
  ($0 ~ /-m scion[.]cli[.]main run/ ||
   $0 ~ /run_.*candidate.*[.]py/ ||
   $0 ~ /run_cvrp_controlled_e2e[.]py/ ||
   $0 ~ /(^|[[:space:]])[^[:space:]]*[/]solver[.]py([[:space:]]|$)/ ||
   $0 ~ /scion-experiments[/]v04-cvrp-m28-/) {
    print
    exit
  }
')"

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra \
    'any(.data[]?; .id == $model)' >/dev/null

env -i \
  HOME=/home/clawd \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
  SCION_MODEL=gpt-5.6-terra SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$PROXY_KEY_VALUE" \
  SCION_LLM_TIMEOUT_SEC=120 \
  SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=120 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=240 \
  SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B -m scion.cli.main run \
  --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem.yaml \
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m28-m27-terminal-research-input.json \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-m20-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-m21-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m24-m22-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m26-m25-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m27-m26-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m28-m27-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m28-seen-bank-qualification-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m28-seen-bank-qualification-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m28-seen-bank-qualification-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 34 \
  --outer-hardwall-sec 15000 \
  --rounds 2 \
  --campaign-dir "$M28_CAMPAIGN_DIR"
```

The provider metadata check and live command were not run during preparation.
After the preparation carrier was committed, independent scientific/runtime
review passed, the tracked tree stayed clean and the root stayed absent, the
user explicitly authorized this exact argument vector. The invocation created
the root and consumed the one-shot; no further authorization follows from this
document.

No distribution, packaging, build, deployment, root/systemd, Trust/Hash
authority, object identity, lease, signing, registration, duplicate-control,
M29 materialization or automatic next experiment is part of M28.
