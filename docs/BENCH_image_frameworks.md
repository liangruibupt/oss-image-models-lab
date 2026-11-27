# 推理框架实测对比：Diffusers vs SGLang Diffusion vs vLLM-Omni（Qwen-Image-2.1-Turbo / Z-Image-Turbo）

> 本文所有数字都来自 2026-11-27 在**同一台** ap-northeast-1 g6e.xlarge（1× L40S 46GB，30GB 主机内存）上的实测，原始结果见 [`assets/bench/results.json`](../assets/bench/results.json)。复现脚本在 [`scripts/bench/`](../scripts/bench/README.md)。

## 1. 测试设置

| 项 | 值 |
|---|---|
| 实例 | ap-northeast-1c / g6e.xlarge（i-060747915b74bc9e8），DLAMI *OSS Nvidia Driver GPU PyTorch 2.7 Ubuntu 22.04*（ami-0152728adca68ed36），250GB gp3 根盘 |
| GPU / 驱动 | NVIDIA L40S 46GB，驱动 580.126.09（CUDA 13.0），内核 6.8.0-1052-aws |
| 模型 | `Qwen/Qwen-Image-2.1-Turbo`：8 步，`true_cfg_scale=1.0`，`negative_prompt=" "`；`Tongyi-MAI/Z-Image-Turbo`：8 步，`guidance_scale=1.0`（与 [`scripts/gen.py`](../scripts/gen.py) 及已有对比完全相同） |
| 精度 / 分辨率 | BF16，1024×1408（仓库标准竖版） |
| Prompt | [`tests/prompts.jsonl`](../tests/prompts.jsonl) 中 `food_sandwich_bread` / `cosmetic_lancome_essence` / `portrait_bird` |
| 冷启动首图 | 服务 ready 后的第 1 次请求：`food_sandwich_bread` seed 11 |
| 热态 | 3 prompt × seed (11, 22) = 6 张，顺序执行（并发 1），取中位数 |
| 并发 4 | 8 个请求（seed 33/44/55），同时 4 个在途，吞吐 = 8 / 总墙钟时间（仅服务框架） |
| 加载时间 | 进程启动 → 可出图（Diffusers：`from_pretrained().to("cuda")` 完成，含 import；服务：`GET /v1/models` 返回 200）。权重已预下载，每次运行前 `drop_caches`，权重都从 EBS 读取 |
| 峰值显存 | `nvidia-smi` 每 250ms 采样，整段运行取最大值 |

框架都走各自默认路径，只做了下面两处必要调整（都记录在 [`scripts/bench/`](../scripts/bench/README.md) 里）：
- **SGLang**：加 `--component-residency=all=resident`。不加时，它的自动显存策略在 44GiB 空闲显存下会把 Qwen 的 text_encoder 和 VAE 设为 *layerwise offload*，16GB 的文本编码器常驻主机内存，30GB 内存的 g6e.xlarge 随即开始 swap（实测 4 分钟只加载完 3/5 个组件，已中止）。全部常驻 GPU 与 Diffusers 的 `.to("cuda")` 是同口径。
- **vLLM-Omni**：启动服务前去掉 `LD_LIBRARY_PATH`。DLAMI 的 `/etc/profile.d/dlami.sh` 把 `/usr/local/cuda`（12.8）放进 `LD_LIBRARY_PATH`，系统 cuDNN 9.10 盖住了 cu130 wheel 自带的 cuDNN 9.20，第一次启动直接报 `RuntimeError: cuDNN version incompatibility: PyTorch was compiled against (9, 20, 0) but found runtime version (9, 10, 2)`。另外按安装提示运行了 `vllm download-kernels`（装 flashinfer-cubin / jit-cache）。

## 2. 版本

| 框架 | 版本 | torch / CUDA | 其它 | Python |
|---|---|---|---|---|
| Diffusers（基线） | diffusers 0.41.0 | torch 2.7.1+cu126 | transformers 5.20.2, accelerate 1.15.0 | 3.10.12（系统 venv，[`scripts/box_env.sh`](../scripts/box_env.sh)） |
| SGLang Diffusion | sglang 0.5.23（`sglang[diffusion]`，sglang-kernel 0.4.10） | torch 2.14.1+cu130 | diffusers 0.37.0, transformers 5.19.0, flashinfer-python 0.7.2 | 3.12（uv venv） |
| vLLM-Omni | vllm 0.32.0 + vllm-omni 0.32.0 | torch 2.13.0+cu130 | diffusers 0.40.0, transformers 5.19.0, flashinfer 0.7.0.post1 | 3.12（uv venv） |

