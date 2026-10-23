#!/usr/bin/env bash
# Start the (already-provisioned) instance and print its new public IP.
set -euo pipefail
source "$(dirname "$0")/common.sh"
: "${INSTANCE_ID:?INSTANCE_ID empty — run provision.sh first}"

state="$(instance_state)"
if [[ "$state" == "running" ]]; then
  log "Already running."
else
  log "Starting $INSTANCE_ID ..."
  aws_cli ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
  aws_cli ec2 wait instance-running --instance-ids "$INSTANCE_ID"
fi

IP="$(instance_public_ip)"
log "Running. Public IP: $IP"
echo
echo "  SSH:            ssh -i $SSH_KEY_PATH ubuntu@$IP"
echo "  ComfyUI tunnel: ssh -i $SSH_KEY_PATH -L 8188:localhost:8188 ubuntu@$IP   # then open http://localhost:8188"
echo
warn "Remember to ./scripts/stop.sh when done — on-demand billing runs while 'running'."
