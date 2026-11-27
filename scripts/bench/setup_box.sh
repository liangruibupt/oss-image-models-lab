#!/usr/bin/env bash
# RUN ON THE GPU INSTANCE (g6e.xlarge, DLAMI OSS Nvidia driver, Ubuntu 22.04).
# One venv per framework + pre-downloaded weights, so "load time" never includes download.
#   ~/.venv          Diffusers baseline   (repo-verified scripts/box_env.sh: py3.10, torch 2.7, diffusers)
#   ~/venv-sglang    SGLang Diffusion     (uv, py3.12, sglang[diffusion])
#   ~/venv-vllm      vLLM-Omni            (uv, py3.12, vllm==VLLM_VER --torch-backend=cu130, vllm-omni==VLLM_VER)
# Each step logs to ~/bench/logs/setup_<step>.log and touches ~/bench/logs/<step>.ok on success.
# Usage: nohup bash setup_box.sh > ~/bench/logs/setup.log 2>&1 &
set -uo pipefail
VLLM_VER="${VLLM_VER:-0.32.0}"
L="$HOME/bench/logs"; mkdir -p "$L"
export PATH="$HOME/.local/bin:$PATH"

# 32 GB swap: g6e.xlarge has 30 GB host RAM and 0 swap; Qwen-Image-2.1 BF16 shards burst past that on load.
if ! swapon --show | grep -q swapfile; then
  sudo fallocate -l 32G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
fi

step() {  # step <name> <cmd...>
  local n="$1"; shift
  ( "$@" ) > "$L/setup_$n.log" 2>&1 && touch "$L/$n.ok" || touch "$L/$n.fail"
}

diffusers_env() { bash "$HOME/box_env.sh" && "$HOME/.venv/bin/pip" install -q "huggingface_hub>=1.32,<2.0" pillow; }  # diffusers 0.41 needs hub<2.0 (ships the `hf` CLI)

uv_bootstrap() { command -v uv || pip3 install --user --break-system-packages uv || pip3 install --user uv; uv --version; }

sglang_env() {
  cd "$HOME" && uv venv --python 3.12 --seed venv-sglang && \
  VIRTUAL_ENV="$HOME/venv-sglang" uv pip install "sglang[diffusion]" --prerelease=allow && \
  "$HOME/venv-sglang/bin/python" -c "import sglang,torch;print('sglang',sglang.__version__,'torch',torch.__version__,torch.version.cuda)"
}

vllm_env() {
  cd "$HOME" && uv venv --python 3.12 --seed venv-vllm && \
  VIRTUAL_ENV="$HOME/venv-vllm" uv pip install "vllm==$VLLM_VER" --torch-backend=cu130 && \
  VIRTUAL_ENV="$HOME/venv-vllm" uv pip install "vllm-omni==$VLLM_VER" && \
  "$HOME/venv-vllm/bin/python" -c "import vllm,vllm_omni,torch;print('vllm',vllm.__version__,'vllm_omni',getattr(vllm_omni,'__version__','?'),'torch',torch.__version__,torch.version.cuda)"
}

weights() {
  "$HOME/.venv/bin/hf" download Qwen/Qwen-Image-2.1-Turbo > /dev/null && \
  "$HOME/.venv/bin/hf" download Tongyi-MAI/Z-Image-Turbo > /dev/null && du -sh "$HOME/.cache/huggingface/hub"
}

step diffusers diffusers_env          # apt python3-venv/pip happens here; must precede uv + the others
step uv uv_bootstrap
step sglang sglang_env &
step vllm vllm_env &
step weights weights &
wait
ls "$L"/*.ok "$L"/*.fail 2>/dev/null
echo SETUP_DONE
