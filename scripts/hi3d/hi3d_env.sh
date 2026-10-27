#!/usr/bin/env bash
# Hi3D v1.0 pinned env install on the L40S box. Logs to ~/hi3d_env.log.
set -uo pipefail
exec > >(tee -a "$HOME/hi3d_env.log") 2>&1
echo "=== Hi3D env install start $(date -u) ==="

# 1) system deps + python3.10 venv (Hi3D requires Python 3.10)
sudo apt-get update -y -q
sudo apt-get install -y -q python3.10 python3.10-venv python3.10-dev git ninja-build || true
python3.10 --version || { echo "NO_PY310"; exit 2; }

# 2) clone Hi3D
cd "$HOME"
if [ ! -d Hi3Dv1.0 ]; then
  git clone --depth 1 https://github.com/hi3d-official/Hi3Dv1.0.git
fi
cd Hi3Dv1.0

# 3) venv py3.10
python3.10 -m venv .venv
. .venv/bin/activate
python -m pip install -q --upgrade pip wheel setuptools

# 4) pinned torch cu124
pip install -q torch==2.5.0+cu124 torchvision==0.20.0+cu124 --extra-index-url https://download.pytorch.org/whl/cu124
python -c "import torch;print('torch',torch.__version__,'cuda',torch.version.cuda,'avail',torch.cuda.is_available())"

# 5) build prereqs + flash-attn (no build isolation) + spconv via constraints
pip install -q packaging ninja psutil
echo "=== building flash-attn (slow) $(date -u) ==="
pip install -q --no-build-isolation flash-attn==2.7.4.post1
echo "=== installing .[inference] with constraints $(date -u) ==="
pip install -q -c docker/constraints.txt -e ".[inference]"

echo "=== verify imports ==="
python -c "import flash_attn; print('flash_attn', flash_attn.__version__)"
python -c "import spconv; print('spconv ok')"
python -c "from sparc3d import Sparc3DPipeline; print('sparc3d import OK')"
echo "HI3D_ENV_DONE $(date -u)"
