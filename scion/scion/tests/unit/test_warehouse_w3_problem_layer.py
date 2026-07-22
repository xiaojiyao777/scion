from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from random import Random

import pytest

from scion.problems.warehouse_delivery.w3_analysis import replay_artifacts
from scion.problems.warehouse_delivery.w3_fixed_arm import (
    ARM_ORDER,
    SOLVER_CLOSURE,
    WILLIAMS,
    _arms,
    _cells,
    _git_blob,
    _greedy_fact,
    _invocation_contract,
    _protocol_gate_contract,
    build_schedule,
    canonical_sha256,
    execution_environment,
    process_spec_for_job,
    registry_semantics,
    render_json,
    repository_root,
    sha256_bytes,
    workspace_runtime,
)
from scion.problems.warehouse_delivery.w3_validation import (
    decode_canonical_row,
    validate_closed_observation,
)
from scion.runtime.execution import (
    CapturedStream,
    CgroupEventsFact,
    CgroupIdentity,
    ClosedSpawnObservation,
    JobCgroupKey,
    ProcessIdentity,
    WaitFact,
)


def test_git_blob_source_is_read_from_the_commit_object() -> None:
    root = repository_root()
    commit = (
        __import__("subprocess")
        .run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
    )
    snapshot, blob_oid = _git_blob(
        root, commit, "scion/design/scion-architecture-v3.md"
    )
    assert len(blob_oid) == 40
    assert snapshot.data.startswith(b"# Scion Framework")
    assert snapshot.sha256 == sha256_bytes(snapshot.data)


def test_schedule_is_exact_43_by_4_and_williams_balanced() -> None:
    screening = [f"warehouse_delivery/screening/s{index}.json" for index in range(14)]
    validation = [f"warehouse_delivery/validation/v{index}.json" for index in range(5)]
    contract = {
        "screening_selected": [
            {"stable_case_id": case_id} for case_id in screening
        ],
        "validation_selected": [
            {"stable_case_id": case_id} for case_id in validation
        ],
    }
    w2 = json.loads(
        (repository_root() / "scion/contracts/warehouse_w2_preservation_manifest.v1.json").read_bytes()
    )
    cells = _cells(contract)
    jobs, balance = build_schedule(cells, _arms(w2))
    assert len(cells) == 43
    assert len(jobs) == 172
    assert tuple(job["job_ordinal"] for job in jobs) == tuple(range(172))
    for cell in cells:
        selected = [job["arm"] for job in jobs if job["cell_ordinal"] == cell["cell_ordinal"]]
        assert tuple(selected) == WILLIAMS[cell["stage_cell_ordinal"] % 4]
    assert all(
        positions == [7, 7, 7, 7]
        for positions in balance["screening"]["positions"].values()
    )


