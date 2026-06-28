"""Package-owned loader for report-only postrun artifact inventory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.postrun.handoff.resume_snapshot import (
    build_resume_top_branch_summaries,
    load_resume_campaign_summary,
)
from scion.postrun.inventory.constants import (
    EXIT_MARKERS,
    HANDOFF_DOC,
    LAUNCHER_ARTIFACTS,
    LAUNCHER_STATUS_KEYS,
    POSTRUN_REPORT_DIRS,
    PRE_CAMPAIGN_INFRA_FAILURE_KEYS,
    RUN_LOG_MARKERS,
)
from scion.postrun.inventory.coverage import _phase4_evidence_coverage
from scion.postrun.inventory.database import (
    _empty_champions,
    _empty_db_inventory,
    _empty_events,
    _empty_hypotheses,
    _merge_branch_counts,
    _read_db_inventory,
)
from scion.postrun.inventory.lifecycle import (
    _campaign_execution_artifact_state,
    _counters,
    _lifecycle_inventory,
    _launch_root_without_current_run,
    _pre_campaign_failure_validity,
    _prepared_only_counters,
    _prepared_only_validity,
    _validity,
)
from scion.postrun.inventory.prepared_contract import (
    build_prepared_run_contract as _build_prepared_run_contract,
    command_has_shell_flag,
)
from scion.postrun.inventory.prepared_ports import (
    PreparedHandoffPortCollection,
    PreparedHandoffReviewPort,
    _prepared_handoff_ports_by_family,
)
from scion.postrun.inventory.traces import (
    _empty_llm_trace_summary,
    _llm_trace_summary,
    _read_llm_traces,
)
from scion.postrun.inventory.utils import (
    _first_string,
    _mapping_or_empty,
    _marker_counts,
    _normalize_problem_family,
    _read_json,
    _read_text,
    _status_fields,
)
from scion.postrun.ports import PostrunInventory

SCION_PROJECT_DIR = Path(__file__).resolve().parents[3]
REPO_DIR = Path(__file__).resolve().parents[4]


def _status_key_set(defaults: Sequence[str], extras: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    keys: list[str] = []
    for raw_key in (*defaults, *extras):
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return tuple(keys)


class PostrunArtifactInventoryLoader:
    """PostrunInventoryPort implementation backed by artifact files on disk."""

    def __init__(
        self,
        *,
        prepared_handoff_ports: PreparedHandoffPortCollection | None = None,
        repo_dir: Path | str | None = None,
        scion_project_dir: Path | str | None = None,
        extra_launcher_status_keys: Sequence[str] = (),
        extra_pre_campaign_infra_failure_keys: Sequence[str] = (),
    ) -> None:
        self._prepared_handoff_ports = prepared_handoff_ports
        self._repo_dir = repo_dir
        self._scion_project_dir = scion_project_dir
        self._extra_launcher_status_keys = tuple(extra_launcher_status_keys)
        self._extra_pre_campaign_infra_failure_keys = tuple(
            extra_pre_campaign_infra_failure_keys
        )

    def load(self, run_root: Path) -> PostrunInventory:
        return build_inventory(
            run_root,
            prepared_handoff_ports=self._prepared_handoff_ports,
            repo_dir=self._repo_dir,
            scion_project_dir=self._scion_project_dir,
            extra_launcher_status_keys=self._extra_launcher_status_keys,
            extra_pre_campaign_infra_failure_keys=(
                self._extra_pre_campaign_infra_failure_keys
            ),
        )


def build_inventory(
    run_root: Path | str,
    *,
    prepared_handoff_ports: PreparedHandoffPortCollection | None = None,
    repo_dir: Path | str | None = None,
    scion_project_dir: Path | str | None = None,
    extra_launcher_status_keys: Sequence[str] = (),
    extra_pre_campaign_infra_failure_keys: Sequence[str] = (),
) -> dict[str, Any]:
    run_root = Path(run_root)
    repo_dir = Path(repo_dir) if repo_dir is not None else REPO_DIR
    scion_project_dir = (
        Path(scion_project_dir) if scion_project_dir is not None else SCION_PROJECT_DIR
    )
    prepared_handoff_ports_by_family = _prepared_handoff_ports_by_family(
        prepared_handoff_ports
    )
    launcher_status_keys = _status_key_set(
        LAUNCHER_STATUS_KEYS,
        tuple(extra_launcher_status_keys),
    )
    pre_campaign_infra_failure_keys = _status_key_set(
        PRE_CAMPAIGN_INFRA_FAILURE_KEYS,
        tuple(extra_pre_campaign_infra_failure_keys),
    )
    campaign_dir = run_root / "campaign"
    run_status_path = run_root / "run_status.json"
    run_status_present = run_status_path.exists()
    run_status = _read_json(run_status_path)
    run_status_valid = isinstance(run_status, dict)
    prepared_manifest = _read_json(run_root / "prepared_run_manifest.v1.json")
    campaign_execution_marker = _read_json(
        run_root / "campaign_execution_marker.v1.json"
    )
    campaign_run_status = _read_json(campaign_dir / "run_status.json")
    campaign_status = _read_json(campaign_dir / "status.json")
    summary = _read_json(campaign_dir / "campaign_summary.json")
    campaign_execution_artifacts = _campaign_execution_artifact_state(
        campaign_dir=campaign_dir,
        marker_path=run_root / "campaign_execution_marker.v1.json",
        marker=campaign_execution_marker,
        docs={
            "campaign_run_status": campaign_run_status,
            "campaign_status": campaign_status,
            "campaign_summary": summary,
        },
    )
    lifecycle = _lifecycle_inventory(
        run_status,
        prepared_manifest,
        campaign_run_status,
        campaign_status,
        summary,
        run_status_present=run_status_present,
        run_status_valid=run_status_valid,
        campaign_execution_artifacts=campaign_execution_artifacts,
        pre_campaign_infra_failure_keys=pre_campaign_infra_failure_keys,
    )
    trace_index = _read_json(
        campaign_dir / "agentic_sessions" / "agentic_session_trace_index.json"
    )
    session_index = _read_json(
        campaign_dir / "agentic_sessions" / "agentic_session_index.json"
    )

    db_path = campaign_dir / "scion.db"
    db_inventory = (
        _read_db_inventory(db_path) if db_path.exists() else _empty_db_inventory()
    )
    llm_traces = _read_llm_traces(
        campaign_dir / "llm_traces",
        trace_index=trace_index,
        session_index=session_index,
    )
    postrun_reports = _postrun_report_inventory(run_root)
    phase4_coverage = _phase4_evidence_coverage(
        run_root=run_root,
        campaign_dir=campaign_dir,
        campaign_status=campaign_status,
        summary=summary,
        trace_index=trace_index,
        session_index=session_index,
        llm_traces=llm_traces,
        lifecycle=lifecycle,
        prepared_manifest=prepared_manifest,
        prepared_handoff_ports=prepared_handoff_ports_by_family,
    )

    branches = _merge_branch_counts(
        db_inventory["branches"],
        session_counts=llm_traces["sessions_by_branch"],
        trace_counts=llm_traces["traces_by_branch"],
    )
    resume_summary = load_resume_campaign_summary(
        root=run_root,
        manifest=_mapping_or_empty(prepared_manifest),
        run_status=_mapping_or_empty(run_status),
        current_summary=summary,
    )
    resume_snapshot = _resume_snapshot_inventory(
        lifecycle=lifecycle,
        db_inventory=db_inventory,
        llm_traces=llm_traces,
        branches=branches,
        summary=resume_summary,
    )
    if _launch_root_without_current_run(lifecycle):
        current_branches: list[dict[str, Any]] = []
        current_events = _empty_events()
        current_hypotheses = _empty_hypotheses()
        current_champions = _empty_champions()
        current_llm_traces = _empty_llm_trace_summary()
    else:
        current_branches = branches
        current_events = db_inventory["events"]
        current_hypotheses = db_inventory["hypotheses"]
        current_champions = db_inventory["champions"]
        current_llm_traces = _llm_trace_summary(llm_traces)

    return {
        "run_root": str(run_root),
        "campaign_dir": str(campaign_dir),
        "run_name": _first_string(
            run_status,
            campaign_run_status,
            campaign_status,
            summary,
            keys=("run_name", "name", "campaign_id"),
        )
        or run_root.name,
        "lifecycle": lifecycle,
        "validity": (
            _prepared_only_validity(lifecycle)
            if lifecycle["prepared_only"]
            else (
                _pre_campaign_failure_validity(lifecycle)
                if (
                    lifecycle.get("launcher_status_unavailable") is True
                    or lifecycle["pre_campaign_completion_preflight_failed"]
                    or lifecycle.get("pre_campaign_infra_failed") is True
                    or lifecycle.get("campaign_execution_artifacts_unavailable") is True
                )
                else _validity(
                    run_status, campaign_run_status, campaign_status, summary
                )
            )
        ),
        "counters": (
            _prepared_only_counters(prepared_manifest)
            if _launch_root_without_current_run(lifecycle)
            else _counters(run_status, campaign_run_status, campaign_status, summary)
        ),
        "llm_traces": current_llm_traces,
        "launcher": _launcher_inventory(
            run_root,
            run_status,
            prepared_handoff_ports=prepared_handoff_ports_by_family,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
            launcher_status_keys=launcher_status_keys,
        ),
        "database": {
            "path": str(db_path),
            "present": db_path.exists(),
            "read_error": db_inventory.get("read_error"),
        },
        "resume_snapshot": resume_snapshot,
        "postrun_reports": postrun_reports,
        "phase4_evidence_coverage": phase4_coverage,
        "branches": current_branches,
        "events": current_events,
        "hypotheses": current_hypotheses,
        "champions": current_champions,
        "analysis_handoff": HANDOFF_DOC,
    }


def _launcher_inventory(
    run_root: Path,
    run_status: Any,
    *,
    prepared_handoff_ports: Mapping[str, PreparedHandoffReviewPort],
    repo_dir: Path,
    scion_project_dir: Path,
    launcher_status_keys: Sequence[str],
) -> dict[str, Any]:
    return {
        "artifacts": {name: (run_root / name).exists() for name in LAUNCHER_ARTIFACTS},
        "prepared_run_contract": _prepared_run_contract(
            run_root,
            prepared_handoff_ports=prepared_handoff_ports,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
        ),
        "status_fields": _status_fields(run_status, launcher_status_keys),
        "run_log_markers": _marker_counts(
            _read_text(run_root / "run.log"),
            RUN_LOG_MARKERS,
        ),
        "exit_markers": _marker_counts(
            _read_text(run_root / "exit.txt"),
            EXIT_MARKERS,
        ),
    }


def _postrun_report_inventory(run_root: Path) -> dict[str, Any]:
    report_dir = run_root / "postrun_acceptance"
    counts: dict[str, int] = {}
    files: dict[str, list[str]] = {}
    for name in POSTRUN_REPORT_DIRS:
        subdir = report_dir / name
        found = (
            sorted(
                str(path.relative_to(report_dir))
                for path in subdir.glob("*.json")
                if path.is_file()
            )
            if subdir.exists()
            else []
        )
        counts[name] = len(found)
        files[name] = found
    return {
        "report_dir": str(report_dir),
        "exists": report_dir.exists(),
        "counts": counts,
        "files": files,
    }


def _prepared_run_contract(
    run_root: Path,
    *,
    prepared_handoff_ports: Mapping[str, PreparedHandoffReviewPort],
    repo_dir: Path,
    scion_project_dir: Path,
) -> dict[str, Any]:
    """Return report-only checks for a prepared launch root."""

    inferred_family = _infer_problem_family_from_run_root(
        run_root,
        known_problem_families=set(prepared_handoff_ports),
    )
    generic = _build_prepared_run_contract(
        run_root,
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
        postrun_report_dirs=POSTRUN_REPORT_DIRS,
        inferred_problem_family=inferred_family,
    )
    contract = generic.contract
    if not generic.manifest_is_mapping:
        return contract

    checks = contract["checks"]
    for name, item in _problem_prepared_contract_checks(
        generic.problem_check_manifest,
        prepared_handoff_ports=prepared_handoff_ports,
        manifest_run_root=generic.manifest_run_root,
        local_run_root=run_root,
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
    ).items():
        checks[name] = {
            "passed": item.get("passed") is True,
            "detail": item.get("detail"),
        }
    contract["contract_complete"] = all(item["passed"] for item in checks.values())
    return contract


def _problem_prepared_contract_checks(
    manifest: Mapping[str, Any],
    *,
    prepared_handoff_ports: Mapping[str, PreparedHandoffReviewPort],
    manifest_run_root: str,
    local_run_root: Path,
    repo_dir: Path,
    scion_project_dir: Path,
) -> dict[str, dict[str, Any]]:
    family = _normalize_problem_family(manifest.get("problem_family"))
    port = prepared_handoff_ports.get(family)
    if port is None:
        return {}
    return port.prepared_contract_checks(
        manifest,
        manifest_run_root=manifest_run_root,
        local_run_root=local_run_root,
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
    )


def _infer_problem_family_from_run_root(
    run_root: Path,
    *,
    known_problem_families: set[str],
) -> dict[str, Any]:
    """Infer problem family from deterministic launched-run artifacts only."""

    for rel_path in (Path("run.log"), Path("campaign") / "run.log"):
        log_path = run_root / rel_path
        problem_family = _problem_family_from_starting_campaign_log(
            _read_text(log_path),
            known_problem_families=known_problem_families,
        )
        if problem_family is not None:
            return {
                "problem_family": problem_family,
                "source": str(rel_path),
                "evidence": "Starting campaign",
            }

    return {
        "problem_family": None,
        "source": None,
        "evidence": None,
    }


def _problem_family_from_starting_campaign_log(
    text: str,
    *,
    known_problem_families: set[str],
) -> str | None:
    for raw_line in text.splitlines():
        if "Starting campaign:" not in raw_line:
            continue
        campaign_name = raw_line.split("Starting campaign:", 1)[1].strip().split()
        if not campaign_name:
            continue
        problem_family = _normalize_problem_family(
            campaign_name[0].strip("`'\"()[]{}:,"),
        )
        if not known_problem_families or problem_family in known_problem_families:
            return problem_family
    return None


def _resume_snapshot_inventory(
    *,
    lifecycle: Mapping[str, Any],
    db_inventory: dict[str, Any],
    llm_traces: dict[str, Any],
    branches: list[dict[str, Any]],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    if not _launch_root_without_current_run(lifecycle):
        return {
            "present": False,
            "current_run_evidence": True,
            "evidence_scope": lifecycle.get("evidence_scope") or "postrun_campaign",
        }
    return {
        "present": bool(
            branches
            or llm_traces["trace_count"]
            or llm_traces["index_trace_count"]
            or db_inventory["hypotheses"].get("count")
            or any(db_inventory["events"].get(key) for key in db_inventory["events"])
        ),
        "current_run_evidence": False,
        "evidence_scope": lifecycle.get("evidence_scope") or "launch_root",
        "resume_from_campaign": lifecycle.get("resume_from_campaign"),
        "branch_count": len(branches),
        "llm_trace_count": llm_traces["trace_count"],
        "llm_index_trace_count": llm_traces["index_trace_count"],
        "llm_index_session_count": llm_traces["index_session_count"],
        "llm_by_kind": dict(sorted(llm_traces["by_kind"].items())),
        "llm_by_status": dict(sorted(llm_traces["by_status"].items())),
        "events_by_kind": db_inventory["events"].get("by_kind", {}),
        "events_by_decision": db_inventory["events"].get("by_decision", {}),
        "events_by_stage": db_inventory["events"].get("by_stage", {}),
        "hypothesis_count": db_inventory["hypotheses"].get("count", 0),
        "hypotheses_by_status": db_inventory["hypotheses"].get("by_status", {}),
        "champion_count": db_inventory["champions"].get("count", 0),
        "max_champion_version": db_inventory["champions"].get("max_version"),
        "top_branches": build_resume_top_branch_summaries(
            branches=branches,
            summary=summary,
        ),
        "source": "copied campaign snapshot; not current-run evidence",
    }
