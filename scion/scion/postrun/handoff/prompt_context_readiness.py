"""Problem prompt bridge specs for prepared prompt-context readiness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable, Mapping


_MODULE_PATH = Path(__file__).resolve()
DEFAULT_SCION_PROJECT_DIR = _MODULE_PATH.parents[3]
DEFAULT_REPO_DIR = _MODULE_PATH.parents[4]

from scion.postrun.handoff.prepared_prompt_context import (
    research_focus_projection_summary,
)
from scion.postrun.inventory.prepared_contract import (
    prepared_execution_runtime_mode,
)


SourceMarker = tuple[str, str]
MeasurementPromptSummaryBuilder = Callable[..., dict[str, Any]]
PROMPT_CONTEXT_READINESS_SCHEMA = "scion.prepared_prompt_context_readiness.v1"


@dataclass(frozen=True)
class ProblemPromptBridgeSpec:
    """Problem-owned prompt bridge metadata consumed by generic readiness tools."""

    problem_family: str
    problem_v1_candidates: tuple[str, ...]
    measurement_signal_name: str
    measurement_failure_prefix: str
    measurement_source_markers: Mapping[str, SourceMarker]
    measurement_marker_group: str
    measurement_bridge_scope: str
    measurement_prompt_summary_schema: str
    measurement_prompt_summary_builder: MeasurementPromptSummaryBuilder
    measurement_prompt_summary_compare_fields: tuple[str, ...]
    measurement_prompt_summary_positive_fields: tuple[str, ...]

    @property
    def measurement_marker_group_name(self) -> str:
        return self.measurement_marker_group

    def measurement_prompt_summary(
        self,
        *,
        problem_v1_path: Path | str | None,
    ) -> dict[str, Any]:
        return self.measurement_prompt_summary_builder(
            problem_v1_path=problem_v1_path,
            problem_family=self.problem_family,
        )

def resolve_problem_v1_path(
    *,
    root: Path,
    manifest: Mapping[str, Any],
    repo_dir: Path,
    spec: ProblemPromptBridgeSpec,
) -> Path | None:
    config = _mapping_or_empty(manifest.get("config"))
    candidates: list[Path] = []
    configured = str(config.get("problem_v1") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.extend((root / path, repo_dir / path))
    for rel in spec.problem_v1_candidates:
        candidates.append(repo_dir / rel)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None

def build_prepared_prompt_context_readiness(
    run_root: Path | str,
    *,
    repo_dir: Path | str | None = None,
    ports_by_family: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit prompt/context signal sources for a prepared-only launch root."""

    root = Path(run_root).expanduser().resolve()
    resolved_repo_dir = _resolve_repo_dir(repo_dir)
    port_registry = (
        dict(ports_by_family)
        if ports_by_family is not None
        else default_prepared_handoff_ports_by_family()
    )
    manifest_path = root / "prepared_run_manifest.v1.json"
    manifest = _read_json(manifest_path)
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    campaign_dir = _resolve_campaign_dir(root, manifest_dict)
    campaign_summary, summary_source, summary_source_kind = (
        _read_resume_context_artifact(
            root=root,
            manifest=manifest_dict,
            campaign_dir=campaign_dir,
            ref="campaign_summary.json",
        )
    )
    campaign_status, status_source, status_source_kind = _read_resume_context_artifact(
        root=root,
        manifest=manifest_dict,
        campaign_dir=campaign_dir,
        ref="status.json",
    )
    summary_dict = campaign_summary if isinstance(campaign_summary, dict) else {}
    status_dict = campaign_status if isinstance(campaign_status, dict) else {}
    research_focus = _mapping_or_empty(manifest_dict.get("research_focus"))
    model = _mapping_or_empty(manifest_dict.get("model"))
    execution = _mapping_or_empty(manifest_dict.get("execution"))
    resume_from_campaign = str(manifest_dict.get("resume_from_campaign") or "").strip()
    copied_campaign_required = bool(resume_from_campaign)
    proposal_runtime = _prepared_prompt_runtime(
        execution=execution,
        summary=summary_dict,
        status=status_dict,
    )

    signals: dict[str, dict[str, Any]] = {}
    _add_signal(
        signals,
        "prepared_manifest",
        available=bool(manifest_dict),
        required=True,
        source=str(manifest_path),
        detail={"problem_family": manifest_dict.get("problem_family")},
    )
    _add_signal(
        signals,
        "proposal_runtime_mode",
        available=proposal_runtime["status"] == "resolved",
        required=True,
        source="prepared manifest and copied campaign status",
        detail=proposal_runtime,
    )
    _add_signal(
        signals,
        "prepared_research_focus",
        available=bool(research_focus),
        required=False,
        source="prepared_run_manifest.research_focus",
        detail={
            "schema_version": research_focus.get("schema_version"),
            "field_count": len(research_focus),
        },
    )
    _add_signal(
        signals,
        "copied_campaign_summary",
        available=bool(summary_dict),
        required=copied_campaign_required,
        source=str(summary_source),
        detail={
            "keys": sorted(summary_dict),
            "resume_from_campaign": resume_from_campaign,
            "source_kind": summary_source_kind,
        },
    )
    _add_signal(
        signals,
        "copied_campaign_status",
        available=bool(status_dict),
        required=copied_campaign_required,
        source=str(status_source),
        detail={
            "keys": sorted(status_dict),
            "resume_from_campaign": resume_from_campaign,
            "source_kind": status_source_kind,
        },
    )
    _add_signal(
        signals,
        "completion_preflight_contract",
        available=model.get("completion_preflight") is True,
        required=False,
        source="prepared_run_manifest.model.completion_preflight",
        detail={"model": model.get("name")},
    )
    _add_focus_signals(
        signals,
        manifest_dict,
        research_focus,
        ports_by_family=port_registry,
    )
    _add_campaign_state_signals(
        signals,
        summary_dict,
        status_dict,
        proposal_runtime=proposal_runtime,
    )
    _add_launch_research_focus_projection_signal(
        signals,
        root=root,
        required=bool(research_focus),
    )

    missing_required = [
        name
        for name, item in sorted(signals.items())
        if item.get("required") is True
        and item.get("available") is not True
        and item.get("runtime_generated_after_launch") is not True
    ]

    return {
        "schema_version": PROMPT_CONTEXT_READINESS_SCHEMA,
        "artifact_kind": "prepared_prompt_context_readiness",
        "generated_at": _utc_now_iso(),
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "promotion_state_mutated": False,
        "raw_provider_prompt_rendered": False,
        "run_root": str(root),
        "campaign_dir": str(campaign_dir),
        "prepared_manifest_path": str(manifest_path),
        "problem_family": manifest_dict.get("problem_family"),
        "model": model.get("name"),
        "proposal_runtime": proposal_runtime,
        "prepared_manifest_commit": _manifest_commit(manifest_dict),
        "checkout_commit": _git_output(("rev-parse", "--short", "HEAD"), resolved_repo_dir),
        "readiness": {
            "ready_for_launch_prompt_audit": not missing_required,
            "missing_required": missing_required,
            "status": "ready" if not missing_required else "missing_required_sources",
        },
        "signals": signals,
        "notes": [
            "This report audits prompt/context signal sources only.",
            "It does not render raw provider prompts or mutate campaign state.",
            "Branch-level next-prompt context may be generated only after launch.",
        ],
    }


