#!/usr/bin/env bash
# Install Hunyuan3D-2 (hy3dgen) coarse stage for Hi3D end-to-end. Logs to ~/hunyuan_env.log
set -uo pipefail
exec > >(tee -a "$HOME/hunyuan_env.log") 2>&1
echo "=== Hunyuan coarse-stage install start $(date -u) ==="
cd "$HOME/Hi3Dv1.0"
. .venv/bin/activate
export PIP_CONSTRAINT="$PWD/docker/constraints.txt"

# extra shape-gen deps under pinned constraints (keep numpy 1.x)
pip install -q einops diffusers opencv-python-headless pymeshlab scikit-image tqdm pyyaml || echo "WARN extra deps"

# clone + install hy3dgen
cd "$HOME"
if [ ! -d Hunyuan3D-2 ]; then
  git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git
fi
cd Hunyuan3D-2
pip install -q -e . 2>&1 | tail -5 || echo "WARN hy3dgen install"

echo "=== verify hy3dgen import ==="
python -c "import hy3dgen; print('hy3dgen import OK')" 2>&1 | tail -3
echo "HUNYUAN_ENV_DONE $(date -u)"
