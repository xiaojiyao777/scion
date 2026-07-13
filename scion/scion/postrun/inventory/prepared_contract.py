"""Generic prepared-run contract inventory checks."""

from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

PREPARED_RUN_MANIFEST_SCHEMA = "scion.launcher_prepared_run_manifest.v1"
PREPARED_RUN_CONTRACT_SCHEMA = "scion.prepared_run_contract_inventory.v1"
REMOVED_RUNTIME_COMMAND_OPTIONS = (
    "--measurement-governance",
    "--proposal-context-ablation",
    "--proposal-runtime-mode",
    "--disable-early-stop",
)
REMOVED_RUNTIME_ENV_KEYS = (
    "MEASUREMENT_GOVERNANCE",
    "PROPOSAL_CONTEXT_ABLATION",
    "PROPOSAL_RUNTIME_MODE",
    "DISABLE_EARLY_STOP",
)


@dataclass
class PreparedRunContractBuild:
    """Prepared contract payload plus context for compatibility adapters."""

    contract: dict[str, Any]
    manifest: Mapping[str, Any]
    problem_check_manifest: dict[str, Any]
    manifest_run_root: str
    manifest_is_mapping: bool


class PreparedRunContractInventoryPort:
    """Build problem-neutral prepared-run contract inventory payloads."""

    def __init__(
        self,
        *,
        repo_dir: Path,
        scion_project_dir: Path,
        postrun_report_dirs: Sequence[str],
    ) -> None:
        self._repo_dir = repo_dir
        self._scion_project_dir = scion_project_dir
        self._postrun_report_dirs = tuple(postrun_report_dirs)

    def build(
        self,
        run_root: Path,
        *,
        inferred_problem_family: Mapping[str, Any] | None = None,
    ) -> PreparedRunContractBuild:
        manifest_path = run_root / "prepared_run_manifest.v1.json"
        manifest = _read_json(manifest_path)
        inferred = _normalized_inferred_problem_family(inferred_problem_family)
        command_text = _read_text(run_root / "command.txt")
        checks: dict[str, dict[str, Any]] = {}

        def add_check(name: str, passed: bool, detail: Any = "") -> None:
            checks[name] = {"passed": bool(passed), "detail": detail}

        manifest_is_mapping = isinstance(manifest, dict)
        add_check("manifest_present", manifest_path.exists(), str(manifest_path))
        add_check("manifest_json_object", manifest_is_mapping, type(manifest).__name__)
        if not manifest_is_mapping:
            contract = _empty_contract(
                manifest_path=manifest_path,
                manifest_present=manifest_path.exists(),
                inferred_problem_family=inferred,
                checks=checks,
            )
            return PreparedRunContractBuild(
                contract=contract,
                manifest={},
                problem_check_manifest={},
                manifest_run_root="",
                manifest_is_mapping=False,
            )

        assert isinstance(manifest, dict)
        rendered_manifest = json.dumps(manifest, sort_keys=True)
        run_root_text = str(manifest.get("run_root") or "")
        campaign_dir_text = str(manifest.get("campaign_dir") or "")
        report_metadata = _mapping_or_empty(manifest.get("report_metadata"))
        model = _mapping_or_empty(manifest.get("model"))
        git = _mapping_or_empty(manifest.get("git"))
        config = _mapping_or_empty(manifest.get("config"))
        execution_raw = manifest.get("execution")
        execution_is_dict = isinstance(execution_raw, dict)
        execution = execution_raw if execution_is_dict else {}
        manifest_problem_family = _string_or_none(manifest.get("problem_family"))
        problem_family = manifest_problem_family or inferred["problem_family"]
        problem_family_source = (
            "prepared_run_manifest"
            if manifest_problem_family is not None
            else inferred["source"]
        )
        problem_family_inferred = (
            manifest_problem_family is None
            and inferred["problem_family"] is not None
        )
        problem_check_manifest = dict(manifest)
        if problem_family is not None and manifest_problem_family is None:
            problem_check_manifest["problem_family"] = problem_family

        add_check(
            "manifest_schema",
            manifest.get("schema_version") == PREPARED_RUN_MANIFEST_SCHEMA,
            manifest.get("schema_version"),
        )
        for key in ("report_only", "decision_features_excluded"):
            add_check(f"manifest_{key}", manifest.get(key) is True, manifest.get(key))
        for key in (
            "quality_judgment",
            "campaign_state_mutated",
            "scheduler_state_mutated",
            "promotion_state_mutated",
        ):
            add_check(f"manifest_{key}", manifest.get(key) is False, manifest.get(key))
        add_check(
            "manifest_secret_free",
            "SCION_API_KEY" not in rendered_manifest,
            "SCION_API_KEY absent",
        )
        add_check(
            "run_root_identity",
            _same_path_or_leaf(run_root_text, run_root),
            run_root_text,
        )
        add_check(
            "campaign_dir_identity",
            _same_path_or_leaf(campaign_dir_text, run_root / "campaign"),
            campaign_dir_text,
        )

        command = str(manifest.get("command") or "")
        add_check("command_txt_present", bool(command_text.strip()), "command.txt")
        add_check(
            "command_matches_manifest",
            bool(command and command in command_text),
            command,
        )
        add_check(
            "prepared_manifest_pointer",
            _command_points_to_prepared_manifest(command_text, run_root, run_root_text),
            "PREPARED_RUN_MANIFEST",
        )
        add_check(
            "model_name_present",
            bool(str(model.get("name") or "").strip()),
            model.get("name"),
        )
        add_check(
            "completion_preflight_enabled",
            model.get("completion_preflight") is True,
            model.get("completion_preflight"),
        )
        add_check(
            "control_pair_key_present",
            bool(report_metadata.get("control_pair_key")),
            report_metadata.get("control_pair_key"),
        )
        add_check(
            "postrun_reports_enabled",
            report_metadata.get("postrun_reports") is True,
            report_metadata.get("postrun_reports"),
        )
        families = report_metadata.get("postrun_acceptance_families")
        missing_families = [
            family
            for family in self._postrun_report_dirs
            if family not in (families or [])
        ]
        add_check(
            "postrun_families_complete",
            isinstance(families, list) and not missing_families,
            ",".join(missing_families),
        )
        add_check("execution_present", execution_is_dict, "execution")
        add_check(
            "execution_rounds_positive",
            _positive_number(execution.get("rounds")),
            execution.get("rounds"),
        )
        try:
            recorded_runtime_mode = prepared_execution_runtime_mode(execution)
            runtime_mode_detail = recorded_runtime_mode
            runtime_mode_consistent = True
        except ValueError as exc:
            runtime_mode_detail = str(exc)
            runtime_mode_consistent = False
        add_check(
            "execution_proposal_runtime_mode_consistent",
            runtime_mode_consistent,
            runtime_mode_detail,
        )
        removed_command_options = [
            option
            for option in REMOVED_RUNTIME_COMMAND_OPTIONS
            if command_has_shell_flag(command, option)
        ]
        add_check(
            "command_removed_runtime_controls_absent",
            not removed_command_options,
            removed_command_options,
        )
        missing_config_paths = missing_manifest_config_paths(
            config,
            manifest_run_root=run_root_text,
            local_run_root=run_root,
            repo_dir=self._repo_dir,
            scion_project_dir=self._scion_project_dir,
        )
        add_check(
            "config_paths_resolvable",
            not missing_config_paths,
            ",".join(missing_config_paths),
        )
        git_consistency = git_runtime_consistency(git, repo_dir=self._repo_dir)
        add_check(
            "git_runtime_consistent",
            git_consistency.get("consistent") is True,
            git_consistency.get("detail"),
        )

        contract = {
            "schema_version": PREPARED_RUN_CONTRACT_SCHEMA,
            "report_only": True,
            "quality_judgment": False,
            "decision_features_excluded": True,
            "manifest_path": str(manifest_path),
            "manifest_present": True,
            "contract_complete": all(item["passed"] for item in checks.values()),
            "problem_family": problem_family,
            "problem_family_source": problem_family_source,
            "problem_family_inferred": problem_family_inferred,
            "problem_family_inference_evidence": inferred["evidence"],
            "model": model.get("name"),
            "analysis_intent": _string_or_none(manifest.get("analysis_intent")),
            "acceptance_focus": _string_items(manifest.get("acceptance_focus")),
            "research_focus": _mapping_or_empty(manifest.get("research_focus")),
            "execution": prepared_contract_execution(execution),
            "resume_from_campaign": _string_or_none(
                manifest.get("resume_from_campaign")
            ),
            "git": prepared_contract_git_identity(git_consistency),
            "control_pair_key": report_metadata.get("control_pair_key"),
            "completion_preflight": model.get("completion_preflight"),
            "postrun_reports": report_metadata.get("postrun_reports"),
            "checks": checks,
        }
        return PreparedRunContractBuild(
            contract=contract,
            manifest=manifest,
            problem_check_manifest=problem_check_manifest,
            manifest_run_root=run_root_text,
            manifest_is_mapping=True,
        )