def render_prompt_context_readiness_markdown(report: Mapping[str, Any]) -> str:
    readiness = report.get("readiness")
    if not isinstance(readiness, dict):
        readiness = {}
    signals = report.get("signals")
    if not isinstance(signals, dict):
        signals = {}

    lines = [
        "# Prepared Prompt/Context Readiness",
        "",
        f"- Schema: `{report.get('schema_version')}`",
        f"- Report-only: `{report.get('report_only')}`",
        f"- Raw provider prompt rendered: `{report.get('raw_provider_prompt_rendered')}`",
        f"- Problem family: `{_display(report.get('problem_family'))}`",
        f"- Model: `{_display(report.get('model'))}`",
        f"- Ready for launch prompt audit: `{readiness.get('ready_for_launch_prompt_audit')}`",
        f"- Status: `{_display(readiness.get('status'))}`",
        "",
        "## Missing Required Sources",
    ]
    missing = readiness.get("missing_required")
    if isinstance(missing, list) and missing:
        for item in missing:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Signal Sources",
            "",
            "| Signal | Required | Available | Runtime-generated after launch | Source | Detail |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for name, item in sorted(signals.items()):
        if not isinstance(item, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(name),
                    _md_cell(item.get("required")),
                    _md_cell(item.get("available")),
                    _md_cell(item.get("runtime_generated_after_launch")),
                    _md_cell(item.get("source")),
                    _md_cell(item.get("detail")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Notes",
        ]
    )
    notes = report.get("notes")
    if isinstance(notes, list) and notes:
        for item in notes:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _read_resume_context_artifact(
    *,
    root: Path,
    manifest: dict[str, Any],
    campaign_dir: Path,
    ref: str,
) -> tuple[Any, Path, str]:
    """Read copied resume context without requiring stale canonical artifacts."""

    canonical_path = campaign_dir / ref
    canonical_doc = _read_json(canonical_path)
    if isinstance(canonical_doc, dict):
        return canonical_doc, canonical_path, "campaign_canonical"

    snapshot_path = _resume_snapshot_artifact_path(
        root=root,
        manifest=manifest,
        original_ref=ref,
    )
    if snapshot_path is not None:
        snapshot_doc = _read_json(snapshot_path)
        if isinstance(snapshot_doc, dict):
            return snapshot_doc, snapshot_path, "resume_snapshot"

    return canonical_doc, canonical_path, "campaign_canonical_missing"


