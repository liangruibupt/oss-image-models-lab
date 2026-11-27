# OSS Image Models Lab

> 🤖 **AI task worker / agent：动手前先读 [`AGENTS.md`](AGENTS.md) 和 [`docs/DEPLOY_MODEL_RUNBOOK.md`](docs/DEPLOY_MODEL_RUNBOOK.md)**，里面是已验证的区域/AMI/模型 id/生成参数和踩坑清单。用 `scripts/launch.py` → `scripts/box_env.sh` → `scripts/gen.py` → `scripts/teardown.py` 这套验证过的流程，**不要重新猜测或从零试错**。

一个用于**测试开源生图模型**的实验仓库，以 AWS GPU 实例按需启停的方式运行，面向"**要高质量、但不需要 7×24**"的使用场景。

首发支持 **Qwen-Image-2.1**（7B 统一文生图 + 图像编辑，原生透明 PNG）与 **Z-Image**（6B，Apache 2.0 可商用），并提供两者的**横向对比**（见下）。架构可扩展到其它开源模型（FLUX、SD3.5、Qwen-Image 系列等）。

此外还评测了 **3D 几何模型 Hi3D v1.0**（图像 → 高精度 3D 几何细化，基于 Sparc3D）——见下方 [🧊 Hi3D v1.0 评测](#-hi3d-v10图像--3d-几何细化)。

> ⚠️ **许可证提醒**：Qwen-Image-2.1 以 **Qwen Research License** 发布，**默认禁止商业用途**，商用需另向 Qwen 申请商业授权；**Z-Image 为 Apache 2.0，可免费商用**。本仓库代码仅用于研究/评估/内部测试。

---

## 为什么是这套方案（2D 生图：Qwen-Image-2.1 / Z-Image）

> 适用范围：本节的机型、ComfyUI 流程和成本估算按 **Qwen-Image-2.1** 设计，**Z-Image** 也在同一机型上实测。Hi3D v1.0 同样跑在 L40S 上，但用的是 [`scripts/hi3d/`](scripts/hi3d/) 的独立流程；**MAGI-2 需要 8×Hopper，不适用本方案**。

| 需求 | 方案 |
|---|---|
| 高质量出图 | **g6e.xlarge（NVIDIA L40S，48 GB）跑 BF16 全精度**，不降精度 |
| 不需要 7×24 | **按需实例 + 一键启停**，用完即关，只付 EBS 存储 |
| 省钱 | 权重存独立 EBS 卷秒加载；空闲自动关机兜底；结果传同区 S3 免出口费 |
| 可复现 | ComfyUI 一键安装脚本 + 固定工作流 JSON + 测试用例清单 |

**成本感受**：一次会话（开机→跑几十张→关机）约 1–2 小时 ≈ **$2–4**；一周用 3–4 次 ≈ **$30–60/月**，比常驻（~$1340/月）省 95%+。

---

## 🆚 模型对比：Z-Image vs Qwen-Image 2.1

本仓库对两个开源生图模型做了**同场景、同 prompt、同 seed 的横向对比**，覆盖 8 个场景（美食/美妆/国潮/人物三视图/5 个人物特写），每模型每场景 4 个 seed，共 **64 张样图**存于 [`assets/`](assets/)。主对比为 **Turbo vs Turbo**（均 8 步，apple-to-apple，含出图速度）；另对两个文字争议场景（兰蔻 / 海南儋州米兰）做了 **full-vs-full 完整模型复核**（同 seed，见 [`assets/fix/`](assets/fix/)），结论与 Turbo 一致。

| | Z-Image | Qwen-Image 2.1 |
|---|---|---|
| 许可证 | **Apache 2.0 ✅ 可商用** | Qwen Research ❌ 商用需授权 |
| 参数 / 显存 | 6B / 16GB 消费卡 | 7B+8B / BF16 ~30GB |
| 原生透明·编辑·2K | ✗ ✗ ✗ | ✓ ✓ ✓ |
| L40S 实测耗时 | ~13.3 s/张 | ~6.4 s/张 |

**完整对比（规格表 + 实测数据 + 选型决策表）见 [`docs/COMPARISON_zimage-vs-qwen-image-2.1.md`](docs/COMPARISON_zimage-vs-qwen-image-2.1.md)。**

一句话：要透明/编辑/2K 选 Qwen-Image 2.1；要可商用/低成本纯文生图选 Z-Image。

---

## 🧊 Hi3D v1.0（图像 → 3D 几何细化）

除 2D 生图外，本仓库评测了 3D 几何模型 **Hi3D v1.0**（[GitHub](https://github.com/hi3d-official/Hi3Dv1.0) · [权重](https://huggingface.co/hi3d-official/Hi3Dv1.0) · [在线体验](https://huggingface.co/spaces/ilcve21/Sparc3D)）。

**它不是文生图，而是"粗网格 → 高精度几何细化"模型（基于 Sparc3D，只出几何、无纹理/材质）**，需要上游粗生成器（demo 用 Tencent Hunyuan3D-2 mini）先出 coarse mesh。

**核心结论：48GB 的 L40S 即可跑满 512/1024/1536 全部三档，不需要官方说的 96GB H20。** 配 `sequential_cpu_offload` 峰值显存仅 ~15GB。

| 档位 | 峰值显存 | 耗时 | 网格（顶点/面） |
|---|---|---|---|
| 512³ | 5.1 GB | ~588 s（含下权重） | 495K / 1.0M |
| 1024³ | 15.6 GB | ~500 s | 496K / 1.0M |
| 1536³ | 14.7 GB | ~642 s | 997K / 2.0M |

细化逐级增加几何细节（发丝成块 → 单根纤维级、针织罗纹出现并锐化、五官/配饰更清晰）。**完整评测（显存/耗时表 + 法线三视图效果图 + 踩坑与复现步骤）见 [`docs/HI3D_eval.md`](docs/HI3D_eval.md)**；脚本见 [`scripts/hi3d/`](scripts/hi3d/)、样图见 [`assets/hi3d/`](assets/hi3d/)。

> ⚠️ **许可证**：Hi3D Open License 1.0，商用可以但有 MAU/营收阈值和 `Powered by Hi3D 1.0` 标注要求。

---

## 🎬 Sand.ai MAGI-2（音视频生成，调研）

[Sand.ai](https://sand.ai) 的 MAGI-2 是同时生成视频和音频的 MoE 模型。**本仓库尚未实测**，调研笔记见 [`docs/MAGI2_sandai.md`](docs/MAGI2_sandai.md)。

| | MAGI-2 Preview | MAGI-2 旗舰版 |
|---|---|---|
| 发布 / 开源 | 2026-08-05，✅ 已开源（Apache 2.0） | 2026-11-24，❌ 暂未开源（官方称即将开源） |
| 参数 | 114B（激活 6B） | 480B（激活 28B） |
| 输出 | 文/图生视频 + 同步音频，10 秒 1080p | 最长 30 秒 1080p 25fps，多参考输入（最多 20 个）+ 视频编辑 |
| 部署 | 权重约 307GB，**需 8×Hopper**（AWS p5/p5e），未蒸馏需 100+5 步 | 目前仅 API |

一句话：已开源的 Preview 跑不进本仓库的单卡 g6e，建议等蒸馏版或旗舰版开源后再实测。

---

## ⚙️ 推理框架支持

调研了 5 个推理框架对本仓库模型的支持情况（checked 2026-11-27），以 Diffusers / ComfyUI 为基线。**完整矩阵、起服务命令、已公布性能数字和选型建议见 [`docs/INFERENCE_FRAMEWORKS.md`](docs/INFERENCE_FRAMEWORKS.md)。**

| 模型 | [SGLang](https://github.com/sgl-project/sglang) | [vLLM](https://github.com/vllm-project/vllm) | [TrnRT](https://github.com/RunanywhereAI/trnrt) | [vLLM-Omni](https://github.com/vllm-project/vllm-omni) | [DeepInfer](https://github.com/deepseek-ai/DeepInfer) | Diffusers | ComfyUI |
|---|---|---|---|---|---|---|---|
| Qwen-Image-2.1（+Turbo） | ✅ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ |
| Z-Image / Turbo | ✅ | ➖ | ➖ | ✅ | ➖ | ✅ | ✅ |
| Hi3D v1.0（+Hunyuan3D-2） | 🟡 仅 Hunyuan3D-2 | ➖ | ➖ | ❌ | ➖ | ❌ | 🟡 仅 Hunyuan3D-2 |
| MAGI-2 Preview | ✅（仅 main） | ➖ | ➖ | ✅（无 1080p refiner） | ➖ | ❌ | ❌ |

✅ 官方支持　🟡 部分支持　❌ 不支持　➖ 不适用（vLLM / TrnRT / DeepInfer 是文本 LLM 引擎）。

一句话：要把出图做成 OpenAI 兼容服务，选 **vLLM-Omni** 或 **SGLang Diffusion**；单卡批量对比继续用 Diffusers。本仓库在 L40S 上的同口径实测见 [`docs/BENCH_image_frameworks.md`](docs/BENCH_image_frameworks.md)。

---

## 仓库结构

```
oss-image-models-lab/
├── README.md                  # 本文件
├── LICENSE                    # 仓库代码许可（MIT）—— 不含模型权重
├── .gitignore
├── config.env.example         # 把它复制成 config.env 并填入你的账号/区域/实例参数
├── scripts/                   # 一键启停与出图脚本
│   ├── common.sh              # 公共函数（加载 config、AWS 调用封装）
│   ├── provision.sh           # 首次：创建实例 + 权重 EBS 卷 + 安全组（只跑一次）
│   ├── start.sh               # 开机（start-instances，秒级恢复）
│   ├── stop.sh                # 关机（stop-instances，停止计费）
│   ├── status.sh             # 查看实例状态 / 公网 IP / 预估已花费
│   ├── setup-comfyui.sh       # 【在实例上运行】安装 ComfyUI + Qwen-Image-2.1 权重
│   ├── run-test.sh            # 【在实例上运行】跑测试用例并把结果传 S3
│   └── idle-autostop.sh       # 空闲 N 分钟自动关机的兜底守护（systemd timer）
├── comfyui/
│   ├── requirements.extra.txt # ComfyUI 额外依赖
│   └── models.manifest.txt    # 需要下载的权重清单（HF 仓库 + 目标目录）
├── workflows/                 # ComfyUI 工作流 JSON（API 格式，可脚本调用）
│   ├── qwen_image_2.1_t2i.json
│   └── qwen_image_2.1_edit.json
├── tests/
│   ├── prompts.jsonl          # 测试 prompt 清单（文生图 + 编辑）
│   └── run_matrix.md          # 测试矩阵与期望产出
├── assets/                    # 生成的样图资产（64 张 2D 对比 + assets/hi3d/ 的 3D 三视图）
└── docs/
    ├── SETUP.md               # 从零到出图完整步骤
    ├── COST.md                # 成本明细与省钱清单
    ├── COMPARISON_zimage-vs-qwen-image-2.1.md   # 🆚 Z-Image vs Qwen-Image 2.1 模型对比
    ├── HI3D_eval.md           # 🧊 Hi3D v1.0（图像 → 3D 几何细化）评测
    ├── MAGI2_sandai.md        # 🎬 Sand.ai MAGI-2 音视频生成模型调研（未实测）
    ├── INFERENCE_FRAMEWORKS.md # ⚙️ 推理框架（SGLang / vLLM / TrnRT / vLLM-Omni / DeepInfer）支持矩阵与实践
    └── MODELS.md              # 已测/待测开源模型与显存对照
```
（3D 评测的脚本在 `scripts/hi3d/`，样图在 `assets/hi3d/`。）

---

## 快速开始（TL;DR）

```bash
# 0. 本地：克隆并配置
git clone https://github.com/liangruibupt/oss-image-models-lab.git
cd oss-image-models-lab
cp config.env.example config.env && vi config.env   # 填 REGION / KEY_NAME / AMI 等

# 1. 本地：首次创建实例 + 权重卷（只跑一次）
./scripts/provision.sh

# 2. 本地：开机
./scripts/start.sh                  # 打印出实例公网 IP

# 3. 实例上（首次）：装 ComfyUI + 下载权重
ssh ubuntu@<IP>
cd ~/oss-image-models-lab && ./scripts/setup-comfyui.sh

# 4. 实例上：跑测试用例
./scripts/run-test.sh               # 出图 → 存 S3

# 5. 本地：用完即关
./scripts/stop.sh
```

详见 [`docs/SETUP.md`](docs/SETUP.md)。

---

## 支持的模型

已测：**Qwen-Image-2.1** 与 **Z-Image**（含横向对比，见 [`docs/COMPARISON_zimage-vs-qwen-image-2.1.md`](docs/COMPARISON_zimage-vs-qwen-image-2.1.md)），以及 3D 几何模型 **Hi3D v1.0**（见 [`docs/HI3D_eval.md`](docs/HI3D_eval.md)）。调研未实测：音视频生成模型 **Sand.ai MAGI-2**（见 [`docs/MAGI2_sandai.md`](docs/MAGI2_sandai.md)）。显存对照与扩展方式见 [`docs/MODELS.md`](docs/MODELS.md)；各模型在 SGLang / vLLM-Omni 等推理框架上的支持情况见 [`docs/INFERENCE_FRAMEWORKS.md`](docs/INFERENCE_FRAMEWORKS.md)；欢迎按同样结构扩展其它开源模型。

## 成本

见 [`docs/COST.md`](docs/COST.md)。
