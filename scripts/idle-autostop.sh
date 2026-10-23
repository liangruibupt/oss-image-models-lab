#!/usr/bin/env bash
# RUN THIS ON THE GPU INSTANCE (once) to install an idle auto-shutdown safety net.
# If GPU utilization stays at 0% for IDLE_SHUTDOWN_MINUTES, the box shuts itself
# down — so a forgotten instance can't quietly burn money.
set -euo pipefail

MINUTES="${IDLE_SHUTDOWN_MINUTES:-30}"
CHECK_INTERVAL=60          # seconds between samples
NEEDED=$(( MINUTES * 60 / CHECK_INTERVAL ))

cat <<EOF | sudo tee /usr/local/bin/idle-autostop.sh >/dev/null
#!/usr/bin/env bash
set -euo pipefail
NEEDED=$NEEDED
idle=0
while true; do
  util=\$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1 | tr -d ' ')
  if [[ "\${util:-0}" -eq 0 ]]; then idle=\$((idle+1)); else idle=0; fi
  if [[ \$idle -ge \$NEEDED ]]; then
    logger "idle-autostop: GPU idle ${MINUTES}min — shutting down"
    sudo shutdown -h now
  fi
  sleep $CHECK_INTERVAL
done
EOF
sudo chmod +x /usr/local/bin/idle-autostop.sh

cat <<'EOF' | sudo tee /etc/systemd/system/idle-autostop.service >/dev/null
[Unit]
Description=Auto-shutdown when GPU idle (oss-image-lab cost guard)
After=network.target
[Service]
ExecStart=/usr/local/bin/idle-autostop.sh
Restart=always
[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now idle-autostop.service
echo "[idle] Auto-shutdown armed: GPU idle ${MINUTES}min -> shutdown. Disable: sudo systemctl disable --now idle-autostop.service"