def build_prepared_run_contract(
    run_root: Path,
    *,
    repo_dir: Path,
    scion_project_dir: Path,
    postrun_report_dirs: Sequence[str],
    inferred_problem_family: Mapping[str, Any] | None = None,
) -> PreparedRunContractBuild:
    """Build a prepared-run contract payload with generic checks only."""

    return PreparedRunContractInventoryPort(
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
        postrun_report_dirs=postrun_report_dirs,
    ).build(run_root, inferred_problem_family=inferred_problem_family)


def command_has_shell_flag(command: Any, flag: str) -> bool:
    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return False
    return flag in tokens


def missing_manifest_config_paths(
    config: Mapping[str, Any],
    *,
    manifest_run_root: str,
    local_run_root: Path,
    repo_dir: Path,
    scion_project_dir: Path,
) -> list[str]:
    missing: list[str] = []
    for key, value in sorted(config.items()):
        if not isinstance(value, str) or not value.strip():
            continue
        if key.endswith("data_root"):
            continue
        if manifest_path_resolves(
            value,
            manifest_run_root,
            local_run_root,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
        ):
            continue
        missing.append(f"{key}={value}")
    return missing


def manifest_path_resolves(
    value: str,
    manifest_run_root: str,
    local_run_root: Path,
    *,
    repo_dir: Path,
    scion_project_dir: Path,
) -> bool:
    return (
        resolve_manifest_path(
            value,
            manifest_run_root=manifest_run_root,
            local_run_root=local_run_root,
            repo_dir=repo_dir,
            scion_project_dir=scion_project_dir,
        )
        is not None
    )


