"""Import boundary for the production direct-v3 campaign entrypoint."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCION_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_IMPORT_PROBE = r"""
import json
from pathlib import Path
import sys

project_root = Path(sys.argv[1]).resolve(strict=True)
sys.path.insert(0, str(project_root))

import scion.cli.main  # noqa: F401
from scion.core.campaign import CampaignManager
import scion.core.campaign_composition  # noqa: F401

assert CampaignManager.__module__ == "scion.core.campaign"
production_modules = sorted(
    name
    for name in sys.modules
    if name.startswith("scion.") and not name.startswith("scion.tests.")
)
print("SCION_IMPORTS=" + json.dumps(production_modules, separators=(",", ":")))
"""

_FORBIDDEN_EXACT_MODULES = frozenset(
    {
        "scion.contract.capability_owner",
        "scion.core.campaign_owner_registry",
        "scion.core.decision_completion",
        "scion.core.decision_completion_transaction",
        "scion.core.durable_owner_codec",
        "scion.core.state_payload",
        "scion.lineage.branch_owner_store",
        "scion.lineage.durable_owner",
        "scion.lineage.hypothesis_owner_store",
        "scion.lineage.owner_transaction",
        "scion.lineage.proposal_attempt_owner",
        "scion.lineage.sqlite_connection",
        "scion.core.verified_candidate_commit",
        "scion.proposal.hypothesis_generation_authority",
        "scion.runtime.execution.cgroup_v2",
        "scion.runtime.execution.external_installation",
        "scion.runtime.execution.external_linux",
        "scion.runtime.execution.invocation_terminal",
        "scion.runtime.execution.launch_authority",
        "scion.runtime.execution.spawn_backend",
    }
)
_FORBIDDEN_MODULE_PREFIXES = (
    "scion.problems.warehouse_delivery.w3_",
    "scion.runtime.execution.systemd",
)
_FORBIDDEN_BASENAME_FRAGMENTS = (
    "capability",
    "issuance",
    "issuer",
    "lease",
)


def _is_forbidden_production_module(module_name: str) -> bool:
    if module_name in _FORBIDDEN_EXACT_MODULES:
        return True
    if module_name.startswith(_FORBIDDEN_MODULE_PREFIXES):
        return True
    basename = module_name.rsplit(".", 1)[-1]
    return any(fragment in basename for fragment in _FORBIDDEN_BASENAME_FRAGMENTS)


def test_direct_v3_entry_does_not_import_dormant_authority_stacks(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"

    completed = subprocess.run(
        (sys.executable, "-c", _IMPORT_PROBE, str(SCION_PROJECT_ROOT)),
        cwd=tmp_path,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr

    marker = "SCION_IMPORTS="
    encoded_imports = next(
        (
            line.removeprefix(marker)
            for line in completed.stdout.splitlines()
            if line.startswith(marker)
        ),
        None,
    )
    assert encoded_imports is not None, completed.stdout
    imported_modules = json.loads(encoded_imports)
    assert isinstance(imported_modules, list)

    forbidden = sorted(
        module_name
        for module_name in imported_modules
        if isinstance(module_name, str) and _is_forbidden_production_module(module_name)
    )
    assert forbidden == []
