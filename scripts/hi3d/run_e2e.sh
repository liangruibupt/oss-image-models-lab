#!/usr/bin/env bash
# Run Hi3D end-to-end at a given resolution, sampling VRAM. Usage: run_e2e.sh RES
set -uo pipefail
RES="${1:-512}"
cd "$HOME/Hi3Dv1.0"
. .venv/bin/activate
LOG="$HOME/e2e_${RES}.log"
exec > >(tee -a "$LOG") 2>&1
echo "=== Hi3D e2e res=$RES start $(date -u) ==="

# background VRAM sampler
( while true; do
    echo "VRAM $(date +%H:%M:%S) $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader)";
    sleep 10;
  done ) &
SAMPLER=$!

START=$(date +%s)
python demo/image_to_mesh.py \
  --model hi3d-official/Hi3Dv1.0 \
  --image "$HOME/hi3d_test.png" \
  --output "$HOME/refined_${RES}.glb" \
  --coarse-output "$HOME/coarse.glb" \
  --resolution "$RES" \
  --seed 0 \
  --remove-background \
  --sequential-cpu-offload
RC=$?
END=$(date +%s)
kill $SAMPLER 2>/dev/null
echo "=== e2e res=$RES rc=$RC elapsed=$((END-START))s $(date -u) ==="
if [ $RC -eq 0 ]; then
  ls -la "$HOME/refined_${RES}.glb" "$HOME/coarse.glb"
  python -c "import trimesh; m=trimesh.load('$HOME/refined_${RES}.glb',force='mesh'); print('refined verts',len(m.vertices),'faces',len(m.faces))"
  echo "E2E_${RES}_DONE"
else
  echo "E2E_${RES}_FAILED rc=$RC"
fi
