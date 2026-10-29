#!/usr/bin/env bash
# Install Hunyuan3D-2 texgen (paint) extensions + deps. Logs to ~/paint_env.log
# Run AFTER hi3d_env.sh + hunyuan_env.sh (shapegen already installed).
set -uo pipefail
exec > >(tee -a "$HOME/paint_env.log") 2>&1
echo "=== Hunyuan paint-module install start $(date -u) ==="
cd "$HOME/Hi3Dv1.0" && . .venv/bin/activate
export PIP_CONSTRAINT="$PWD/docker/constraints.txt"

# paint module deps (keep pinned diffusers 0.31 / hub 0.28.1 from earlier fixes)
pip install -q realesrgan || echo "WARN realesrgan"
# texgen needs these at runtime
pip install -q "numpy<2" opencv-python-headless Pillow || true

cd "$HOME/Hunyuan3D-2"
echo "=== build custom_rasterizer ==="
cd hy3dgen/texgen/custom_rasterizer
python3 setup.py install 2>&1 | tail -4 || echo "WARN custom_rasterizer build"
cd "$HOME/Hunyuan3D-2"
echo "=== build differentiable_renderer ==="
cd hy3dgen/texgen/differentiable_renderer
python3 setup.py install 2>&1 | tail -4 || echo "WARN diff_renderer build"
cd "$HOME/Hunyuan3D-2"

echo "=== verify texgen import ==="
python -c "from hy3dgen.texgen import Hunyuan3DPaintPipeline; print('Hunyuan3DPaintPipeline import OK')" 2>&1 | tail -3
echo "PAINT_ENV_DONE $(date -u)"
