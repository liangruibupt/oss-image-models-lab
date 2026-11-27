# ⚙️ 推理框架支持与实践（SGLang / vLLM / TrnRT / vLLM-Omni / DeepInfer）

> 本文是**调研**（未在本仓库 GPU 上实测），所有支持状态 **checked 2026-11-27**，以各项目官方文档 / 仓库 / PR 为准。
> 本仓库自己的实测基准见 [`BENCH_image_frameworks.md`](BENCH_image_frameworks.md)（单独 PR 提交）。
> 文中性能数字**只引用已公布的数据**，每条都标注来源和硬件，**不是本仓库测的**。

本仓库目前用 **Diffusers**（2D 出图）和 Hi3D 自带的 `sparc3d` 包（3D）跑模型，**ComfyUI** 作为备选。本文回答一个问题：如果想把这些模型做成**在线服务**（OpenAI 兼容 API、批处理、并行、量化），主流推理框架各支持到什么程度、怎么起服务、在本仓库的 g6e（L40S 48GB）上该选哪个。

---

## 1. 框架概览

### SGLang（含 SGLang Diffusion）
[sgl-project/sglang](https://github.com/sgl-project/sglang)，Apache-2.0。原本是 LLM / 多模态理解的服务框架，仓库内的 **SGLang Diffusion**（[`python/sglang/multimodal_gen`](https://github.com/sgl-project/sglang/tree/main/python/sglang/multimodal_gen)）是独立的扩散推理运行时，覆盖图像、视频、音频、3D 和动作生成，提供 `sglang generate`（离线）/ `sglang serve`（OpenAI 兼容 `/v1/images/*`、`/v1/videos/*`）、Python SDK 和 ComfyUI 插件。硬件：NVIDIA（H100/H200/A100/B200/4090/5090 等）、AMD MI300X 系列、Intel XPU、昇腾、Apple MPS、摩尔线程。**图像：支持；视频：支持。** 最新正式版 v0.5.23（2026-11-02），部分新模型只在 main / nightly 镜像里。

### vLLM
[vllm-project/vllm](https://github.com/vllm-project/vllm)，Apache-2.0。高吞吐 **LLM 推理引擎**（PagedAttention、连续批处理、多种量化与并行），支持 NVIDIA/AMD/Intel GPU、CPU 及 TPU、Gaudi、昇腾等插件。它支持的"多模态"是**多模态理解**（如 Qwen-VL 输入图像、输出文本），**不做图像 / 视频生成**；生成类模型由下面的 vLLM-Omni 承接。**图像生成：否；视频生成：否。** 最新版 v0.34.0（2026-11-16）。

### TrnRT
[RunanywhereAI/trnrt](https://github.com/RunanywhereAI/trnrt)，Apache-2.0，由 RunAnywhere 发布。面向 **AWS Trainium2** 的开源 **LLM 推理引擎**：在一台 `trn2.48xlarge` 上用 NKI megakernel 跑 decode，提供 OpenAI / Anthropic 兼容 API，首个支持的模型是 GLM-5.3-Flash（v0.2.0，2026-11-25）。**图像生成：否；视频生成：否。** 与本仓库的扩散模型无关，列入是为了说明"Trainium 上目前没有现成的开源扩散服务路径"。

### vLLM-Omni
[vllm-project/vllm-omni](https://github.com/vllm-project/vllm-omni)，Apache-2.0。vLLM 社区的**全模态（any-to-any）**服务框架，把 vLLM 扩展到 DiT 扩散模型等非自回归架构，输出文本、图像、音频、视频、动作。`vllm serve <model> --omni` 即提供 OpenAI 兼容服务，图像走 DALL·E 风格的 `/v1/images/generations` 与 `/v1/images/edits`，视频走 `/v1/videos/*`。硬件：NVIDIA、AMD、昇腾、Intel GPU（按模型而定，见[支持模型表](https://docs.vllm.ai/projects/vllm-omni/en/latest/models/supported_models/)）。**图像：支持；视频：支持。** 最新版 v0.34.0（2026-11-22），与 vLLM 版本线对齐。

### DeepInfer
[deepseek-ai/DeepInfer](https://github.com/deepseek-ai/DeepInfer)，Apache-2.0，DeepSeek 于 2026-10-20 开源（仓库首次提交日期）。DeepSeek 生产服务所用的推理框架的开源版，本次发布只含**离线推理**，仅支持 **DeepSeek-V4.1-Flash**，硬件为 NVIDIA SM100（Blackwell）和昇腾 950。README 说明 KV cache 系统、PD 分离、负载均衡等完整服务组件未包含在内。**图像生成：否；视频生成：否。**

### 基线：Diffusers 与 ComfyUI
- **Diffusers**（[huggingface/diffusers](https://github.com/huggingface/diffusers)，Apache-2.0）：本仓库 2D 出图的默认路线（`scripts/gen.py`），单进程 Python 管线，没有服务层、批调度和并行。
- **ComfyUI**（[Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI)，GPL-3.0）：节点式工作流，本仓库保留了 `workflows/` 下的工作流 JSON，但 AGENTS.md 记录了 `comfy-kitchen` 与 torch 的 `infer_schema` 崩溃坑，**当前默认不用**。

---

## 2. 支持矩阵（checked 2026-11-27）

图例：✅ 官方支持（附文档 / recipe / PR）　🟡 部分 / 实验 / 仅支持同族的另一个模型（已注明）　❌ 该框架做生成但不支持此模型　➖ 不适用（框架不是为这种模态设计的，例如纯文本 LLM 引擎）

| 模型 | SGLang | vLLM | TrnRT | vLLM-Omni | DeepInfer | Diffusers | ComfyUI |
|---|---|---|---|---|---|---|---|
| **Qwen-Image-2.1**（+Turbo） | ✅ [cookbook](https://docs.sglang.io/cookbook/diffusion/Qwen-Image/Qwen-Image-2.1)（T2I、编辑、RGBA 透明；2.1 与 Turbo 两个 checkpoint） | ➖ | ➖ | ✅ [recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/Qwen/Qwen-Image-2.1.md)（`QwenImage21Pipeline`，v0.32.0 起） | ➖ | ✅ [`QwenImage21Pipeline`](https://huggingface.co/docs/diffusers/main/en/api/pipelines/qwenimage21)（v0.41.0，[PR #14804](https://github.com/huggingface/diffusers/pull/14804)） | ✅ [官方教程](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1)（权重 `Comfy-Org/Qwen-Image-2.1`） |
| **Z-Image / Z-Image-Turbo** | ✅ [cookbook](https://docs.sglang.io/cookbook/diffusion/Z-Image/Z-Image-Turbo)（[模型目录](https://docs.sglang.io/docs/sglang-diffusion/compatibility_matrix)同时列出 `Z-Image` 与 `Z-Image-Turbo`） | ➖ | ➖ | ✅ [Turbo recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/Tongyi-MAI/Z-Image-Turbo.md)（`ZImagePipeline`；支持表只以 Turbo 为示例，基础版未单独验证） | ➖ | ✅ [`ZImagePipeline`](https://huggingface.co/docs/diffusers/main/en/api/pipelines/z_image) | ✅ [Z-Image](https://docs.comfy.org/tutorials/image/z-image/z-image) / [Turbo](https://docs.comfy.org/tutorials/image/z-image/z-image-turbo) 教程 |
| **Hi3D v1.0**（+Hunyuan3D-2） | 🟡 只支持上游 **Hunyuan3D-2**（[`Hunyuan3D2Pipeline`](https://github.com/sgl-project/sglang/blob/main/python/sglang/multimodal_gen/configs/pipeline_configs/hunyuan3d.py)，`tencent/Hunyuan3D-2` 的 `dit-v2-0`，不是 Hi3D 用的 2mini）；Hi3D 细化 ❌ | ➖ | ➖ | ❌（支持表无 Hi3D / Hunyuan3D） | ➖ | ❌（Hi3D 用自带的 [`sparc3d`](https://github.com/hi3d-official/Hi3Dv1.0) 包，API 仿 Diffusers 但不在 Diffusers 内） | 🟡 只支持 **Hunyuan3D-2 / 2mini / 2.1**（[教程](https://docs.comfy.org/tutorials/3d/hunyuan3D-2)、[`supported_models.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/supported_models.py) 的 `Hunyuan3Dv2mini`）；Hi3D 细化 ❌ |
| **Sand.ai MAGI-2 Preview** | ✅ [cookbook](https://docs.sglang.io/cookbook/diffusion/MAGI/MAGI-2)（[PR #35014](https://github.com/sgl-project/sglang/pull/35014) 2026-11-26 合入 main，**尚未进入正式版**，需源码 / nightly） | ➖ | ➖ | ✅ [recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/SandAI/MAGI-2-preview-L20X.md)（`Magi2Pipeline`，v0.30.0 起；**不含 1080p refiner**，只出 272p/540p） | ➖ | ❌ | ❌ |

要点：
- **真正能服务本仓库扩散模型的只有 SGLang Diffusion 和 vLLM-Omni**；vLLM、TrnRT、DeepInfer 都是文本 LLM 引擎，整行 ➖。
- Hi3D 是"粗网格 → 几何细化"的 3D 模型，**没有任何框架原生支持它的细化阶段**；最多只能把上游 Hunyuan3D-2 粗生成交给 SGLang 或 ComfyUI。
- vLLM-Omni 的 [PR #2029](https://github.com/vllm-project/vllm-omni/pull/2029)（2026-04-01 合入）为 Qwen-Image 系列、Z-Image、GLM-Image 加了 HSDP 分片推理，这是并行特性，不是首次支持这些模型。

---

## 3. 已公布的性能数字（不是本仓库实测）

| 框架 · 模型 | 硬件 | 配置 | 结果 | 来源 |
|---|---|---|---|---|
| vLLM-Omni · Qwen-Image-2.1 | 1×H200 | 1024²，50 步，BF16 | 默认 compile+CUDA graph **6.04 s/张**；eager 7.31 s；同卡 Diffusers 7.74 s | 官方 recipe（[Qwen-Image-2.1.md](https://github.com/vllm-project/vllm-omni/blob/main/recipes/Qwen/Qwen-Image-2.1.md)） |
| vLLM-Omni · Qwen-Image-2.1 | 1×H200 | 1024²，50 步，eager | BF16 7.34 s / 峰值 36.9 GB；DiT 全层 FP8 6.06 s / 30.4 GB（PSNR 33.0 dB） | 官方 recipe（同上） |
| vLLM-Omni · Z-Image-Turbo | 1×RTX 5880 Ada 48GB | 1024²，9 步，在线服务 | baseline ~9.5 s / 25.0 GB；`--quantization fp8` ~5.6 s / 19.8 GB | 官方 recipe（[Z-Image-Turbo.md](https://github.com/vllm-project/vllm-omni/blob/main/recipes/Tongyi-MAI/Z-Image-Turbo.md)，社区维护） |
| vLLM-Omni · MAGI-2 Preview | 4×L20X 140GB | 540p T2VA，100 步，DLO SP4 | 端到端 563.9 s / 条 | 官方 recipe（[MAGI-2-preview-L20X.md](https://github.com/vllm-project/vllm-omni/blob/main/recipes/SandAI/MAGI-2-preview-L20X.md)） |
| vLLM-Omni · MAGI-2 Preview | 1×L20X 140GB | 272p，4 步，layerwise offload | 峰值显存 49.29 GiB，主机内存 PSS ~372 GiB | 官方 recipe（同上） |
| SGLang · Qwen-Image-2.1 | 1×H200 / 1×RTX 4090 | 1024²，40 步，CFG 1 | H200 4.48 s / 38.4 GiB；4090（文本编码器 layerwise offload）18.68 s / 22.7 GiB | 官方 cookbook（[Qwen-Image-2.1](https://docs.sglang.io/cookbook/diffusion/Qwen-Image/Qwen-Image-2.1)） |
| SGLang · Qwen-Image-2.1-Turbo（ComfyUI 插件） | 1×**L40S** | 1024²，8 步，cfg 1，热启动 | 原生 ComfyUI BF16 3.43 s / 22.9 GB；SGLD BF16 3.29 s / 26.9 GB；SGLD 在线 INT8 **2.35 s** / 23.5 GB；在线 FP8 4.49 s（更慢、画质掉） | 官方 PR（[sglang #44865](https://github.com/sgl-project/sglang/pull/44865)，在 Modal 上测） |
| SGLang · Z-Image-Turbo | 1×MI300X | 单请求 | 1.84 s，峰值 30.7 GB | 官方 cookbook（[Z-Image-Turbo](https://docs.sglang.io/cookbook/diffusion/Z-Image/Z-Image-Turbo)） |
| SGLang · MAGI-2 Preview | 4×H200 | 1080p 两阶段，100+5 步 | 348 s / 条，每卡峰值 85,274 MiB | 官方 cookbook（[MAGI-2](https://docs.sglang.io/cookbook/diffusion/MAGI/MAGI-2)） |

> 注意：这些数字的硬件、步数、编译模式都不同，**不能横向比框架快慢**。要比较请看本仓库同口径实测 [`BENCH_image_frameworks.md`](BENCH_image_frameworks.md)。

---

## 4. 实践：起服务的命令（摘自官方文档）

以下命令均来自对应官方文档，端口和 prompt 可改。生成的图片以 base64 返回在 `data[0].b64_json`。

### 4.1 vLLM-Omni + Qwen-Image-2.1

安装（官方 quickstart，需 Python 3.12、CUDA 13 驱动）：

```bash
uv venv --python 3.12 --seed && source .venv/bin/activate
uv pip install vllm==0.34.0 --torch-backend=cu130
git clone https://github.com/vllm-project/vllm-omni.git && cd vllm-omni
uv pip install -e .
```

起服务（完整模型；Turbo 把模型名换成 `Qwen/Qwen-Image-2.1-Turbo`）：

```bash
vllm serve Qwen/Qwen-Image-2.1 --omni --port 8091
```

请求（Turbo 示例；**Turbo 不要传 `num_inference_steps`、不要开 CFG**，步数由 checkpoint 自带的 `sample_sigmas` 决定）：

```bash
curl -s http://localhost:8091/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen-Image-2.1-Turbo",
    "prompt": "A ceramic teapot on a wooden table",
    "size": "1024x1024",
    "seed": 42
  }' | python -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["b64_json"])' | base64 -d > out.png
```

可选：DiT 在线 FP8（recipe 推荐保留 `img_mlp` 为 BF16 以保画质）：`--quantization fp8`，离线示例中配合 `--ignored-layers "img_mlp"`。

### 4.2 vLLM-Omni + Z-Image-Turbo

```bash
vllm serve Tongyi-MAI/Z-Image-Turbo --omni --host 127.0.0.1 --port 8091
# 可选：--quantization fp8（recipe 实测最省显存也最快）

curl -s http://localhost:8091/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
        "model": "Tongyi-MAI/Z-Image-Turbo",
        "prompt": "A cat is sitting inside a bowl.",
        "size": "1024x1024",
        "num_inference_steps": 9,
        "guidance_scale": 0,
        "seed": 42
      }' | python -c 'import sys,json; print(json.load(sys.stdin)["data"][0]["b64_json"])' | base64 -d > out.png
```

编辑走 `/v1/images/edits`（multipart，`-F image=@out.png -F prompt=... -F strength=0.6`）。

### 4.3 vLLM-Omni + MAGI-2 Preview（多卡，仅供参考）

```bash
export CUDA_VISIBLE_DEVICES=0,1,2,3
vllm serve "$MAGI2_CKPT_ROOT" --omni \
  --model-class-name Magi2Pipeline \
  --num-gpus 4 --tensor-parallel-size 1 --ulysses-degree 4 \
  --port 8091

curl -X POST http://localhost:8091/v1/videos/sync \
  -F 'prompt=A red fox walks through fresh snow.' \
  -F 'seconds=10' -F 'size=896x512' -F 'num_frames=125' -F 'fps=12.5' \
  -F 'num_inference_steps=100' -F 'seed=42' \
  -F 'extra_params={"resolution":"540p"}' \
  -o magi2_online.mp4
```

`$MAGI2_CKPT_ROOT` 需先按 recipe 用 `hf download sand-ai/MAGI-2-preview preview/ text_encoder/ vae/ turbo_vae/ stable-audio-open-1.0/ ...` 下载（约 274 GiB，不含 refiner）。

### 4.4 SGLang Diffusion + Qwen-Image-2.1

安装（官方推荐 Docker `lmsysorg/sglang`；Qwen-Image-2.1 cookbook 要求用含该集成的 nightly 镜像或源码安装）：

```bash
pip install uv
uv pip install "sglang[diffusion]" --prerelease=allow
```

离线出图 / 起服务（默认端口 30000；Turbo 换成 `Qwen/Qwen-Image-2.1-Turbo`，不要传步数）：

```bash
sglang generate --model-path Qwen/Qwen-Image-2.1 \
  --prompt "A capybara reading a book by candlelight"

sglang serve --model-path Qwen/Qwen-Image-2.1
```

请求（OpenAI 兼容 Images API）：

```bash
curl -sS -X POST "http://localhost:30000/v1/images/generations" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A ceramic teapot on a wooden table", "size": "1024x1024", "n": 1, "response_format": "b64_json"}'
```

透明 PNG：在 prompt 里写明"透明背景上的独立主体"并输出 PNG；cookbook 说明只传 `background: "transparent"` 不会去掉背景。

### 4.5 SGLang Diffusion + Z-Image-Turbo

```bash
sglang serve --model-path Tongyi-MAI/Z-Image-Turbo
# 可选 Cache-DiT 加速：SGLANG_CACHE_DIT_ENABLED=true sglang serve --model-path Tongyi-MAI/Z-Image-Turbo
```

```python
import base64
from openai import OpenAI

client = OpenAI(api_key="EMPTY", base_url="http://localhost:30000/v1")
resp = client.images.generate(model="Tongyi-MAI/Z-Image-Turbo",
                              prompt="A logo With Bold Large text: SGL Diffusion",
                              n=1, response_format="b64_json")
open("output.png", "wb").write(base64.b64decode(resp.data[0].b64_json))
```

宽高需是 16 的倍数，否则向下取整（`1000x1000` 实际出 `992x992`）。

### 4.6 SGLang Diffusion + MAGI-2 Preview（多卡，仅供参考）

```bash
sglang serve --model-path sand-ai/MAGI-2-preview \
  --num-gpus 4 --ulysses-degree 4 --performance-mode speed --port 30010
```

只接受 1920x1088（默认两阶段 1080p）和 896x512（仅 preview）两种尺寸，时长固定 10 秒。

### 4.7 基线：Diffusers / ComfyUI

- Diffusers：照本仓库 [`DEPLOY_MODEL_RUNBOOK.md`](DEPLOY_MODEL_RUNBOOK.md) 与 `scripts/gen.py`（diffusers 0.41.0，`QwenImage21Pipeline` / `ZImagePipeline`）。
- ComfyUI：照官方教程 [Qwen-Image-2.1](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1)、[Z-Image](https://docs.comfy.org/tutorials/image/z-image/z-image)、[Hunyuan3D-2](https://docs.comfy.org/tutorials/3d/hunyuan3D-2)。

---

## 5. 已知限制与坑

- **环境与本仓库现有 AMI 不一致**：本仓库的 DLAMI 是 Python 3.10 + torch 2.7（cu126）。vLLM-Omni 0.34 官方安装要求 Python 3.12 + CUDA 13 驱动（cu130 wheel）；SGLang Diffusion 推荐官方 Docker。换框架时建议用框架的官方镜像，不要往现有 venv 里硬装。
- **新模型常常只在 main / nightly**：SGLang 的 MAGI-2 支持 2026-11-26 才合入 main，不在 v0.5.23 正式版里；Qwen-Image-2.1 cookbook 也写明要用含该集成的 nightly 镜像或源码。
- **Qwen-Image-2.1 在 vLLM-Omni 上不支持 Cache-DiT / TeaCache**（recipe 的 Known Limitations），只暴露 true CFG，没有 `guidance_scale`。recipe 还注明模型 id 以官方发布为准。
- **Turbo 的步数是锁死的**：两个框架都从 `model_index.json` 的 `sample_sigmas` 读取 8 步网格，传 `num_inference_steps` 会被忽略（vLLM-Omni）或不生效（SGLang）；在完整模型上设 8 步也复现不了 Turbo。
- **L40S 上 FP8 不一定更快**：SGLang PR #44865 在 L40S 上测得 Qwen-Image-2.1 在线 FP8 比 BF16 更慢、PSNR 掉到 ~21 dB，所以其 ComfyUI 插件对单文件拒绝 FP8，INT8 才是 L40S 上的提速选项。vLLM-Omni 的 FP8 数字是在 H200 上测的，L40S（SM89）上的效果未见公布。
- **MAGI-2 的硬门槛**：SandAI 官方运行时要 8×Hopper；vLLM-Omni 的 1 卡 layerwise 方案峰值显存仍有 49.29 GiB、主机内存 ~372 GiB；SGLang 的 Qwen3.5 文本编码器 52 GiB 常驻主机内存。vLLM-Omni 集成不含 1080p refiner。
- **Hi3D 没有服务化路径**：细化阶段依赖 `flash-attn`、稀疏卷积和 Hi3D 自己的 `sparc3d` 包，目前只能按 [`HI3D_eval.md`](HI3D_eval.md) 的独立流程跑。SGLang 的 Hunyuan3D-2 是完整版 `dit-v2-0`，和 Hi3D demo 用的 2mini 不同。
- **ComfyUI 在本仓库有已知崩溃**：`comfy-kitchen` 与 torch 2.6/2.7 的 `infer_schema` 问题（见 AGENTS.md），所以 ComfyUI 列只代表"上游支持"，不代表本仓库能直接跑。

---

## 6. 选型建议（本仓库的 g6e.xlarge：1×L40S 48GB，32 GiB 内存）

| 场景 | 建议 |
|---|---|
| 偶尔批量出图、做对比（当前用法） | **继续用 Diffusers**。最简单，已验证；服务框架的批调度和并行在单卡、低并发下收益有限。 |
| 需要 OpenAI 兼容的出图 API（给应用调用） | **vLLM-Omni** 或 **SGLang Diffusion** 二选一，两者都官方支持 Qwen-Image-2.1（含 Turbo）和 Z-Image-Turbo，都走 `/v1/images/generations`。Qwen-Image-2.1 BF16 在 H200 上峰值约 37–38 GiB，按此推算单张 L40S 48GB 放得下（未在 L40S 上验证）。 |
| L40S 上要再快一点 | Qwen-Image-2.1 优先试 **SGLang 的在线 INT8**（L40S 上有公布数据）；FP8 在 L40S 上先自测再用。Z-Image-Turbo 可试 vLLM-Omni `--quantization fp8`（数据来自同为 48GB Ada 卡的 RTX 5880）。 |
| Hi3D v1.0 | 继续用 `scripts/hi3d/` 独立流程。没有框架支持 Hi3D 细化。 |
| MAGI-2 Preview | **g6e 跑不了**：显存和主机内存都不够。需要 4–8 张 80GB+ 卡（AWS p5/p5e），框架可选 SGLang（含 1080p refiner）或 vLLM-Omni（只到 540p）。 |
| Trainium / Blackwell 专用 LLM 引擎（TrnRT、DeepInfer） | 与本仓库的扩散模型无关，不用考虑。 |

---

## 7. 来源（均 checked 2026-11-27）

- SGLang：[GitHub](https://github.com/sgl-project/sglang) · [SGLang Diffusion README](https://github.com/sgl-project/sglang/tree/main/python/sglang/multimodal_gen) · [支持模型目录](https://docs.sglang.io/docs/sglang-diffusion/compatibility_matrix) · [Qwen-Image-2.1 cookbook](https://docs.sglang.io/cookbook/diffusion/Qwen-Image/Qwen-Image-2.1) · [Z-Image-Turbo cookbook](https://docs.sglang.io/cookbook/diffusion/Z-Image/Z-Image-Turbo) · [MAGI-2 cookbook](https://docs.sglang.io/cookbook/diffusion/MAGI/MAGI-2) · [Hunyuan3D-2 pipeline 配置](https://github.com/sgl-project/sglang/blob/main/python/sglang/multimodal_gen/configs/pipeline_configs/hunyuan3d.py) · [PR #35014（MAGI-2）](https://github.com/sgl-project/sglang/pull/35014) · [PR #44865（L40S INT8）](https://github.com/sgl-project/sglang/pull/44865)
- vLLM：[GitHub](https://github.com/vllm-project/vllm)（README 的模型类别列表）
- TrnRT：[GitHub](https://github.com/RunanywhereAI/trnrt)（README，v0.2.0）
- vLLM-Omni：[GitHub](https://github.com/vllm-project/vllm-omni) · [支持模型表](https://docs.vllm.ai/projects/vllm-omni/en/latest/models/supported_models/) · [Qwen-Image-2.1 recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/Qwen/Qwen-Image-2.1.md) · [Z-Image-Turbo recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/Tongyi-MAI/Z-Image-Turbo.md) · [MAGI-2 Preview recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/SandAI/MAGI-2-preview-L20X.md) · [PR #2029（HSDP）](https://github.com/vllm-project/vllm-omni/pull/2029) · [v0.32.0 release notes](https://github.com/vllm-project/vllm-omni/releases/tag/v0.32.0) · [v0.30.0 release notes](https://github.com/vllm-project/vllm-omni/releases/tag/v0.30.0)
- DeepInfer：[GitHub](https://github.com/deepseek-ai/DeepInfer)（README）
- Diffusers：[Qwen-Image 2.1 文档](https://huggingface.co/docs/diffusers/main/en/api/pipelines/qwenimage21) · [Z-Image 文档](https://huggingface.co/docs/diffusers/main/en/api/pipelines/z_image) · [PR #14804](https://github.com/huggingface/diffusers/pull/14804) · [v0.41.0 release](https://github.com/huggingface/diffusers/releases/tag/v0.41.0)
- ComfyUI：[`supported_models.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/supported_models.py) · [Qwen-Image-2.1 教程](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1) · [Z-Image 教程](https://docs.comfy.org/tutorials/image/z-image/z-image) · [Hunyuan3D-2 教程](https://docs.comfy.org/tutorials/3d/hunyuan3D-2)
- Hi3D：[Hi3Dv1.0 README](https://github.com/hi3d-official/Hi3Dv1.0)
