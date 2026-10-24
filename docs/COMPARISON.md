# Z-Image vs Qwen-Image 2.1 对比

两者都来自阿里，但**不是同一条产品线、也不是升级关系**，而是两种定位不同的开源生图模型：
- **Z-Image**（通义 Tongyi-MAI）：轻量、极速、**Apache 2.0 可商用**，纯文生图。
- **Qwen-Image 2.1**（Qwen 团队）：统一生成+编辑、**原生透明 PNG**、2K，Qwen Research License（商用需授权）。

> 本文档的"文字评价"只基于可验证的模型特性与本仓库实测数据，不含主观画质打分。样图见本仓库 `assets/`：Qwen 为 `<scene>_seed<n>.png`，Z-Image 为 `zimage_<scene>_seed<n>.png`，同场景同 seed 可直接并排对比。

## 规格对比

| 维度 | Z-Image | Qwen-Image 2.1 |
|---|---|---|
| 团队 | 通义 Tongyi-MAI | Qwen |
| 发布 | Turbo 2025-11 / Base 2026-01 | 2026-09-20（+Turbo 2026-10） |
| **许可证** | **Apache 2.0 ✅ 可商用** | Qwen Research ❌ 商用需授权 |
| 参数量 | 6B（S3-DiT 单流扩散 Transformer） | 7B 生成器 + 8B 文本编码器 |
| 架构 | Single-Stream DiT | Single-Stream DiT + Qwen3-VL 编码器 |
| 显存 | 16GB 消费卡可跑 | BF16 ~30GB / FP8 16GB |
| 原生透明 RGBA | ✗ 无 | ✓ 招牌能力 |
| 图像编辑 | ✗（基础 Img2Img/ControlNet 有，但非多参考编辑） | ✓ 最多 10 张参考图 |
| 最大分辨率 | 1024 级（可放大） | 原生 2K |
| 双语文字 | ✓ 中英 | ✓ 中文尤强 |
| 宣传速度 | Turbo 亚秒级 @1024²（H800，8 步） | Turbo 约数秒 |

## 本仓库实测（同一台 ap-northeast-1 g6e.xlarge / L40S 46GB，BF16）

同样 5 个场景、同样 prompt、同样 4 个 seed，两模型各出 20 张：

| 指标 | Z-Image-Turbo | Qwen-Image-2.1-Turbo |
|---|---|---|
| 平均耗时/张 | **~13.3 s** | **~6.4 s** |
| 采样步数 | 8 | 8 |
| 样图数 | 20 | 20 |

> ⚠️ **实测反差说明**：Z-Image 宣传"亚秒级"，但本次实测反而比 Qwen Turbo 慢。原因：(1) 我们跑的是竖版 1024×1408 等较大尺寸，而"亚秒级"基准是 1024² 方图 + H800 + 厂商优化内核；(2) diffusers 通用路径未启用 Z-Image 的专用加速。**结论：别照搬营销数字，按你的真实尺寸/硬件实测为准。** 在 1024² 小图 + 消费卡本地场景，Z-Image 的低显存优势才会体现。

## 怎么选

| 你的情况 | 选 |
|---|---|
| 需要**商用**、无法走授权流程 | **Z-Image**（Apache 2.0）|
| 需要**原生透明 PNG**（贴纸/UI/抠图）| **Qwen-Image 2.1** |
| 需要**图像编辑 / 多参考图融合** | **Qwen-Image 2.1** |
| 需要 **2K 高分辨率** | **Qwen-Image 2.1** |
| **消费级 16GB 显卡**本地跑、纯文生图 | **Z-Image** |
| 中文海报 / 双语文字 | 两者都强，按商用需求定 |

## 一句话
- **Z-Image = 可商用 + 轻量**，补上了 Qwen-Image 2.1 "不能免费商用" 的缺口；
- **Qwen-Image 2.1 = 透明 + 编辑 + 2K**，这三样 Z-Image 做不到。
- 对纯文生图的广告图：优先 Z-Image（可商用）；需要透明/编辑/2K 时用 Qwen。

## 复现
```bash
# Z-Image（diffusers 0.41+ 自带 ZImagePipeline，Tongyi-MAI/Z-Image-Turbo）
# Qwen（QwenImage21Pipeline，Qwen/Qwen-Image-2.1-Turbo）
# 两者均 BF16 on L40S，8 步，见本仓库生成脚本与 tests/prompts.jsonl
```
