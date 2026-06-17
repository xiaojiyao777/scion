"""Default parameters for the branch-owned CVRP solver-design algorithm."""
from __future__ import annotations

ENABLE_BASELINE_ALGORITHM = True

SIGMA_BEST = 33.0
SIGMA_BETTER = 9.0
SIGMA_ACCEPTED = 13.0

BASELINE_TIME_FRACTION = 0.80
DESTROY_RATIO = (0.10, 0.40)
SEGMENT_LENGTH = 100
REACTION_FACTOR = 0.1
VNS_MAX_NO_IMPROVE = 5000
USE_VNS = True
ENABLE_INITIAL_VNS = True
ENABLE_EMBEDDED_VNS = True
# Positive values run embedded VNS every N ALNS iterations. Zero disables the
# fixed cadence and leaves repair-improvement triggering available.
EMBEDDED_VNS_CADENCE = 1
# Positive values force embedded VNS during the first N ALNS iterations before
# cadence thinning applies. The default preserves canonical every-iteration VNS.
EMBEDDED_VNS_EARLY_ALWAYS_ITERATIONS = 0
# Positive values force embedded VNS while its cumulative runtime share within
# the ALNS loop is below the configured floor; cadence thinning applies after.
EMBEDDED_VNS_MIN_RUNTIME_SHARE = 0.0
# Positive values cap embedded VNS once its cumulative runtime share reaches the
# configured ceiling. Zero disables the cap and preserves canonical behavior.
EMBEDDED_VNS_MAX_RUNTIME_SHARE = 0.0
EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE = True
EMBEDDED_VNS_CAP_RESCUE_CADENCE = 0
EMBEDDED_VNS_RUN_ON_REPAIR_IMPROVEMENT = True
EMBEDDED_VNS_DIAGNOSTIC_PHASE = ""
ENABLE_SIZE70_TWO_OPT_FALLBACK = True
SIZE70_TWO_OPT_MIN_CUSTOMERS = 70
CW_THRESHOLD = 1500
VNS_THRESHOLD = 1200
ALNS_THRESHOLD = 2000
MAX_DESTROY_CUSTOMERS = 200
EXIT_RESERVE_FRACTION = 0.03

_EPS = 1e-9
