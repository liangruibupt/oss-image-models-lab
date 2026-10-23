#!/usr/bin/env bash
# RUN THIS ON THE GPU INSTANCE (not your laptop).
# Mounts the weights volume, installs ComfyUI + Qwen-Image-2.1 custom nodes,
# and downloads the model weights from Hugging Face.
set -euo pipefail

MOUNT="/mnt/weights"
COMFY="$MOUNT/ComfyUI"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[setup] === 1. Mount weights volume at $MOUNT ==="
# The dedicated EBS volume shows up as the second NVMe disk. Find the unmounted one.
DEV=$(lsblk -dpno NAME,MOUNTPOINT | awk '$2=="" {print $1}' | grep -E 'nvme1n1|xvdf|sdf' | head -1 || true)
if [[ -z "$DEV" ]]; then
  echo "[setup] No extra unmounted disk found — assuming $MOUNT already set up."
else
  sudo file -s "$DEV" | grep -q ext4 || { echo "[setup] Formatting $DEV ext4 (first time)"; sudo mkfs -t ext4 "$DEV"; }
  sudo mkdir -p "$MOUNT"
  sudo mount "$DEV" "$MOUNT"
  sudo chown -R "$USER":"$USER" "$MOUNT"
  # persist across reboots
  UUID=$(sudo blkid -s UUID -o value "$DEV")
  grep -q "$UUID" /etc/fstab || echo "UUID=$UUID $MOUNT ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab
fi

echo "[setup] === 2. Install ComfyUI ==="
if [[ ! -d "$COMFY" ]]; then
  git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFY"
fi
cd "$COMFY"
python3 -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip wheel
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
pip install -r "$REPO_DIR/comfyui/requirements.extra.txt"

echo "[setup] === 3. Custom nodes (GGUF loader + helpers, optional for BF16) ==="
cd "$COMFY/custom_nodes"
[[ -d ComfyUI-GGUF ]] || git clone https://github.com/city96/ComfyUI-GGUF.git
[[ -d ComfyUI-Manager ]] || git clone https://github.com/ltdrdata/ComfyUI-Manager.git

echo "[setup] === 4. Download Qwen-Image-2.1 weights (BF16, full quality) ==="
pip install -U "huggingface_hub[cli]"
mkdir -p "$COMFY/models/diffusion_models" "$COMFY/models/text_encoders" "$COMFY/models/vae"
# Pull from the Comfy-Org packaged repo (ComfyUI-ready single files). See comfyui/models.manifest.txt.
while IFS='|' read -r repo file dest; do
  [[ "$repo" =~ ^#.*$ || -z "$repo" ]] && continue
  echo "[setup]   $repo :: $file -> $dest"
  huggingface-cli download "$repo" "$file" --local-dir "$COMFY/models/$dest"
done < "$REPO_DIR/comfyui/models.manifest.txt"

echo "[setup] === 5. Done ==="
echo "Start ComfyUI:  cd $COMFY && source .venv/bin/activate && python main.py --listen 127.0.0.1 --port 8188"
echo "Then on your laptop tunnel:  ssh -L 8188:localhost:8188 ubuntu@<IP>  and open http://localhost:8188"
echo "Or run the automated test cases:  $REPO_DIR/scripts/run-test.sh"
