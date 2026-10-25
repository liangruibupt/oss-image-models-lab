# OSS Image Models Lab

> 🤖 **AI task worker / agent：动手前先读 [`AGENTS.md`](AGENTS.md) 和 [`docs/RUNBOOK.md`](docs/RUNBOOK.md)**，里面是已验证的区域/AMI/模型 id/生成参数和踩坑清单。用 `scripts/launch.py` → `scripts/box_env.sh` → `scripts/gen.py` → `scripts/teardown.py` 这套验证过的流程，**不要重新猜测或从零试错**。

一个用于**测试开源生图模型**的实验仓库，以 AWS GPU 实例按需启停的方式运行，面向"**要高质量、但不需要 7×24**"的使用场景。

首发支持 **Qwen-Image-2.1**（7B 统一文生图 + 图像编辑，原生透明 PNG）与 **Z-Image**（6B，Apache 2.0 可商用），并提供两者的**横向对比**（见下）。架构可扩展到其它开源模型（FLUX、SD3.5、Qwen-Image 系列等）。

> ⚠️ **许可证提醒**：Qwen-Image-2.1 以 **Qwen Research License** 发布，**默认禁止商业用途**，商用需另向 Qwen 申请商业授权；**Z-Image 为 Apache 2.0，可免费商用**。本仓库代码仅用于研究/评估/内部测试。

---

## 🆚 模型对比：Z-Image vs Qwen-Image 2.1

本仓库对两个开源生图模型做了**同场景、同 prompt、同 seed 的横向对比**，覆盖 8 个场景（美食/美妆/国潮/人物三视图/5 个人物特写），每模型每场景 4 个 seed，共 **64 张样图**存于 [`assets/`](assets/)。

| | Z-Image | Qwen-Image 2.1 |
|---|---|---|
| 许可证 | **Apache 2.0 ✅ 可商用** | Qwen Research ❌ 商用需授权 |
| 参数 / 显存 | 6B / 16GB 消费卡 | 7B+8B / BF16 ~30GB |
| 原生透明·编辑·2K | ✗ ✗ ✗ | ✓ ✓ ✓ |
| L40S 实测耗时 | ~13.3 s/张 | ~6.4 s/张 |

**完整对比（规格表 + 实测数据 + 选型决策表）见 [`docs/COMPARISON_zimage-vs-qwen-image-2.1.md`](docs/COMPARISON_zimage-vs-qwen-image-2.1.md)。**

一句话：要透明/编辑/2K 选 Qwen-Image 2.1；要可商用/低成本纯文生图选 Z-Image。

---

## 为什么是这套方案

| 需求 | 方案 |
|---|---|
| 高质量出图 | **g6e.xlarge（NVIDIA L40S，48 GB）跑 BF16 全精度**，不降精度 |
| 不需要 7×24 | **按需实例 + 一键启停**，用完即关，只付 EBS 存储 |
| 省钱 | 权重存独立 EBS 卷秒加载；空闲自动关机兜底；结果传同区 S3 免出口费 |
| 可复现 | ComfyUI 一键安装脚本 + 固定工作流 JSON + 测试用例清单 |

**成本感受**：一次会话（开机→跑几十张→关机）约 1–2 小时 ≈ **$2–4**；一周用 3–4 次 ≈ **$30–60/月**，比常驻（~$1340/月）省 95%+。

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
├── assets/                    # 生成的样图资产（64 张，Qwen + Z-Image 并排对比）
└── docs/
    ├── SETUP.md               # 从零到出图完整步骤
    ├── COST.md                # 成本明细与省钱清单
    ├── COMPARISON_zimage-vs-qwen-image-2.1.md   # 🆚 Z-Image vs Qwen-Image 2.1 模型对比
    └── MODELS.md              # 已测/待测开源模型与显存对照
```

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

已测：**Qwen-Image-2.1** 与 **Z-Image**（含横向对比，见 [`docs/COMPARISON_zimage-vs-qwen-image-2.1.md`](docs/COMPARISON_zimage-vs-qwen-image-2.1.md)）。显存对照与扩展方式见 [`docs/MODELS.md`](docs/MODELS.md)；欢迎按同样结构扩展其它开源模型。

## 成本

见 [`docs/COST.md`](docs/COST.md)。