def _tiny_case(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "orders": [
                    {
                        "order_id": "one",
                        "vehicle_category": 1,
                        "vehicle_subcategory": 1,
                        "urgent": False,
                        "hazard_flag": False,
                        "hazard_quantity": 0,
                        "pickup_name": "P",
                        "pickup_province": "Guangdong",
                        "pickup_city": "Dongguan",
                        "declaration_amount": 1,
                        "lsp": "L",
                        "ship_method": "sea",
                        "destination_country": "DE",
                        "spu_list": [{"packing_type": "FULL_PLT", "quantity": 1}],
                    }
                ],
                "amount_limits": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _closed_observation(spec: object, stdout: bytes) -> ClosedSpawnObservation:
    nonce = "0123456789abcdef" * 4
    key = JobCgroupKey.create(ordinal=0, invocation_nonce=nonce)
    process = ProcessIdentity(
        pid=1201,
        proc_starttime_ticks=700,
        pidfd_device=5,
        pidfd_inode=91,
        creator_pid=1199,
        creator_starttime_ticks=600,
    )
    wait = WaitFact.from_native((1201, 1000, 1, 0, 0, 0, 0, 0))
    cgroup = CgroupIdentity(
        service_name="scion-w3@fixture.service",
        supervisor_name="supervisor",
        job_name=key.rendered_name,
        service_device=1,
        service_inode=11,
        supervisor_device=1,
        supervisor_inode=12,
        job_device=1,
        job_inode=13,
        service_relative_lineage=("scion-w3@fixture.service", key.rendered_name),
    )
    events = CgroupEventsFact.decode(b"populated 0\nfrozen 0\n")
    return ClosedSpawnObservation.create(
        spec=spec,  # type: ignore[arg-type]
        start_wall_ns=100,
        end_wall_ns=200,
        start_monotonic_ns=300,
        end_monotonic_ns=400,
        process_identity=process,
        wait_fact=wait,
        stdout=CapturedStream.from_bytes(stdout),
        stderr=CapturedStream.from_bytes(b""),
        cgroup_identity=cgroup,
        initial_cgroup_events=events,
        final_cgroup_events=events,
    )


def test_closed_observation_becomes_row_bytes_without_publication(tmp_path: Path) -> None:
    root = tmp_path / "dry"
    workspace = root / "workspaces/champion"
    for relative in SOLVER_CLOSURE:
        source = repository_root() / "surrogate" / relative
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    case_path = root / "cases/screening/tiny.json"
    case_path.parent.mkdir(parents=True)
    _tiny_case(case_path)
    case_bytes = case_path.read_bytes()
    case = {
        "stable_case_id": "warehouse_delivery/screening/tiny.json",
        "manifest_index": 0,
        "lexical_path": "/evidence/tiny.json",
        "resolved_path": "/evidence/tiny.json",
        "size_bytes": len(case_bytes),
        "content_sha256": sha256_bytes(case_bytes),
        "sealed_relative_path": "cases/screening/tiny.json",
    }
    with workspace_runtime(workspace) as runtime:
        fact = _greedy_fact(runtime, case, case_path, 42)
        instance = runtime["solver"].load_instance(case_path, phase=1)
        solution = runtime["greedy"].greedy_init(instance, Random(42))
        solution.objective = runtime["oracle"].recompute_objective(solution, instance)
        names = [
            entry["name"]
            for entry in registry_semantics(
                (workspace / "registry.yaml").read_bytes(), label="tiny"
            )["operators"]
        ]
        setattr(solution, "_scion_runtime", {"operator_registry": names})
        payload = runtime["solver"].solution_to_dict(solution, instance, 1)
    arm_sha = canonical_sha256({"arm": "champion"})
    job = {
        "job_ordinal": 0,
        "cell_ordinal": 0,
        "stage_cell_ordinal": 0,
        "stage": "screening",
        "stable_case_id": case["stable_case_id"],
        "seed": 42,
        "arm": "champion",
        "arm_position": 0,
        "arm_sha256": arm_sha,
    }
    manifest = {
        "toolchain": {"python": {"executable": str(Path(sys.executable).resolve())}},
        "invocation_contract": _invocation_contract(execution_environment()),
        "workspaces": [
            {
                "arm": "champion",
                "relative_path": "workspaces/champion",
                "tree": {"tree_sha256": canonical_sha256({"tree": "tiny"})},
                "registry_semantics": registry_semantics(
                    (workspace / "registry.yaml").read_bytes(), label="tiny"
                ),
            }
        ],
        "cases": [case],
        "greedy_preflight": [fact],
    }
    spec = process_spec_for_job(root, manifest, job)
    observation = _closed_observation(
        spec, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
    )
    row_bytes = validate_closed_observation(
        root, manifest, "0" * 64, job, observation
    )
    row = decode_canonical_row(row_bytes)
    assert row["execution_observation"]["observation_sha256"] == observation.observation_sha256
    assert row["oracle"]["feasible"] is True
    assert row["locked_groups"]["split_group_count"] == 0
    assert list(root.rglob("*.json")) == [case_path]


def _replay_fixture() -> tuple[dict[str, object], list[bytes], list[dict[str, object]]]:
    screening = [f"warehouse_delivery/screening/s{index}.json" for index in range(14)]
    validation = [f"warehouse_delivery/validation/v{index}.json" for index in range(5)]
    cases = screening + validation
    case_entries = [
        {
            "stable_case_id": case_id,
            "content_sha256": f"{index + 1:064x}",
        }
        for index, case_id in enumerate(cases)
    ]
    workspaces = [
        {
            "arm": arm,
            "tree": {"tree_sha256": canonical_sha256({"arm": arm})},
        }
        for arm in ARM_ORDER
    ]
    jobs: list[dict[str, object]] = []
    rows: list[bytes] = []
    identities: list[dict[str, object]] = []
    preflight: list[dict[str, object]] = []
    cell = 0
    costs = {
        "champion": 100,
        "destroy_only": 90,
        "merge_only": 110,
        "cumulative": 100,
    }
    for stage, selected_cases, seeds in (
        ("screening", screening, (42, 137)),
        ("validation", validation, (7, 19, 83)),
    ):
        for case_id in selected_cases:
            case_entry = next(item for item in case_entries if item["stable_case_id"] == case_id)
            for seed in seeds:
                counts = {
                    "formal_compatible_directed_pairs": 1,
                    "champion_merge_eligible_directed_pairs": 1,
                    "r3_merge_eligible_directed_pairs": 1,
                }
                preflight.append(
                    {
                        "stable_case_id": case_id,
                        "seed": seed,
                        "initial_solution_sha256": f"{cell + 100:064x}",
                        "initial_objective": {"subcategory_splits": 0, "total_cost": 100},
                        "merge_pair_counts": counts,
                    }
                )
                sequence = WILLIAMS[(cell if stage == "screening" else cell - 28) % 4]
                for position, arm in enumerate(sequence):
                    ordinal = len(jobs)
                    arm_sha = canonical_sha256({"arm": arm})
                    job = {
                        "job_ordinal": ordinal,
                        "cell_ordinal": cell,
                        "stage_cell_ordinal": cell if stage == "screening" else cell - 28,
                        "stage": stage,
                        "stable_case_id": case_id,
                        "seed": seed,
                        "arm": arm,
                        "arm_position": position,
                        "arm_sha256": arm_sha,
                    }
                    jobs.append(job)
                    row = {
                        "schema": "scion.warehouse_w3_fixed_arm_raw_row.v2",
                        "manifest_sha256": "a" * 64,
                        **{key: job[key] for key in (
                            "job_ordinal", "cell_ordinal", "stage_cell_ordinal", "stage",
                            "seed", "arm", "arm_position", "arm_sha256",
                        )},
                        "case_identity": {
                            "stable_case_id": case_id,
                            "content_sha256": case_entry["content_sha256"],
                        },
                        "workspace_tree_sha256": next(
                            item["tree"]["tree_sha256"] for item in workspaces if item["arm"] == arm
                        ),
                        "phase": 1,
                        "scientific_time_limit_seconds": 30,
                        "max_iterations": 200,
                        "execution_observation": {"observation_sha256": f"{ordinal + 1:064x}"},
                        "solution": {},
                        "solution_sha256": f"{ordinal + 200:064x}",
                        "oracle": {"feasible": True, "issue_codes": []},
                        "objective": {
                            "subcategory_splits": 0,
                            "total_cost": costs[arm],
                            "solver_reported_runtime_ms": 1,
                            "runner_wall_time_ns": 1000 + position,
                        },
                        "greedy_initial": {
                            "preflight_sha256": f"{cell + 100:064x}",
                            "job_reconstructed_sha256": f"{cell + 100:064x}",
                            "objective": {"subcategory_splits": 0, "total_cost": 100},
                        },
                        "locked_groups": {
                            "final_intact_locked_group_count": 0,
                            "whole_groups_moved_count": 0,
                            "split_group_count": 0,
                        },
                        "merge_pair_counts": counts,
                        "operator_runtime_diagnostics": {"status": "available", "value": {}},
                    }
                    data = render_json(row)
                    rows.append(data)
                    identities.append(
                        {
                            "job_ordinal": ordinal,
                            "opaque_publication_key": f"warehouse-w3-row-{ordinal:03d}",
                            "sha256": sha256_bytes(data),
                            "size_bytes": len(data),
                        }
                    )
                cell += 1
    manifest: dict[str, object] = {
        "jobs": jobs,
        "cases": case_entries,
        "workspaces": workspaces,
        "greedy_preflight": preflight,
        "arms": [
            {"name": arm, "arm_sha256": canonical_sha256({"arm": arm})}
            for arm in ARM_ORDER
        ],
        "case_contract": {
            "views": {
                "r3_initial_screening": {"stable_case_ids": screening[:6]},
                "r3_expanded_screening": {"stable_case_ids": screening},
                "r3_validation": {"stable_case_ids": validation},
            }
        },
        "analysis_contract": {
            "bootstrap": {"seed": 42, "draws": 100, "alpha": 0.05},
            "protocol_gate": _protocol_gate_contract(repository_root()),
            "source_digests": [],
        },
        "authority": {"design_sha256": "d" * 64},
        "source": {
            "source_commit": "c" * 40,
            "git_blob_aggregate_sha256": "b" * 64,
        },
        "toolchain": {},
        "problem_layer_sources": [],
        "sealed_repository_inputs": [],
        "w2_preservation_inputs": [],
        "schedule_balance": {},
    }
    return manifest, rows, identities


def test_replay_is_deterministic_and_has_no_publication_side_effect() -> None:
    manifest, rows, identities = _replay_fixture()
    first = replay_artifacts(manifest, "a" * 64, rows, identities)
    second = replay_artifacts(manifest, "a" * 64, rows, identities)
    assert first == second
    assert json.loads(first[0])["row_count"] == 172
    assert json.loads(first[1])["posterior_decomposition_only"] is True
    assert json.loads(first[2])["integrity_verdict"] == "passed"

    damaged = list(rows)
    damaged[0] = damaged[0].replace(b'"job_ordinal": 0', b'"job_ordinal": 9')
    with pytest.raises(Exception, match="canonical|job_ordinal"):
        replay_artifacts(manifest, "a" * 64, damaged, identities)
