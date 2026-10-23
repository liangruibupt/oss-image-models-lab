#!/usr/bin/env bash
# Shared helpers: load config, resolve paths, wrap AWS calls.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/config.env"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "ERROR: $CONFIG_FILE not found. Copy config.env.example -> config.env and fill it in." >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${REGION:?set REGION in config.env}"

aws_cli() {
  # Thin wrapper so every call carries region/profile consistently.
  aws --region "$REGION" ${AWS_PROFILE:+--profile "$AWS_PROFILE"} "$@"
}

log()  { printf '\033[1;34m[lab]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[lab]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[lab]\033[0m %s\n' "$*" >&2; exit 1; }

# Write a KEY=VALUE back into config.env (used by provision.sh to persist IDs).
save_config() {
  local key="$1" val="$2"
  if grep -q "^export ${key}=" "$CONFIG_FILE"; then
    sed -i.bak "s|^export ${key}=.*|export ${key}=\"${val}\"|" "$CONFIG_FILE" && rm -f "$CONFIG_FILE.bak"
  else
    echo "export ${key}=\"${val}\"" >> "$CONFIG_FILE"
  fi
}

instance_public_ip() {
  aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
}

instance_state() {
  aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].State.Name' --output text
}
