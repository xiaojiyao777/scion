#!/bin/bash
# auto_w16.sh — Automatically launch W16 batches 2-6 after batch 1 completes.
#
# Usage (from repo root, after batch 1 is already running):
#   nohup setsid bash scion/auto_w16.sh > /tmp/auto_w16.log 2>&1 &
#   echo $!  # save PID to kill if needed
#
# Progress:
#   tail -f /tmp/auto_w16.log

set -uo pipefail

LAUNCH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/launch_w16.sh"
EXP_BASE="$HOME/research/scion-experiments/v03-validation"

# Must match launch_w16.sh exactly
CAMPAIGNS=(
    "claude-sonnet-4-6 synthetic 11"
    "gpt-5.4-mini      synthetic 11"
    "claude-sonnet-4-6 synthetic 29"
    "gpt-5.4-mini      synthetic 29"
    "claude-sonnet-4-6 synthetic 47"
    "gpt-5.4-mini      synthetic 47"
    "claude-sonnet-4-6 production 11"
    "gpt-5.4-mini      production 11"
    "claude-sonnet-4-6 production 29"
    "gpt-5.4-mini      production 29"
    "claude-sonnet-4-6 production 47"
    "gpt-5.4-mini      production 47"
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Mirrors run_w16_campaign.py: model.replace("claude-","").replace(".","")
model_short() { echo "$1" | sed 's/claude-//' | tr -d '.'; }

# Return the campaign output dir for CAMPAIGNS index N
campaign_dir() {
    local idx=$1
    read -r model variant seed <<< "${CAMPAIGNS[$idx]}"
    echo "$EXP_BASE/$(model_short "$model")_${variant}_seed${seed}"
}

# Block until both campaign_summary.json files for BATCH exist, or timeout.
wait_for_batch() {
    local batch=$1
    local idx_a=$(( (batch - 1) * 2 ))
    local idx_b=$(( idx_a + 1 ))
    local dir_a dir_b
    dir_a=$(campaign_dir "$idx_a")
    dir_b=$(campaign_dir "$idx_b")

    log "Waiting for batch $batch to finish..."
    log "  A: $dir_a"
    log "  B: $dir_b"

    local max_wait=$(( 16 * 3600 ))   # 16h hard cap per batch
    local elapsed=0
    local interval=60

    while true; do
        local a_done=0 b_done=0
        [[ -f "$dir_a/campaign_summary.json" ]] && a_done=1
        [[ -f "$dir_b/campaign_summary.json" ]] && b_done=1

        if [[ $a_done -eq 1 && $b_done -eq 1 ]]; then
            log "Batch $batch done (both summaries written)."
            return 0
        fi

        if [[ $elapsed -ge $max_wait ]]; then
            log "WARNING: batch $batch timeout after ${max_wait}s — proceeding regardless."
            log "  A done=$a_done  B done=$b_done"
            return 0
        fi

        # Heartbeat every 30 min
        if [[ $((elapsed % 1800)) -eq 0 && $elapsed -gt 0 ]]; then
            log "  Still waiting... A_done=$a_done B_done=$b_done elapsed=$(( elapsed/60 ))m"
        fi

        sleep $interval
        elapsed=$(( elapsed + interval ))
    done
}

# ── Main ──────────────────────────────────────────────────────────────────────

START_BATCH=${1:-2}
END_BATCH=6

log "============================================================"
log "auto_w16.sh — W16 batch auto-launcher"
log "Will run batches $START_BATCH through $END_BATCH"
log "============================================================"

for batch in $(seq "$START_BATCH" "$END_BATCH"); do
    prev=$(( batch - 1 ))

    wait_for_batch "$prev"

    log "Launching batch $batch..."
    bash "$LAUNCH" "$batch"
    log "Batch $batch launched."
    log "------------------------------------------------------------"
done

# Wait for the last batch to finish too, so the log has a clean completion line
wait_for_batch "$END_BATCH"

log "============================================================"
log "All W16 batches complete."
log "Results: $EXP_BASE"
log "============================================================"
