#!/usr/bin/env bash
# Show instance state, IP, uptime-this-run and a rough cost estimate.
set -euo pipefail
source "$(dirname "$0")/common.sh"
: "${INSTANCE_ID:?INSTANCE_ID empty — run provision.sh first}"

state="$(instance_state)"
log "Instance: $INSTANCE_ID ($INSTANCE_TYPE)"
log "State:    $state"

if [[ "$state" == "running" ]]; then
  IP="$(instance_public_ip)"
  LAUNCH=$(aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].LaunchTime' --output text)
  log "Public IP: $IP"
  log "Launched:  $LAUNCH (this run)"
  # Rough on-demand rate table (us-east-1, re-check before trusting).
  declare -A RATE=( [g6e.xlarge]=1.861 [g6.xlarge]=0.805 [g5.xlarge]=1.006 [g4dn.xlarge]=0.526 )
  r="${RATE[$INSTANCE_TYPE]:-}"
  if [[ -n "$r" ]]; then
    now=$(date +%s); start=$(date -d "$LAUNCH" +%s 2>/dev/null || echo "$now")
    hrs=$(awk -v a="$now" -v b="$start" 'BEGIN{printf "%.2f",(a-b)/3600}')
    cost=$(awk -v h="$hrs" -v r="$r" 'BEGIN{printf "%.2f",h*r}')
    log "~Uptime this run: ${hrs}h  →  ~\$${cost} (at \$${r}/hr on-demand, estimate only)"
  fi
  warn "Still running — ./scripts/stop.sh to halt billing."
fi