def resolve_manifest_path(
    value: str,
    manifest_run_root: str = "",
    local_run_root: Path | None = None,
    *,
    repo_dir: Path,
    scion_project_dir: Path,
) -> Path | None:
    for candidate in manifest_path_candidates(
        value,
        manifest_run_root,
        local_run_root,
        repo_dir=repo_dir,
        scion_project_dir=scion_project_dir,
    ):
        if candidate.exists():
            return candidate
    return None


def manifest_path_candidates(
    value: str,
    manifest_run_root: str = "",
    local_run_root: Path | None = None,
    *,
    repo_dir: Path,
    scion_project_dir: Path,
) -> list[Path]:
    path = Path(value)
    candidates = [path]
    if not path.is_absolute():
        candidates.extend(
            (
                repo_dir / path,
                scion_project_dir / path,
                scion_project_dir / "scion" / path,
            )
        )
    if (
        local_run_root is not None
        and manifest_run_root
        and value.startswith(manifest_run_root)
    ):
        try:
            candidates.append(
                local_run_root / Path(value).relative_to(manifest_run_root)
            )
        except ValueError:
            pass
    return candidates


def git_runtime_consistency(
    git: Mapping[str, Any],
    *,
    repo_dir: Path,
) -> dict[str, Any]:
    manifest_commit = str(git.get("commit") or "").strip()
    runtime_guard_paths = str(git.get("runtime_guard_paths") or "").strip()
    checkout_commit = git_output(("rev-parse", "--short", "HEAD"), repo_dir=repo_dir)
    if not manifest_commit:
        return {
            "consistent": False,
            "manifest_commit": None,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "missing manifest git.commit",
        }
    if not checkout_commit:
        return {
            "consistent": False,
            "manifest_commit": manifest_commit,
            "checkout_commit": None,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "unable to read checkout HEAD",
        }
    if checkout_commit == manifest_commit:
        return {
            "consistent": True,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout matches manifest commit",
        }
    if not runtime_guard_paths:
        return {
            "consistent": False,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout differs and runtime guard paths are missing",
        }
    pathspecs = runtime_guard_paths.split()
    diff = subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "diff",
            "--quiet",
            f"{manifest_commit}..HEAD",
            "--",
            *pathspecs,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if diff.returncode == 0:
        return {
            "consistent": True,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout differs, but runtime guard paths are unchanged",
        }
    if diff.returncode == 1:
        return {
            "consistent": False,
            "manifest_commit": manifest_commit,
            "checkout_commit": checkout_commit,
            "runtime_guard_paths": runtime_guard_paths,
            "detail": "checkout differs and runtime guard paths changed",
        }
    detail = (diff.stderr or diff.stdout or "git diff failed").strip()
    return {
        "consistent": False,
        "manifest_commit": manifest_commit,
        "checkout_commit": checkout_commit,
        "runtime_guard_paths": runtime_guard_paths,
        "detail": detail,
    }


