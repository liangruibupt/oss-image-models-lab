#!/usr/bin/env bash
# RUN THIS ON THE GPU INSTANCE.
# Boots ComfyUI headless, renders the scenes in tests/prompts.jsonl (one image per
# seed) into the repo's assets/ dir so they can be committed, then (optionally)
# syncs to S3. Pass scene ids to --only via $ONLY to render a subset.
#   ONLY=food_sandwich_bread ./scripts/run-test.sh     # just scene 1
set -euo pipefail

MOUNT="/mnt/weights"
COMFY="$MOUNT/ComfyUI"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_DIR/assets"          # committed to the repo
mkdir -p "$OUT"

[[ -f "$REPO_DIR/config.env" ]] && source "$REPO_DIR/config.env" || true

cd "$COMFY"
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[test] Launching ComfyUI headless on 127.0.0.1:8188 ..."
RUNLOG="$MOUNT/comfyui-run.log"
python main.py --listen 127.0.0.1 --port 8188 >"$RUNLOG" 2>&1 &
COMFY_PID=$!
trap 'kill $COMFY_PID 2>/dev/null || true' EXIT

for i in $(seq 1 90); do
  curl -sf http://127.0.0.1:8188/system_stats >/dev/null && break
  sleep 2
  [[ $i -eq 90 ]] && { echo "[test] ComfyUI failed to start — see $RUNLOG"; exit 1; }
done
echo "[test] ComfyUI up."

echo "[test] Rendering ${ONLY:+(only: $ONLY) }..."
python3 "$REPO_DIR/tests/run_prompts.py" \
  --server http://127.0.0.1:8188 \
  --prompts "$REPO_DIR/tests/prompts.jsonl" \
  --t2i-workflow "$REPO_DIR/workflows/qwen_image_2.1_t2i.json" \
  --edit-workflow "$REPO_DIR/workflows/qwen_image_2.1_edit.json" \
  --out "$OUT" \
  --only "${ONLY:-}"

echo "[test] Assets in $OUT"
if [[ -n "${S3_BUCKET:-}" ]]; then
  echo "[test] Syncing to s3://$S3_BUCKET/assets/ ..."
  aws s3 sync "$OUT" "s3://$S3_BUCKET/assets/" --only-show-errors || true
fi
echo "[test] Done. Commit assets from your laptop (git add assets && git commit && git push)."
