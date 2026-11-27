# scripts/bench — 推理框架对比测试（Diffusers / SGLang Diffusion / vLLM-Omni）

结果与结论见 [`docs/BENCH_image_frameworks.md`](../../docs/BENCH_image_frameworks.md)。

| 文件 | 在哪跑 | 作用 |
|---|---|---|
| [`launch_bench.py`](launch_bench.py) | 本机 | 包装 `scripts/launch.py` / `teardown.py`：SSH key 与 `launch.json` 放稳定路径 `~/.ssh/oss-bench/`，独立 key pair 名 `oss-bench-key` |
| [`setup_box.sh`](setup_box.sh) | GPU 实例 | 32GB swap；三个 venv（`~/.venv` 用仓库 `box_env.sh`，`~/venv-sglang`，`~/venv-vllm`）；预下载两个模型权重 |
| [`benchlib.py`](benchlib.py) | GPU 实例 | 固定测试矩阵（3 prompt、seed、模型参数）、`nvidia-smi` 显存采样（纯标准库） |
| [`bench_diffusers.py`](bench_diffusers.py) | GPU 实例 | 基线，直接复用 `scripts/gen.py` 的 `load_pipe()` / `render()` |
| [`bench_server.py`](bench_server.py) | GPU 实例 | 自己拉起 `sglang serve` / `vllm serve --omni`，测加载、冷启动、热态、并发 4，走 OpenAI `/v1/images/generations` |
| [`run_matrix.sh`](run_matrix.sh) | GPU 实例 | 顺序跑完整矩阵（每次一个框架独占 GPU，跑前 `drop_caches`） |
| [`collect.py`](collect.py) | 本机 | 原图 → 512px JPEG、并排对比图、`results.json`、markdown 表 |

## 用法

```bash
# 本机
python scripts/bench/launch_bench.py launch                 # 打印 IP；key 在 ~/.ssh/oss-bench/key
K=~/.ssh/oss-bench/key; H=ubuntu@<ip>
scp -i $K scripts/box_env.sh scripts/gen.py scripts/bench/setup_box.sh tests/prompts.jsonl $H:~/
ssh -i $K $H 'mkdir -p ~/bench/scripts ~/bench/logs'
scp -i $K scripts/bench/{benchlib.py,bench_diffusers.py,bench_server.py,run_matrix.sh} $H:~/bench/scripts/

# 实例上：后台启动，单独轮询日志（约 18 分钟，看 ~/bench/logs/*.ok）
ssh -i $K $H 'setsid nohup bash ~/setup_box.sh > ~/bench/logs/setup.log 2>&1 < /dev/null & disown'
ssh -i $K $H 'setsid nohup bash ~/bench/scripts/run_matrix.sh > ~/bench/logs/matrix.log 2>&1 < /dev/null & disown'
#   子集重跑：MODELS=z-turbo FRAMEWORKS=sglang bash ~/bench/scripts/run_matrix.sh
#   改 SGLang/vLLM 参数：SGLANG_ARGS="..." / VLLM_ARGS="..."（SGLang 默认 --component-residency=all=resident）

# 拉回 + 生成资产，然后一定要 terminate
ssh -i $K $H 'tar czf ~/bench_raw.tgz bench/results'; scp -i $K $H:~/bench_raw.tgz <stable-dir>/
python scripts/bench/collect.py --raw <stable-dir>/bench/results --assets assets/bench   # 需要 Pillow
python scripts/bench/launch_bench.py teardown
```

注意：
- 同一时刻只能有一个矩阵在跑，否则加载和显存互相干扰（本次曾因此重跑 Z-Image/Diffusers）。
- 杀服务时按 PID / 进程组杀，不要用会匹配到自己 shell 的 `pgrep -f` 模式。
- 一次完整矩阵（含安装和下载）约 1.2–1.5 实例小时。