def _resume_snapshot_artifact_path(
    *,
    root: Path,
    manifest: dict[str, Any],
    original_ref: str,
) -> Path | None:
    manifest_ref = str(manifest.get("resume_snapshot_ref") or "").strip()
    if not manifest_ref:
        run_status = _read_json(root / "run_status.json")
        if isinstance(run_status, dict):
            manifest_ref = str(run_status.get("resume_snapshot_ref") or "").strip()
    if not manifest_ref:
        return None
    snapshot_manifest_path = (root / manifest_ref).resolve()
    try:
        snapshot_manifest_path.relative_to(root)
    except ValueError:
        return None
    snapshot_manifest = _read_json(snapshot_manifest_path)
    if not isinstance(snapshot_manifest, dict):
        return None
    for item in snapshot_manifest.get("terminal_artifacts") or []:
        if not isinstance(item, dict):
            continue
        if item.get("original_ref") != original_ref:
            continue
        snapshot_ref = str(item.get("snapshot_ref") or "").strip()
        if not snapshot_ref:
            return None
        snapshot_path = (root / snapshot_ref).resolve()
        try:
            snapshot_path.relative_to(root)
        except ValueError:
            return None
        return snapshot_path
    return None


def _add_focus_signals(
    signals: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
    research_focus: dict[str, Any],
    *,
    ports_by_family: Mapping[str, Any],
) -> None:
    family = str(manifest.get("problem_family") or "")
    port = ports_by_family.get(family)
    if port is not None:
        signals.update(
            port.prepared_prompt_context_signals(
                manifest,
                research_focus,
            )
        )

    boundary = str(research_focus.get("decision_boundary") or "").lower()
    _add_signal(
        signals,
        "research_focus_decision_boundary",
        available=(
            "decisionfeatures" in boundary
            and "protocol" in boundary
            and "promotion" in boundary
            and "scheduler" in boundary
        ),
        required=False,
        source="prepared_run_manifest.research_focus.decision_boundary",
        detail={"problem_family": family},
    )


def _prepared_prompt_runtime(
    *,
    execution: Mapping[str, Any],
    summary: Mapping[str, Any],
    status: Mapping[str, Any],
) -> dict[str, Any]:
    sources: dict[str, str] = {}
    errors: list[str] = []
    try:
        sources["prepared_manifest.execution"] = prepared_execution_runtime_mode(
            execution
        )
    except ValueError as exc:
        errors.append(str(exc))
    for name, payload in (("campaign_summary", summary), ("campaign_status", status)):
        value = payload.get("proposal_runtime_mode")
        if value not in (None, ""):
            sources[name] = str(value)
    invalid_sources = {
        name: value
        for name, value in sources.items()
        if value != "direct_v3"
    }
    if errors or invalid_sources:
        runtime_status = "invalid"
        resolved = None
    elif sources and all(value == "direct_v3" for value in sources.values()):
        runtime_status = "resolved"
        resolved = "direct_v3"
    else:
        runtime_status = "unknown"
        resolved = None
    return {
        "status": runtime_status,
        "resolved_mode": resolved,
        "sources": sources,
        "errors": errors,
        "invalid_sources": invalid_sources,
        "fail_closed": runtime_status != "resolved",
    }