每个框架一个独立 venv。两个模型在三个框架上都**加载成功并正常出图**，没有不支持的组合。

## 3. 结果

| 模型 | 框架 | 加载 (s) | 冷启动首图 (s) | 热态 s/img（中位数，n=6） | 吞吐 c=1 (img/s) | 吞吐 c=4 (img/s) | 峰值显存 (GiB) |
|---|---|---|---|---|---|---|---|
| Qwen-Image-2.1-Turbo | Diffusers | **279.1** | 11.93 | 5.34 | 0.169 | n/a（离线管线） | 42.3 |
| Qwen-Image-2.1-Turbo | SGLang | 377.5 | **5.14** | **4.20** | **0.238** | **0.238** | 42.5 |
| Qwen-Image-2.1-Turbo | vLLM-Omni | 308.4 | 5.86 | 5.88 | 0.170 | 0.169 | **39.8** |
| Z-Image-Turbo | Diffusers | **263.6** | 13.19 | 12.53 | 0.077 | n/a（离线管线） | 27.9 |
| Z-Image-Turbo | SGLang | 342.7 | **7.59** | **7.17** | **0.139** | **0.134** | **23.0** |
| Z-Image-Turbo | vLLM-Omni | 300.4 | 18.01 | 7.83 | 0.128 | 0.126 | 26.1 |

热态 6 张的单张耗时非常稳定（波动 ≤ 0.3s）：

| 模型 / 框架 | 6 张热态耗时 (s) | c=4 下 8 个请求各自延迟 (s) |
|---|---|---|
| Qwen / Diffusers | 5.31, 5.34, 5.34, 5.34, 5.38, 5.40 | — |
| Qwen / SGLang | 4.10, 4.12, 4.15, 4.24, 4.27, 4.25 | 8.4, 4.2, 16.8, 12.6, 16.7, 16.7, 16.7, 16.8 |
| Qwen / vLLM-Omni | 5.83, 5.86, 5.95, 5.83, 5.92, 5.89 | 11.8, 6.0, 17.6, 23.5, 23.4, 23.5, 23.7, 23.8 |
| Z / Diffusers | 12.49, 12.57, 12.38, 12.40, 12.65, 12.68 | — |
| Z / SGLang | 7.12, 7.19, 7.14, 7.14, 7.26, 7.23 | 7.3, 29.6, 14.7, 22.1, 29.8, 30.0, 30.2, 30.2 |
| Z / vLLM-Omni | 7.72, 7.87, 7.75, 7.80, 7.91, 7.93 | 8.1, 23.9, 16.0, 31.8, 31.6, 31.6, 31.8, 31.8 |

## 4. 出图对比（同 prompt、同 seed 11）

每列一个框架，表头是该框架热态中位耗时。单张缩略图在 `assets/bench/<model>/<framework>/<scene>_seed<n>.jpg`（512px JPEG，seed 11 和 22 都有）。

### Qwen-Image-2.1-Turbo

![Qwen-Image-2.1-Turbo：Diffusers / SGLang / vLLM-Omni 同 seed 并排](../assets/bench/qwen-turbo/sidebyside.jpg)

### Z-Image-Turbo

![Z-Image-Turbo：Diffusers / SGLang / vLLM-Omni 同 seed 并排](../assets/bench/z-turbo/sidebyside.jpg)

同 seed 下三个框架的构图、主体和文字几乎一致，只有细节差异（例如 Z-Image 化妆品图的标题字重、瓶身小字）。这说明三者跑的是同一模型、同一采样参数，速度差异来自内核和运行时，而不是少算了步数。

## 5. 结论

