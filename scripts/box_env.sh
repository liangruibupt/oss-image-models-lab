#!/usr/bin/env bash
# RUN THIS ON THE GPU INSTANCE. Verified env setup — see docs/RUNBOOK.md.
# Installs python3-venv (DLAMI lacks it), torch 2.7 (NOT 2.6 — comfy-kitchen bug),
# and diffusers (which ships QwenImage21Pipeline + ZImagePipeline).
set -euxo pipefail
sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv python3-pip
cd "$HOME"
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip wheel
# torch 2.7 from default PyPI (cu126 wheel). Do NOT pin cu124 index (only has 2.6).
pip install -q "torch==2.7.*" "torchvision==0.22.*"
pip install -q -U diffusers transformers accelerate safetensors sentencepiece
python -c "import torch,diffusers; print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'diffusers',diffusers.__version__)"
echo ENV_DONE
