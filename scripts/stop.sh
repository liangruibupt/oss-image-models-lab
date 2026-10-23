#!/usr/bin/env bash
# Stop the instance (halts compute billing). The weights EBS volume is kept.
set -euo pipefail
source "$(dirname "$0")/common.sh"
: "${INSTANCE_ID:?INSTANCE_ID empty — run provision.sh first}"

state="$(instance_state)"
if [[ "$state" == "stopped" ]]; then
  log "Already stopped."
  exit 0
fi
log "Stopping $INSTANCE_ID ..."
aws_cli ec2 stop-instances --instance-ids "$INSTANCE_ID" >/dev/null
aws_cli ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
log "Stopped. Compute billing halted. You still pay for EBS storage only."
log "Weights volume ${WEIGHTS_VOLUME_ID:-<none>} retained — next start.sh reuses it, no re-download."