1. **单张热态速度：SGLang 最快。** Qwen 4.20 s/img，比 Diffusers 的 5.34 快 21%；Z-Image 7.17 s/img，比 Diffusers 的 12.53 快 43%。vLLM-Omni 在 Z-Image 上接近 SGLang（7.83，比 Diffusers 快 38%），在 Qwen 上反而比 Diffusers 慢 10%（5.88 vs 5.34）。
2. **Z-Image 在 Diffusers 上慢的原因找到了。** 之前 [COMPARISON](COMPARISON_zimage-vs-qwen-image-2.1.md) 记录的 "Z-Image 比 Qwen Turbo 还慢" 主要是 Diffusers 通用路径的问题：换到 SGLang/vLLM-Omni 后 Z-Image 从 12.5s 降到 7.2–7.8s。但即便如此，1024×1408 下 Z-Image-Turbo 仍比 Qwen-Image-2.1-Turbo 慢（7.17 vs 4.20，都在 SGLang 上）。
3. **并发 4 没有提高吞吐。** 两个服务框架在默认配置下都把请求排队串行执行：c=4 吞吐与 c=1 相同（Qwen/SGLang 都是 0.238 img/s），排队请求的延迟涨到单张的 4 倍左右。单张 L40S 上，这个分辨率的 DiT 已经把 GPU 跑满，想提吞吐只能加卡或降精度，不能靠并发。
4. **冷启动：服务框架首图更快，但加载更慢。** 加载时间主要受 EBS gp3（约 110 MB/s）读 30GB 权重限制，三者都在 4.5–6.5 分钟；SGLang 最慢（多出约 100s 的初始化/预热）。vLLM-Omni 对 Z-Image 使用懒加载的区域 `torch.compile`，所以首图 18s，第二张起才到 7.8s。Diffusers 没有预热步骤，首图（12–13s）比热态多出 0.7–6.6s 的首次初始化开销。实例上有 232GB 实例存储 NVMe（`/opt/dlami/nvme`，本次未用），把 HF 缓存放那里应能明显缩短加载时间。
5. **显存：** 全部常驻 GPU 时 Qwen 在三个框架上都要 40–42.5GiB，46GB 的 L40S 很紧；vLLM-Omni 最省（39.8GiB）。Z-Image 23–28GiB，SGLang 最省。
6. **选型建议：** 要对外提供 HTTP 接口（OpenAI `/v1/images/generations`）优先用 **SGLang Diffusion**（两个模型都最快）。vLLM-Omni 适合已经用 vLLM 栈的团队，Z-Image 上表现接近 SGLang。一次性离线批量出图，Diffusers（仓库现有 `gen.py`）依旧最省事、加载最快，但 Z-Image 慢很多。

## 6. 坑（本次实测踩到的）

- **SGLang 自动显存策略会在 g6e.xlarge 上触发 swap**：默认对 Qwen-Image-2.1 的 text_encoder/VAE 选 layerwise offload，16GB 留在 30GB 主机内存里。→ `--component-residency=all=resident`。
- **vLLM-Omni 与 DLAMI 的 `LD_LIBRARY_PATH` 冲突**（cuDNN 9.10 vs 9.20）。→ 启动前 `unset LD_LIBRARY_PATH`（脚本已处理）。
- **vLLM-Omni 0.32 需要 CUDA 13 驱动**（`--torch-backend=cu130`）。本 AMI 驱动 580 满足；更老的驱动需换 AMI。
- **SGLang 对 Z-Image 的 `b64_json` 返回 JPEG**（Qwen 返回 PNG），本次未调整。需要无损 PNG 时要另查 SGLang 的输出格式参数（未实测）。
- **`huggingface_hub` 别升到 2.x**：diffusers 0.41 需要 `<2.0`；`pip install -U huggingface_hub` 会破坏 Diffusers venv。

## 7. 本次运行成本

| 项 | 值 |
|---|---|
| 实例 | i-060747915b74bc9e8，g6e.xlarge，ap-northeast-1c |
| 启动 → 终止 | 2026-11-27 02:51:01 UTC → 04:14:03 UTC（发起 terminate） |
| 实例时长 | **约 1.38 实例小时**（上限 4 小时） |
| 费用 | 按仓库费率 ~$1.86/hr 约 **$2.6**（东京区按需价略高，以账单为准）；EBS 随实例删除 |
| 其中 | 装 3 个 venv + 下载约 60GB 权重 ~18 分钟；6 组正式测量 ~55 分钟；其余为两次中止重跑（SGLang offload swap、vLLM cuDNN） |