def git_output(args: tuple[str, ...], *, repo_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def prepared_contract_execution(execution: Mapping[str, Any]) -> dict[str, Any]:
    try:
        proposal_runtime_mode = prepared_execution_runtime_mode(execution)
    except ValueError:
        proposal_runtime_mode = None
    return {
        "rounds": execution.get("rounds"),
        "time_limit_sec": execution.get("time_limit_sec"),
        "proposal_runtime_mode": proposal_runtime_mode,
    }


def prepared_execution_runtime_mode(execution: Mapping[str, Any]) -> str:
    """Require the sole production proposal runtime."""

    explicit = execution.get("proposal_runtime_mode")
    if explicit != "direct_v3":
        raise ValueError("prepared proposal runtime must be direct_v3")
    supported_fields = {
        "rounds",
        "time_limit_sec",
        "proposal_runtime_mode",
    }
    unsupported = sorted(set(execution).difference(supported_fields))
    if unsupported:
        raise ValueError(
            "prepared direct_v3 execution contains unsupported fields: "
            + ", ".join(unsupported)
        )
    return "direct_v3"


def prepared_contract_git_identity(
    git_consistency: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **dict(git_consistency),
        "commit": git_consistency.get("manifest_commit"),
    }


def _empty_contract(
    *,
    manifest_path: Path,
    manifest_present: bool,
    inferred_problem_family: Mapping[str, Any],
    checks: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": PREPARED_RUN_CONTRACT_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "manifest_path": str(manifest_path),
        "manifest_present": manifest_present,
        "contract_complete": False,
        "problem_family": inferred_problem_family["problem_family"],
        "problem_family_source": inferred_problem_family["source"],
        "problem_family_inferred": inferred_problem_family["problem_family"]
        is not None,
        "problem_family_inference_evidence": inferred_problem_family["evidence"],
        "model": None,
        "analysis_intent": None,
        "acceptance_focus": [],
        "research_focus": {},
        "execution": {},
        "resume_from_campaign": None,
        "control_pair_key": None,
        "completion_preflight": None,
        "postrun_reports": None,
        "checks": dict(checks),
    }


def _same_path_or_leaf(manifest_path: str, local_path: Path) -> bool:
    if not manifest_path:
        return False
    remote = Path(manifest_path)
    if remote == local_path:
        return True
    if remote.name == local_path.name and local_path.name != "campaign":
        return True
    return (
        remote.name == local_path.name
        and remote.parent.name == local_path.parent.name
    )


def _command_points_to_prepared_manifest(
    command_text: str,
    run_root: Path,
    manifest_run_root: str,
) -> bool:
    for line in command_text.splitlines():
        if not line.startswith("PREPARED_RUN_MANIFEST="):
            continue
        raw_path = line.split("=", 1)[1].strip()
        if raw_path == str(run_root / "prepared_run_manifest.v1.json"):
            return True
        if raw_path == str(Path(manifest_run_root) / "prepared_run_manifest.v1.json"):
            return True
        prepared_path = Path(raw_path)
        return (
            prepared_path.name == "prepared_run_manifest.v1.json"
            and prepared_path.parent.name == run_root.name
        )
    return False


def _positive_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (float, int)) and value > 0


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _normalized_inferred_problem_family(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    data = value if isinstance(value, Mapping) else {}
    return {
        "problem_family": _string_or_none(data.get("problem_family")),
        "source": _string_or_none(data.get("source")),
        "evidence": _string_or_none(data.get("evidence")),
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
