"""Prepare a resumed campaign directory without carrying stale terminal state."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import shutil
from pathlib import Path
from typing import Any


RESUME_PREPARATION_SCHEMA = "scion.launcher_resume_preparation.v1"

_TERMINAL_ARTIFACT_REFS = (
    "run_status.json",
    "status.json",
    "campaign_summary.json",
    "exit.txt",
    "artifacts/formal_candidates/index.jsonl",
)


@dataclass(frozen=True)
class ResumePreparation:
    """Result of copying a resume source into a new run directory."""

    resume_source: Path
    campaign_dir: Path
    snapshot_dir: Path
    manifest_path: Path
    terminal_artifacts: tuple[dict[str, Any], ...]

    def source_had(self, ref: str) -> bool:
        return any(item.get("original_ref") == ref for item in self.terminal_artifacts)

    def manifest_ref(self, run_root: Path) -> str:
        return self.manifest_path.relative_to(run_root).as_posix()


@dataclass(frozen=True)
class LauncherResumeState:
    """Environment-facing resume fields shared by problem launchers."""

    resume_from_campaign: str = ""
    resume_snapshot_manifest_ref: str = ""
    copied_campaign_status_present: int = 0
    copied_campaign_summary_present: int = 0

    def env(self) -> dict[str, object]:
        return {
            "RESUME_FROM_CAMPAIGN": self.resume_from_campaign,
            "RESUME_SNAPSHOT_MANIFEST_REF": self.resume_snapshot_manifest_ref,
            "RESUME_COPIED_CAMPAIGN_STATUS_PRESENT": (
                self.copied_campaign_status_present
            ),
            "RESUME_COPIED_CAMPAIGN_SUMMARY_PRESENT": (
                self.copied_campaign_summary_present
            ),
        }


class ResumePreparationError(ValueError):
    """Raised when a launcher cannot prepare a resumed campaign."""


def prepare_launcher_campaign(
    *,
    resume_from_campaign: Path | None,
    campaign_dir: Path,
    run_root: Path,
) -> LauncherResumeState:
    """Prepare a new campaign directory and return launcher resume env fields."""

    if resume_from_campaign is None:
        campaign_dir.mkdir(parents=True, exist_ok=False)
        return LauncherResumeState()

    resume_source = resume_from_campaign.expanduser().resolve()
    if not resume_source.is_dir():
        raise ResumePreparationError(
            f"--resume-from-campaign is not a directory: {resume_source}"
        )
    run_root.mkdir(parents=True, exist_ok=False)
    preparation = prepare_resumed_campaign(
        resume_source=resume_source,
        campaign_dir=campaign_dir,
        run_root=run_root,
    )
    return LauncherResumeState(
        resume_from_campaign=str(resume_source),
        resume_snapshot_manifest_ref=preparation.manifest_ref(run_root),
        copied_campaign_status_present=int(preparation.source_had("run_status.json")),
        copied_campaign_summary_present=int(
            preparation.source_had("campaign_summary.json")
        ),
    )


def prepare_resumed_campaign(
    *,
    resume_source: Path,
    campaign_dir: Path,
    run_root: Path,
) -> ResumePreparation:
    """Copy a source campaign and quarantine stale terminal artifacts.

    Resume copies need durable state such as ``scion.db``, workspaces, champions,
    and branch evidence. They must not expose previous terminal files as the new
    run's canonical status or evidence index.
    """

    shutil.copytree(resume_source, campaign_dir)
    snapshot_dir = run_root / "resume_snapshot" / "campaign"
    terminal_artifacts = tuple(
        _quarantine_terminal_artifact(
            campaign_dir=campaign_dir,
            snapshot_dir=snapshot_dir,
            ref=ref,
        )
        for ref in _TERMINAL_ARTIFACT_REFS
        if (campaign_dir / ref).is_file()
    )
    manifest_path = run_root / "resume_snapshot" / "resume_source_manifest.v1.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": RESUME_PREPARATION_SCHEMA,
        "resume_from_campaign": str(resume_source),
        "campaign_dir": str(campaign_dir),
        "snapshot_dir": str(snapshot_dir),
        "current_run_canonical_terminal_artifacts_cleared": True,
        "terminal_artifacts": list(terminal_artifacts),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ResumePreparation(
        resume_source=resume_source,
        campaign_dir=campaign_dir,
        snapshot_dir=snapshot_dir,
        manifest_path=manifest_path,
        terminal_artifacts=terminal_artifacts,
    )


def _quarantine_terminal_artifact(
    *,
    campaign_dir: Path,
    snapshot_dir: Path,
    ref: str,
) -> dict[str, Any]:
    original = campaign_dir / ref
    target = snapshot_dir / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    stat = original.stat()
    digest = _sha256_file(original)
    shutil.move(str(original), str(target))
    _prune_empty_parents(original.parent, stop_at=campaign_dir)
    return {
        "original_ref": ref,
        "snapshot_ref": target.relative_to(campaign_dir.parent).as_posix(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": digest,
    }


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prune_empty_parents(path: Path, *, stop_at: Path) -> None:
    current = path
    while current != stop_at and current.is_dir():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
