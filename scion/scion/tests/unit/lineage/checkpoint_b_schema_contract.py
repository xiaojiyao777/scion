"""Frozen test-only SQLite contract for the dormant Checkpoint-B vertical.

Production schema ownership remains with the separately reviewed offline
activation work.  These constants make the accepted vertical-correction DDL
explicit in focused tests without importing a production schema bootstrap.
"""

from __future__ import annotations


CHECKPOINT_B_MINIMAL_EXPERIMENT_EVENTS_DDL = """
CREATE TABLE experiment_events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    hypothesis_id TEXT,
    timestamp TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    stage TEXT NOT NULL,
    audit_payload_json TEXT NOT NULL
);
"""


CHECKPOINT_B_PRODUCTION_LIKE_EXPERIMENT_EVENTS_DDL = """
CREATE TABLE experiment_events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT,
    branch_id TEXT NOT NULL,
    hypothesis_id TEXT,
    timestamp TEXT NOT NULL,
    event_kind TEXT DEFAULT 'experiment',
    code_hash TEXT,
    patch_action TEXT,
    patch_file TEXT,
    hypothesis_text TEXT,
    contract_passed TEXT,
    verification_passed TEXT,
    contract_result TEXT,
    verification_result TEXT,
    canary_result TEXT,
    stage TEXT,
    case_ids TEXT,
    seed_set TEXT,
    raw_metrics_ref TEXT,
    screening_n_cases INTEGER,
    screening_win_rate REAL,
    screening_win_rate_scope TEXT,
    screening_case_wins INTEGER,
    screening_case_losses INTEGER,
    screening_case_ties INTEGER,
    screening_case_total INTEGER,
    screening_case_win_rate REAL,
    screening_case_level_gate_wins INTEGER,
    screening_case_level_gate_losses INTEGER,
    screening_case_level_gate_ties INTEGER,
    screening_case_level_gate_total INTEGER,
    screening_case_level_gate_win_rate REAL,
    screening_gate_win_rate REAL,
    screening_pair_wins INTEGER,
    screening_pair_losses INTEGER,
    screening_pair_ties INTEGER,
    screening_pair_total INTEGER,
    screening_pair_win_rate REAL,
    screening_median_delta REAL,
    screening_ci_low REAL,
    screening_ci_high REAL,
    decision_features_json TEXT,
    decision TEXT,
    decision_reason TEXT,
    scheduler_slot TEXT,
    scheduler_reason TEXT,
    model_id TEXT,
    protocol_version TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    execution_outcome TEXT,
    execution_outcome_reason_code TEXT,
    execution_outcome_detail TEXT,
    execution_outcome_provenance_json TEXT,
    contract_diagnostics_json TEXT,
    audit_payload_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


# Verbatim from the accepted vertical correction, lines 739-846.  Production
# DDL remains intentionally absent from the dormant implementation.
CHECKPOINT_B_BINDING_SCHEMA_CONTRACT_DDL = """
CREATE TABLE proposal_hypothesis_attempt_bindings (
    campaign_id TEXT NOT NULL
        CHECK(typeof(campaign_id) = 'text'
              AND length(campaign_id) > 0
              AND campaign_id = trim(campaign_id)),
    provider_attempt_id TEXT NOT NULL
        CHECK(typeof(provider_attempt_id) = 'text'
              AND length(provider_attempt_id) > 0
              AND provider_attempt_id = trim(provider_attempt_id)),
    started_event_id TEXT NOT NULL UNIQUE
        CHECK(typeof(started_event_id) = 'text'
              AND length(started_event_id) > 0
              AND started_event_id = trim(started_event_id)),
    generated_event_id TEXT NOT NULL UNIQUE
        CHECK(typeof(generated_event_id) = 'text'
              AND length(generated_event_id) > 0
              AND generated_event_id = trim(generated_event_id)),
    branch_id TEXT NOT NULL
        CHECK(typeof(branch_id) = 'text'
              AND length(branch_id) > 0
              AND branch_id = trim(branch_id)),
    branch_owner_revision INTEGER NOT NULL
        CHECK(typeof(branch_owner_revision) = 'integer'
              AND branch_owner_revision >= 0),
    branch_storage_sha256 TEXT NOT NULL
        CHECK(typeof(branch_storage_sha256) = 'text'
              AND length(branch_storage_sha256) = 64
              AND branch_storage_sha256 NOT GLOB '*[^0-9a-f]*'),
    hypothesis_id TEXT NOT NULL UNIQUE
        CHECK(typeof(hypothesis_id) = 'text'
              AND length(hypothesis_id) > 0
              AND hypothesis_id = trim(hypothesis_id)),
    parent_hypothesis_id TEXT,
    parent_owner_revision INTEGER,
    parent_storage_sha256 TEXT,
    proposal_digest TEXT NOT NULL
        CHECK(typeof(proposal_digest) = 'text'
              AND length(proposal_digest) = 64
              AND proposal_digest NOT GLOB '*[^0-9a-f]*'),
    hypothesis_storage_sha256 TEXT NOT NULL
        CHECK(typeof(hypothesis_storage_sha256) = 'text'
              AND length(hypothesis_storage_sha256) = 64
              AND hypothesis_storage_sha256 NOT GLOB '*[^0-9a-f]*'),
    transition_group_sha256 TEXT NOT NULL
        CHECK(typeof(transition_group_sha256) = 'text'
              AND length(transition_group_sha256) = 64
              AND transition_group_sha256 NOT GLOB '*[^0-9a-f]*'),
    binding_protocol_generation TEXT NOT NULL
        CHECK(binding_protocol_generation = 'proposal-h-binding.v1'),
    created_at TEXT NOT NULL
        CHECK(typeof(created_at) = 'text'
              AND length(created_at) > 0
              AND created_at = trim(created_at)),
    PRIMARY KEY (campaign_id, provider_attempt_id),
    CHECK(started_event_id <> generated_event_id),
    CHECK(
        (parent_hypothesis_id IS NULL
         AND parent_owner_revision IS NULL
         AND parent_storage_sha256 IS NULL)
        OR
        (typeof(parent_hypothesis_id) = 'text'
         AND length(parent_hypothesis_id) > 0
         AND parent_hypothesis_id = trim(parent_hypothesis_id)
         AND typeof(parent_owner_revision) = 'integer'
         AND parent_owner_revision >= 0
         AND typeof(parent_storage_sha256) = 'text'
         AND length(parent_storage_sha256) = 64
         AND parent_storage_sha256 NOT GLOB '*[^0-9a-f]*')
    ),
    FOREIGN KEY (campaign_id) REFERENCES campaign_identity(campaign_id),
    FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
    FOREIGN KEY (started_event_id) REFERENCES experiment_events(event_id),
    FOREIGN KEY (generated_event_id) REFERENCES experiment_events(event_id),
    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(hypothesis_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (parent_hypothesis_id) REFERENCES hypotheses(hypothesis_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TRIGGER proposal_h_binding_immutable_update
BEFORE UPDATE ON proposal_hypothesis_attempt_bindings
BEGIN
    SELECT RAISE(ABORT, 'proposal hypothesis binding is immutable');
END;

CREATE TRIGGER proposal_h_binding_immutable_delete
BEFORE DELETE ON proposal_hypothesis_attempt_bindings
BEGIN
    SELECT RAISE(ABORT, 'proposal hypothesis binding is immutable');
END;

CREATE TRIGGER proposal_attempt_event_immutable_update
BEFORE UPDATE ON experiment_events
WHEN (OLD.event_kind = 'proposal_attempt_transition'
      AND OLD.stage = 'proposal_hypothesis')
  OR (NEW.event_kind = 'proposal_attempt_transition'
      AND NEW.stage = 'proposal_hypothesis')
BEGIN
    SELECT RAISE(ABORT, 'proposal attempt event is append-only');
END;

CREATE TRIGGER proposal_attempt_event_immutable_delete
BEFORE DELETE ON experiment_events
WHEN OLD.event_kind = 'proposal_attempt_transition'
 AND OLD.stage = 'proposal_hypothesis'
BEGIN
    SELECT RAISE(ABORT, 'proposal attempt event is append-only');
END;
"""


CHECKPOINT_B_DROP_IMMUTABILITY_TRIGGERS_FOR_CORRUPTION_DDL = """
DROP TRIGGER proposal_h_binding_immutable_update;
DROP TRIGGER proposal_h_binding_immutable_delete;
DROP TRIGGER proposal_attempt_event_immutable_update;
DROP TRIGGER proposal_attempt_event_immutable_delete;
"""
