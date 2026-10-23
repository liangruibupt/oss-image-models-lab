#!/usr/bin/env bash
# RUN THIS ON THE GPU INSTANCE.
# Boots ComfyUI headless, submits every prompt in tests/prompts.jsonl through the
# API-format workflow, waits for images, then (optionally) syncs outputs to S3.
set -euo pipefail

MOUNT="/mnt/weights"
COMFY="$MOUNT/ComfyUI"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$MOUNT/outputs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

# Load S3 bucket if config.env was copied over (optional on the box).
[[ -f "$REPO_DIR/config.env" ]] && source "$REPO_DIR/config.env" || true

cd "$COMFY"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[test] Launching ComfyUI headless on 127.0.0.1:8188 ..."
python main.py --listen 127.0.0.1 --port 8188 --output-directory "$OUT" >"$OUT/comfyui.log" 2>&1 &
COMFY_PID=$!
trap 'kill $COMFY_PID 2>/dev/null || true' EXIT

# wait until the API is up
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8188/system_stats >/dev/null && break
  sleep 2
  [[ $i -eq 60 ]] && { echo "[test] ComfyUI failed to start — see $OUT/comfyui.log"; exit 1; }
done
echo "[test] ComfyUI up."

echo "[test] Driving test cases through the API ..."
python3 "$REPO_DIR/tests/run_prompts.py" \
  --server http://127.0.0.1:8188 \
  --prompts "$REPO_DIR/tests/prompts.jsonl" \
  --t2i-workflow "$REPO_DIR/workflows/qwen_image_2.1_t2i.json" \
  --edit-workflow "$REPO_DIR/workflows/qwen_image_2.1_edit.json" \
  --out "$OUT"

echo "[test] Outputs in $OUT"
if [[ -n "${S3_BUCKET:-}" ]]; then
  echo "[test] Syncing to s3://$S3_BUCKET/runs/$(basename "$OUT")/ ..."
  aws s3 sync "$OUT" "s3://$S3_BUCKET/runs/$(basename "$OUT")/" --only-show-errors
  echo "[test] Done. s3://$S3_BUCKET/runs/$(basename "$OUT")/"
else
  echo "[test] S3_BUCKET unset — left outputs on the box only."
fi
