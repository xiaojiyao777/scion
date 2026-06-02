"""External proposal/workspace ingestion for Scion."""

from scion.external_ingest.ingest import (
    ExternalIngestResult,
    ExternalProposalIngestor,
    MockSmokeResult,
    run_mock_smoke,
)
from scion.external_ingest.schema import (
    ExternalProposalManifest,
    load_external_manifest,
)

__all__ = [
    "ExternalIngestResult",
    "ExternalProposalIngestor",
    "ExternalProposalManifest",
    "MockSmokeResult",
    "load_external_manifest",
    "run_mock_smoke",
]
