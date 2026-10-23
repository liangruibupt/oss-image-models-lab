#!/usr/bin/env bash
# One-time: create the GPU instance + a dedicated EBS weights volume + security group.
# Run this ONCE. Afterwards use start.sh / stop.sh for the daily loop.
set -euo pipefail
source "$(dirname "$0")/common.sh"

: "${INSTANCE_TYPE:?}" ; : "${KEY_NAME:?}"
: "${WEIGHTS_VOLUME_SIZE_GB:?}" ; : "${ROOT_VOLUME_SIZE_GB:?}"

if [[ -n "${INSTANCE_ID:-}" ]]; then
  die "INSTANCE_ID already set ($INSTANCE_ID). Looks provisioned. Use start.sh, or clear it in config.env to re-provision."
fi

# --- 1. Resolve a Deep Learning AMI (Ubuntu 22.04, Nvidia driver preinstalled) ---
if [[ -z "${AMI_ID:-}" ]]; then
  log "Resolving latest Deep Learning OSS Nvidia Driver AMI (Ubuntu 22.04)..."
  AMI_ID=$(aws_cli ssm get-parameters \
    --names /aws/service/deeplearning/ami/x86_64/oss-nvidia-driver-gpu-pytorch-2.5-ubuntu-22.04/latest/ami-id \
    --query 'Parameters[0].Value' --output text 2>/dev/null || true)
  [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]] && die "Could not resolve DLAMI via SSM. Set AMI_ID manually in config.env."
  save_config AMI_ID "$AMI_ID"
fi
log "Using AMI: $AMI_ID"

# --- 2. Security group ---
VPC_ID=$(aws_cli ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG_NAME="oss-image-lab-sg"
SECURITY_GROUP_ID=$(aws_cli ec2 describe-security-groups \
  --filters Name=group-name,Values="$SG_NAME" Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")
if [[ "$SECURITY_GROUP_ID" == "None" || -z "$SECURITY_GROUP_ID" ]]; then
  log "Creating security group $SG_NAME ..."
  SECURITY_GROUP_ID=$(aws_cli ec2 create-security-group --group-name "$SG_NAME" \
    --description "OSS image models lab" --vpc-id "$VPC_ID" --query 'GroupId' --output text)
  CIDR="${MY_IP_CIDR:-0.0.0.0/0}"
  [[ "$CIDR" == "0.0.0.0/0" ]] && warn "SSH open to 0.0.0.0/0 — set MY_IP_CIDR in config.env to lock it down."
  aws_cli ec2 authorize-security-group-ingress --group-id "$SECURITY_GROUP_ID" \
    --protocol tcp --port 22 --cidr "$CIDR" >/dev/null
  # ComfyUI UI port 8188 — only to your IP; we tunnel via SSH by default so this is optional.
  [[ -n "${MY_IP_CIDR:-}" ]] && aws_cli ec2 authorize-security-group-ingress \
    --group-id "$SECURITY_GROUP_ID" --protocol tcp --port 8188 --cidr "$MY_IP_CIDR" >/dev/null || true
fi
save_config SECURITY_GROUP_ID "$SECURITY_GROUP_ID"
log "Security group: $SECURITY_GROUP_ID"

# --- 3. Launch instance (on-demand; root volume gp3) ---
log "Launching $INSTANCE_TYPE (on-demand)..."
INSTANCE_ID=$(aws_cli ec2 run-instances \
  --image-id "$AMI_ID" --instance-type "$INSTANCE_TYPE" --key-name "$KEY_NAME" \
  --security-group-ids "$SECURITY_GROUP_ID" \
  --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=${ROOT_VOLUME_SIZE_GB},VolumeType=gp3,DeleteOnTermination=true}" \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=oss-image-lab},{Key=project,Value=oss-image-models-lab}]' \
  --query 'Instances[0].InstanceId' --output text)
save_config INSTANCE_ID "$INSTANCE_ID"
log "Instance: $INSTANCE_ID — waiting for running..."
aws_cli ec2 wait instance-running --instance-ids "$INSTANCE_ID"

AZ=$(aws_cli ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].Placement.AvailabilityZone' --output text)

# --- 4. Dedicated weights volume (persists across stop; holds ~32GB weights + ComfyUI) ---
log "Creating weights EBS volume (${WEIGHTS_VOLUME_SIZE_GB}GB gp3) in $AZ ..."
WEIGHTS_VOLUME_ID=$(aws_cli ec2 create-volume --availability-zone "$AZ" \
  --size "$WEIGHTS_VOLUME_SIZE_GB" --volume-type gp3 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=oss-image-lab-weights},{Key=project,Value=oss-image-models-lab}]' \
  --query 'VolumeId' --output text)
save_config WEIGHTS_VOLUME_ID "$WEIGHTS_VOLUME_ID"
aws_cli ec2 wait volume-available --volume-ids "$WEIGHTS_VOLUME_ID"
log "Attaching weights volume as /dev/sdf ..."
aws_cli ec2 attach-volume --volume-id "$WEIGHTS_VOLUME_ID" --instance-id "$INSTANCE_ID" --device /dev/sdf >/dev/null

IP=$(instance_public_ip)
cat <<EOF

✅ Provisioned.
  Instance:  $INSTANCE_ID ($INSTANCE_TYPE)
  Public IP: $IP
  Weights vol: $WEIGHTS_VOLUME_ID (attached /dev/sdf)

Next:
  1) Copy this repo to the box:  rsync -av -e "ssh -i $SSH_KEY_PATH" ./ ubuntu@$IP:~/oss-image-models-lab/
  2) ssh -i $SSH_KEY_PATH ubuntu@$IP
  3) cd ~/oss-image-models-lab && ./scripts/setup-comfyui.sh
  4) ./scripts/run-test.sh
  5) Back on your laptop:  ./scripts/stop.sh   (stops billing; weights volume kept)
EOF
