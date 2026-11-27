#!/usr/bin/env bash
# RUN ON THE GPU INSTANCE after setup_box.sh. Runs the full model x framework matrix sequentially
# (one framework owns the GPU at a time) and writes ~/bench/results/<model>/<framework>/result.json.
# Usage: nohup bash run_matrix.sh > ~/bench/logs/matrix.log 2>&1 &
#        MODELS="z-turbo" FRAMEWORKS="sglang" bash run_matrix.sh     # subset / rerun
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
MODELS="${MODELS:-qwen-turbo z-turbo}"
FRAMEWORKS="${FRAMEWORKS:-diffusers sglang vllm-omni}"
for m in $MODELS; do
  for f in $FRAMEWORKS; do
    echo "=== $m / $f  $(date -u +%T) ==="
    sync; echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null   # every load reads weights from EBS, not page cache
    if [ "$f" = diffusers ]; then
      timeout 2400 "$HOME/.venv/bin/python" "$D/bench_diffusers.py" --model "$m"
    else
      # SGLang's auto memory policy picks layerwise CPU offload for text_encoder/vae on a 44 GiB card, which
      # pushes 16 GB into the 30 GB host RAM and swaps; pin everything on-GPU like Diffusers' .to("cuda").
      if [ "$f" = sglang ]; then X="${SGLANG_ARGS---component-residency=all=resident}"; else X="${VLLM_ARGS-}"; fi
      timeout 3000 python3 "$D/bench_server.py" --framework "$f" --model "$m" ${X:+"--extra-args=$X"}
    fi
    sleep 5
  done
done
echo MATRIX_DONE "$(date -u +%T)"
