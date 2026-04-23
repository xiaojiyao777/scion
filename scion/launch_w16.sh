#!/bin/bash
# launch_w16.sh — Launch W16 validation campaigns in tmux
#
# Usage:
#   ./scion/launch_w16.sh           # Launch first 2 campaigns
#   ./scion/launch_w16.sh --batch 2 # Launch batch 2 (campaigns 3-4)
#
# 12 campaigns total (2 models × 2 variants × 3 seeds), run 2 at a time.

set -euo pipefail

PYTHON=/home/clawd/miniconda3/envs/claw/bin/python
SCRIPT=/home/clawd/research/or-autoresearch-agent/scion/run_w16_campaign.py
SESSION=scion-w16

BATCH=${1:-1}

# Campaign matrix: model, variant, seed
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

# Batch: 2 campaigns per batch
IDX_A=$(( (BATCH - 1) * 2 ))
IDX_B=$(( IDX_A + 1 ))

if [ $IDX_A -ge ${#CAMPAIGNS[@]} ]; then
    echo "All 12 campaigns already launched (6 batches)."
    exit 0
fi

read -r MODEL_A VARIANT_A SEED_A <<< "${CAMPAIGNS[$IDX_A]}"
read -r MODEL_B VARIANT_B SEED_B <<< "${CAMPAIGNS[$IDX_B]}"

echo "Batch $BATCH:"
echo "  A: model=$MODEL_A variant=$VARIANT_A seed=$SEED_A"
echo "  B: model=$MODEL_B variant=$VARIANT_B seed=$SEED_B"

# Create/reuse tmux session
tmux kill-session -t $SESSION 2>/dev/null || true
tmux new-session -d -s $SESSION -n "campaign-a"

# Pane A
tmux send-keys -t $SESSION:0 \
    "$PYTHON $SCRIPT --model $MODEL_A --variant $VARIANT_A --seed $SEED_A --max-rounds 100 2>&1 | tee /tmp/scion_w16_${MODEL_A//[.-]/_}_${VARIANT_A}_s${SEED_A}.log" Enter

# Pane B (split horizontal)
tmux split-window -h -t $SESSION:0
tmux send-keys -t $SESSION:0.1 \
    "$PYTHON $SCRIPT --model $MODEL_B --variant $VARIANT_B --seed $SEED_B --max-rounds 100 2>&1 | tee /tmp/scion_w16_${MODEL_B//[.-]/_}_${VARIANT_B}_s${SEED_B}.log" Enter

echo ""
echo "Campaigns launched in tmux session '$SESSION'."
echo "  tmux attach -t $SESSION   # to monitor"
echo "  tmux ls                   # to check status"
echo ""
echo "Next batch: ./scion/launch_w16.sh $((BATCH + 1))"
