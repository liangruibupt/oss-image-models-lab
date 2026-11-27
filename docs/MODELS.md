# 模型清单与显存对照

## 已集成

### Qwen-Image-2.1 ✅（首发）
- **类型**：统一文生图 + 图像编辑，7B 生成器 + Qwen3-VL ~8B 文本编码器。
- **招牌能力**：原生透明 PNG（RGBA）、最多 10 张参考图编辑、原生 2K。
- **发布**：2026-09-20（+ Turbo 变体 2026-10-09，8 步快采样）。
- **许可证**：Qwen Research License —— **默认禁止商业用途**，商用需另签。
- **来源**：`Qwen/Qwen-Image-2.1`（Diffusers 全量）/ `Comfy-Org/Qwen-Image-2.1`（ComfyUI 单文件）。

#### 精度 / 显存对照
| 路线 | 权重 | 显存 | 说明 |
|---|---|---|---|
| **BF16 全精度** | ~30 GB | **≥32 GB**（本仓库用 L40S 48GB） | 最高质量，走 Diffusers 或自行转权重 |
| **INT8 ConvRot**（默认） | ~24GB 级 | 24–48 GB | Comfy-Org 打包版，质量近 BF16，本仓库 manifest 默认 |
| **FP8** | ~7 GB | 16 GB | 1024 图约 1–2 分钟，甜点区 |
| **GGUF Q4–Q8** | 4–7 GB | 6–8 GB | 低显存路径 |
| **GGUF + CPU offload** | — | 低至 4 GB | 很慢，仅尝鲜 |

> ⚠️ "7B" 是生成器；完整下载约 **32GB**（文本编码器比图像模型还大）。GGUF 文件大小 ≠ 总显存需求（还要算文本编码器、VAE、中间张量、CUDA runtime）。

### Z-Image ✅（已实测对比）
- **类型**：纯文生图（6B，S3-DiT 单流扩散 Transformer），团队：通义 Tongyi-MAI。
- **许可证**：**Apache 2.0 —— 完全可商用**（这是相对 Qwen-Image 2.1 的最大优势）。
- **显存**：16GB 消费卡即可跑；BF16 本地实测于 L40S。
- **强项**：写实 + 中英双语文字 + 低显存/低成本；**不支持**原生透明、多参考图编辑、2K。
- **来源**：`Tongyi-MAI/Z-Image-Turbo`（diffusers 0.41+ 自带 `ZImagePipeline`）。
- **与 Qwen-Image 2.1 的完整对比见 [`COMPARISON_zimage-vs-qwen-image-2.1.md`](COMPARISON_zimage-vs-qwen-image-2.1.md)**（含同场景同 seed 的并排样图与本仓库实测耗时）。

## 待测 / 可扩展（欢迎按同结构添加）

| 模型 | 类型 | 许可证 | 备注 |
|---|---|---|---|
| FLUX.1 [dev] / [schnell] | 文生图 | 非商用 / Apache | 社区生态成熟，ComfyUI 原生支持 |
| Stable Diffusion 3.5 Large | 文生图 | Stability 社区许可 | 8B，质量高 |
| Qwen-Image（初代） | 文生图 | **Apache-2.0** | 可商用，若需商用优先考虑 |
| Qwen-Image-2.1-Turbo | 文生图+编辑 | Qwen Research | 8 步加速，已含在默认 manifest |

## 视频模型（调研，未实测）

| 模型 | 类型 | 许可证 | 备注 |
|---|---|---|---|
| Sand.ai MAGI-2 Preview | 文/图生视频 + 同步音频，10 秒 1080p | **Apache-2.0** | 114B MoE（激活 6B），权重约 307GB，需 8×Hopper（AWS p5/p5e）。调研笔记见 [`MAGI2_sandai.md`](MAGI2_sandai.md) |
| Sand.ai MAGI-2（旗舰） | 音视频生成，30 秒 1080p，多参考 + 编辑 | 未开源 | 480B MoE（激活 28B），2026-11-24 发布，官方称即将开源 |

## 推理框架支持
各模型在 SGLang、vLLM、TrnRT、vLLM-Omni、DeepInfer（及 Diffusers / ComfyUI 基线）上的支持矩阵与起服务命令见 [`INFERENCE_FRAMEWORKS.md`](INFERENCE_FRAMEWORKS.md)。

## 如何新增一个模型
1. 在 `comfyui/models.manifest.txt` 加上该模型的 HF 仓库 + 文件 + 目标目录。
2. 在 `workflows/` 加一个该模型的 API 格式工作流 JSON。
3. 在 `tests/prompts.jsonl` 加用例，`task` 指向你的工作流键（或扩展 `run_prompts.py` 的 workflow 映射）。
4. 跑 `run-test.sh`，对比 `report.json` 的耗时与产出质量。

## 商用注意
需要**商用**时，优先选许可证友好的模型（如初代 Qwen-Image Apache-2.0，或 FLUX schnell Apache-2.0）；用 Qwen-Image-2.1 商用必须先向 Qwen 申请商业授权。
