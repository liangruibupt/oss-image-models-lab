# 🎬 Sand.ai MAGI-2：开源音视频生成模型调研

> 状态：**调研笔记，尚未在本仓库实测**（2026-11-25 整理）。信息来自官方博客、GitHub 和 Hugging Face，下方列出来源。

[Sand.ai](https://sand.ai) 是 Swin Transformer 原班成员创立的视频生成公司，此前开源过 MAGI-1（2025-05，自回归视频生成）。目前有两个 MAGI-2 版本：

| | **MAGI-2 Preview** | **MAGI-2 旗舰版** |
|---|---|---|
| 发布 | 2026-08-05 | 2026-11-24 |
| 是否开源 | ✅ **已开源**，权重 + 推理代码，Apache 2.0 | ❌ **暂未开源**，官方称"即将开源并发布技术报告" |
| 参数 | 114B 总参数，每 token 激活约 6B | 480B 总参数，每 token 激活约 28B |
| 预训练数据 | 约 1.3T token（按旗舰版"扩大约 3 倍到 4T"推算） | 4T token |
| 架构 | Multi-Head Latent MoE，单流 Transformer，文本/视频/音频 token 在同一序列 | 同左，规模扩大 4 倍以上 |
| 输出 | 文生视频 / 图生视频，**同步生成音频**，固定 10 秒，1080p | 最长 30 秒，1080p 25fps，原生音视频（对白对口型、音效、环境声、音乐） |
| 参考输入 | 首帧图片 | 多参考输入，最多 20 个（10 图 + 5 视频 + 5 音频） |
| 其它能力 | — | 时间轴分镜控制、视频编辑，6 种画幅 |
| 评测 | AA Video Arena v2.1 四项平均 Elo 998.5 | 同榜 1150.3（+151.8） |
| 获取方式 | [GitHub](https://github.com/SandAI-org/MAGI-2-preview) · [HF 权重](https://huggingface.co/sand-ai/MAGI-2-preview) · Docker `sandai/magi-2-preview` | 目前仅 API，例如 [Higgsfield](https://higgsfield.ai/announcing-magi-2) |

## MAGI-2 Preview 部署要点（已开源版本）

### 硬件与环境
- **官方要求 8 张 NVIDIA Hopper GPU**，Python 3.12，较新的 CUDA toolkit，`ffmpeg` 在 PATH 中（用于混入音轨，缺失时输出无声视频）。
- 1080p 时 preview 和 refiner 两个 transformer 无法和对方的激活同时放进一张 80GB 卡，所以默认按阶段换入换出（`MAGI2_*_OFFLOAD_MODE=roundtrip`）。
- 依赖 Sand.ai 自家的 [MagiAttention](https://github.com/SandAI-org/MagiAttention) 和 [MagiCompiler](https://github.com/SandAI-org/MagiCompiler)，版本固定在 Dockerfile 的 build args 里。建议直接用官方镜像，镜像内 `/etc/magi2-build-info` 记录构建来源。

### 权重（约 307 GB）
| 目录 | 大小 | 内容 |
|---|---|---|
| `preview/` | 228 GB | preview 阶段 transformer（56 个 shard） |
| `text_encoder/` | 56 GB | 文本编码器 Qwen3.5-27B |
| `refiner/` | 14 GB | refiner 阶段 transformer |
| `stable-audio-open-1.0/` | 5 GB | 音频 VAE |
| `vae/` | 3 GB | 视频 VAE（来自 Wan2.2-TI2V-5B） |
| `turbo_vae/` | 2 GB | 蒸馏版快速 VAE 解码器（默认使用） |

```bash
hf download sand-ai/MAGI-2-preview --local-dir ckpt
export MAGI2_CKPT_ROOT=/data/magi2-weights   # 权重放在别处时
```

### 推理流程
- 两阶段：`magi2_preview` 在 512x896 去噪，`magi2_refiner` 放大到 1088x1920（VAE stride 要求 16 的倍数，所以是 1088 而不是 1080，可用 `--output-width/--output-height` 缩放到精确尺寸）。
- **尚未步数蒸馏**：base 版要跑 100 步 preview + 5 步 refiner，耗时主要在这里。少步数的蒸馏版"即将发布"。
- 训练用的 caption 长且结构化，短 prompt 效果打折。官方提供 prompt enhancement（PE），调用 OpenAI 兼容的 LLM 接口把 prompt 改写成结构化 JSON caption。

```bash
torchrun --nproc_per_node=8 inference/pipeline/entry.py \
    --prompt "a red fox in snow" --output output/
```

## 对本仓库的意义

- **跑不进现有机型**：本仓库默认用单卡 g6e（L40S 48GB）。MAGI-2 Preview 需要 8 张 Hopper，在 AWS 上对应 **p5.48xlarge（8×H100 80GB）或 p5e/p5en.48xlarge（8×H200）**，按需价格比 g6e 高一个数量级，且容量紧张，通常要用 Capacity Blocks。
- **g7e.48xlarge（8×Blackwell）官方未声明支持**，MagiAttention 等自定义 kernel 是否支持 Blackwell 需要实测。
- **建议**：等蒸馏版（步数少很多）或 480B 旗舰版开源后再评估实测；在那之前，如果只想看效果，用 API 平台试用成本更低。
- 许可证 Apache 2.0，**可商用**，这一点比很多开源视频模型友好。

## 来源
- Sand.ai 博客：[MAGI-2: A 480B Frontier Video Generation Model](https://sand.ai/blog/magi-2/)
- GitHub：[SandAI-org/MAGI-2-preview](https://github.com/SandAI-org/MAGI-2-preview)（README 中的硬件、权重、推理说明）
- GitHub 组织：[SandAI-org](https://github.com/SandAI-org)
- Higgsfield：[Announcing MAGI-2](https://higgsfield.ai/announcing-magi-2)
- 36Kr：[MAGI-2 Preview 发布报道](https://eu.36kr.com/en/p/3967032902129541)

（以上内容为转述整理，非原文引用。）
