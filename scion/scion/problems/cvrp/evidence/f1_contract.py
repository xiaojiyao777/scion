"""Frozen constants and public error type for CVRP F1."""

from __future__ import annotations

from pathlib import Path

F1_SCHEMA = "scion.cvrp_f1_ancestry_manifest.v1"
F1_ROW_SCHEMA = "scion.cvrp_f1_ancestry_row.v1"
F1_TERMINAL_SCHEMA = "scion.cvrp_f1_ancestry_terminal.v1"
F1_DESIGN_SHA256 = "a8167117e147c8fe4bcccb808ad267a8a88fa9ba864e1389af40497d43d07faa"
F1_RUNTIME_COMMIT = "56bc445d07b19587ecb8e4b763ab448c4ceb9115"
F1_BRANCH_ID = "3203548d-f2dd-46ab-a055-e3efb53033e6"
F1_SOURCE_ROOT = Path(
    "/home/clawd/research/scion-experiments/"
    "v04-cvrp-direct-longitudinal-r11c-8r-gpt56sol-8r-gpt56sol-"
    "20260716T132422Z-claw"
)
F1_DATA_ROOT = Path("/home/clawd/research/or-autoresearch-agent/vrp")
F1_ORDER_CONTRACT = "scion.cvrp_f1_stage_local_williams.v1"
F1_SELECTED_SURFACE = "solver_design"
F1_WILLIAMS = ("ABDC", "BCAD", "CDBA", "DACB")
F1_ARM_ORDER = ("champion", "h1_only", "swap_only", "cumulative")
F1_ARM_SYMBOL = {
    "champion": "A",
    "h1_only": "B",
    "swap_only": "C",
    "cumulative": "D",
}
F1_ARM_HASH = {
    "champion": "06820ecdb062c96326b194d76b532140af1354036a79688ca4f62e775e179e79",
    "h1_only": "818bd833104222e0d9d58f08df626cc5c44975091ea78c2858bf69ece4976fd3",
    "swap_only": "1b1bd55421d2a9c94b89c61aa95fc926e6dca6f0ba8e5b37eff27b7e8c7cd73e",
    "cumulative": "09a39f11b7f4e42e049074d009acf98d844443ef50dc46f69d65abd9bd50a911",
}
F1_SEEDS = {
    "screening": (11, 29, 43, 59),
    "validation": (47, 53, 71, 83),
}
F1_CASES = {
    "screening": (
        ("cvrplib/A/A-n64-k9.vrp", 30),
        ("cvrplib/B/B-n63-k10.vrp", 30),
        ("cvrplib/E/E-n101-k14.vrp", 30),
        ("cvrplib/P/P-n65-k10.vrp", 30),
        ("cvrplib/CMT/CMT2.vrp", 30),
        ("cvrplib/CMT/CMT4.vrp", 45),
        ("cvrplib/M/M-n200-k17.vrp", 45),
        ("cvrplib/X/X-n110-k13.vrp", 30),
    ),
    "validation": (
        ("cvrplib/A/A-n60-k9.vrp", 30),
        ("cvrplib/P/P-n70-k10.vrp", 30),
        ("cvrplib/tai/tai75c.vrp", 30),
        ("cvrplib/tai/tai150a.vrp", 60),
        ("cvrplib/tai/tai150b.vrp", 60),
        ("cvrplib/X/X-n120-k6.vrp", 45),
        ("cvrplib/X/X-n129-k18.vrp", 45),
        ("cvrplib/X/X-n190-k8.vrp", 60),
    ),
}

_ROOT_AUTHORITIES = {
    "prepared_cvrp_data_identity.v1.json": (
        "7efe0fc8f293853624e6fcb910fe57342bc5de906f5f58102708529477b284b6"
    ),
    "pre_campaign_split_data.v1.json": (
        "5e6e7f74325e70a4490d827b25e5d070ec130c2cbc0ee3a5027a7493abc87dad"
    ),
    "post_campaign_split_data.v1.json": (
        "5e6e7f74325e70a4490d827b25e5d070ec130c2cbc0ee3a5027a7493abc87dad"
    ),
    "prepared_run_manifest.v1.json": (
        "e7ce911810af1b480f47ef75baa186994616b33e03de94d907f3a81596ab0aea"
    ),
}
_PROTECTED_AUTHORITIES = {
    "campaign/artifacts/formal_candidates/index.jsonl": (
        "c2d24ff28c5008fba1b65dcb4f9f243802f17d4bd3c0571498084635b6b145ed"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-5691ed4639659108/"
    "candidate.diff": (
        "1853a0e8d8592002d9a25a0becbb9632d7265318488118169b43e536df92d48f"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-5691ed4639659108/"
    "proposal.diff": (
        "1853a0e8d8592002d9a25a0becbb9632d7265318488118169b43e536df92d48f"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-5691ed4639659108/"
    "candidate.patch.json": (
        "6a25128b0c0cf61ff9d045a56bd3402dba5f43330a09ab86c84a6081eb3188ae"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-c936cb9fb7e7c961/"
    "candidate.diff": (
        "1853a0e8d8592002d9a25a0becbb9632d7265318488118169b43e536df92d48f"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-c936cb9fb7e7c961/"
    "proposal.diff": (
        "1853a0e8d8592002d9a25a0becbb9632d7265318488118169b43e536df92d48f"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-c936cb9fb7e7c961/"
    "candidate.patch.json": (
        "cb3ba6ce68e8134b7b1322fea50e6a1134b51374254da3eacfce51472096b43a"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-86816129-fe73-4e1f-8ecc-be93a600eaae-fd7e5088f03c7a3c/"
    "candidate.diff": (
        "afc9f3ecba5e418c97e2faf3e2e57d75253bfc201e5e634e5e32ed6d4a2c57d6"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-86816129-fe73-4e1f-8ecc-be93a600eaae-fd7e5088f03c7a3c/"
    "proposal.diff": (
        "e0a184e94e3f0c6d767a7db223e131ac2f10797875870afe538e7cac99c5c395"
    ),
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-86816129-fe73-4e1f-8ecc-be93a600eaae-fd7e5088f03c7a3c/"
    "candidate.patch.json": (
        "36565e454e3364d7924ac8b702abb05f384fd52394238598da97011265807e02"
    ),
    "campaign/metrics/83fe3b49-df68-4b14-8c74-7e6f0d2f62a8.json": (
        "e8318925fa3157cbc1d537d22b7be8755b346bd916999ecbacf5de2fa6b99bd8"
    ),
    "campaign/metrics/caf87853-0267-4f14-bcbc-f908f8e8cfbc.json": (
        "355857546b869ecab960546e1bbaa981c6ed9401dea440dedcc8d3e769c5969b"
    ),
}
_H1_PATCH = (
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-1bc9ebd2-325a-42ce-bdee-44375b90f0d7-c936cb9fb7e7c961/"
    "candidate.patch.json"
)
_H2_PATCH = (
    "campaign/artifacts/formal_candidates/3203548d/"
    "screening-86816129-fe73-4e1f-8ecc-be93a600eaae-fd7e5088f03c7a3c/"
    "candidate.patch.json"
)
_DESIGN_RELATIVE = "scion/docs/planning/v0.4/v0.4-cvrp-f1-ancestry-matrix-20260718.md"
_GENERATED_SUFFIXES = frozenset({".pyc", ".pyo"})


class CvrpF1Error(RuntimeError):
    """Raised when the fixed F1 execution contract is not provable."""