def _add_campaign_state_signals(
    signals: dict[str, dict[str, Any]],
    summary: dict[str, Any],
    status: dict[str, Any],
    *,
    proposal_runtime: Mapping[str, Any],
) -> None:
    summary_branch_count = _sequence_count(summary.get("branches"))
    status_branch_count = _sequence_count(status.get("branches"))
    branch_count = max(summary_branch_count, status_branch_count)
    _add_signal(
        signals,
        "copied_branch_snapshot",
        available=branch_count > 0,
        required=False,
        source="campaign_summary.branches or status.branches",
        detail={
            "summary_branch_count": summary_branch_count,
            "status_branch_count": status_branch_count,
        },
        runtime_generated_after_launch=branch_count == 0,
    )

    prompt_manifest_ref_count = _count_prompt_manifest_refs(summary) + (
        _count_prompt_manifest_refs(status)
    )
    _add_signal(
        signals,
        "prompt_manifest_history",
        available=prompt_manifest_ref_count > 0,
        required=False,
        source="campaign_summary/status prompt_manifest references",
        detail={"prompt_manifest_ref_count": prompt_manifest_ref_count},
        runtime_generated_after_launch=prompt_manifest_ref_count == 0,
    )


def _add_launch_research_focus_projection_signal(
    signals: dict[str, dict[str, Any]],
    *,
    root: Path,
    required: bool,
) -> None:
    manifest_path = root / "prepared_run_manifest.v1.json"
    manifest = _mapping_or_empty(_read_json(manifest_path))
    projection_summary = research_focus_projection_summary(
        manifest_path=manifest_path,
        manifest=manifest,
    )
    _add_signal(
        signals,
        "prepared_research_focus_projection",
        available=projection_summary.get("available") is True,
        required=required,
        source=(
            "prepared_run_manifest.research_focus typed projection"
        ),
        detail=projection_summary,
    )


def _add_signal(
    signals: dict[str, dict[str, Any]],
    name: str,
    *,
    available: bool,
    required: bool,
    source: Any,
    detail: Any = None,
    runtime_generated_after_launch: bool = False,
) -> None:
    signals[name] = {
        "available": bool(available),
        "required": bool(required),
        "source": source,
        "detail": detail,
        "runtime_generated_after_launch": bool(runtime_generated_after_launch),
    }


def _resolve_campaign_dir(root: Path, manifest: dict[str, Any]) -> Path:
    local_campaign = root / "campaign"
    if local_campaign.exists():
        return local_campaign
    manifest_campaign = manifest.get("campaign_dir")
    if isinstance(manifest_campaign, str) and manifest_campaign:
        path = Path(manifest_campaign).expanduser()
        if path.exists():
            return path.resolve()
    return local_campaign


def _count_prompt_manifest_refs(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            (1 if "prompt_manifest" in str(key).lower() else 0)
            + _count_prompt_manifest_refs(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return sum(_count_prompt_manifest_refs(item) for item in value)
    if isinstance(value, str) and "prompt_manifest" in value.lower():
        return 1
    return 0


def _source_contains(repo_dir: Path, relative_path: str, marker: str) -> bool:
    path = repo_dir / relative_path
    return _path_contains(path, marker)


def _path_contains(path: Path, marker: str) -> bool:
    try:
        return marker in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _display(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _md_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        rendered = json.dumps(value, sort_keys=True)
    else:
        rendered = _display(value)
    return rendered.replace("|", "\\|").replace("\n", " ")


def default_prepared_handoff_ports_by_family() -> dict[str, Any]:
    from scion.problems.cvrp.postrun_handoff import CvrpPreparedHandoffReviewPort
    from scion.problems.warehouse_delivery.postrun_handoff import (
        WarehousePreparedHandoffReviewPort,
    )

    return {
        "cvrp": CvrpPreparedHandoffReviewPort(),
        "warehouse_delivery": WarehousePreparedHandoffReviewPort(),
    }


def _default_prepared_handoff_ports_by_family() -> dict[str, Any]:
    return default_prepared_handoff_ports_by_family()


def _resolve_repo_dir(repo_dir: Path | str | None) -> Path:
    if repo_dir is None:
        return DEFAULT_REPO_DIR
    return Path(repo_dir).expanduser().resolve()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _manifest_commit(manifest: Any) -> str | None:
    if not isinstance(manifest, dict):
        return None
    git = manifest.get("git")
    if not isinstance(git, dict):
        return None
    commit = git.get("commit")
    return str(commit) if commit else None


def _git_output(args: tuple[str, ...], repo_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0
