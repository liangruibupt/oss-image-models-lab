# Hi3D v1.0 (Sparc3D) 实测评估：图→3D 几何细化

> 模型：[hi3d-official/Hi3Dv1.0](https://huggingface.co/hi3d-official/Hi3Dv1.0) ·
> [GitHub](https://github.com/hi3d-official/Hi3Dv1.0) ·
> [在线 Space](https://huggingface.co/spaces/ilcve21/Sparc3D) ·
> 论文 [Sparc3D arXiv:2505.14521](https://arxiv.org/abs/2505.14521)
> 许可：Hi3D Open License 1.0（商用可，有 MAU/营收阈值 + `Powered by Hi3D 1.0` 标注要求）

## 一句话结论

Hi3D v1.0 **不是文生图模型**，而是一个 **“粗网格 → 高精度几何”的 3D 细化模型**（image-to-3D geometry
refinement，**只出几何，不出纹理/颜色**）。它本身不能从一张图直接出 3D，需要一个上游“粗生成器”先出 coarse
mesh——官方 demo 用 **Tencent Hunyuan3D-2 mini** 充当这个角色。实测在 **48GB L40S** 上配
`sequential_cpu_offload` 可以跑通 **512 / 1024 / 1536 全部三档**，**完全不需要官方建议的 96GB H20**。

## 和 Qwen-Image / Z-Image 的区别

| | Qwen-Image / Z-Image | Hi3D v1.0 |
|---|---|---|
| 任务 | 文本 → 2D 图像 | 图 + 粗网格 → **高精度 3D 几何** |
| 输入 | 文本 prompt | 参考图 **+ coarse mesh（.glb）** |
| 输出 | PNG 图片 | **几何网格 .glb（无纹理/无颜色）** |
| 能否独立出 3D | — | **否**，需上游粗生成器（demo 用 Hunyuan3D-2 mini） |

对比图里的彩色是**表面法线渲染**（normal map），不是生成的贴图——Hi3D 明确声明 “Geometry only”。

## 系统/流水线

三档“分辨率阶梯”，逐级细化（每档一个 pass，高档包含前面所有 pass）：

| 请求分辨率 | passes | 名义结构网格 | 稀疏抽取网格 | 用到的 transformer |
|---|---|---|---|---|
| 512  | 1 | 64³  | 512³  | `transformer_512` |
| 1024 | 2 | 128³ | 1024³ | + `transformer_1024` |
| 1536 | 3 | 192³ | 1536³ | `transformer_1024` 再跑一轮 |

端到端：**参考图 →（Hunyuan mini 出 coarse mesh）→ Hi3D 逐 pass 细化 → refined.glb**。

## 实测硬件与可行性（关键发现）

官方实测栈是 **96GB NVIDIA H20**，并声明 1536³ 只在该卡验证过、更小卡“峰值显存与可行性未知”。
我们在 **东京 g6e.xlarge（NVIDIA L40S, 46GB 可用）** 上用 `--sequential-cpu-offload` 实测：

| 档位 | 结果 | 峰值显存 | 耗时* | 输出网格（顶点/面） | 文件大小 |
|---|---|---|---|---|---|
| 512  | ✅ 成功 | **5.1 GB** | ~588s（含首次下权重） | 495K / 1.0M | 18 MB |
| 1024 | ✅ 成功 | **15.6 GB** | ~500s | 496K / 1.0M（面数封顶 1M） | 18 MB |
| 1536 | ✅ 成功 | **14.7 GB** | ~642s | **997K / 2.0M** | 36 MB |

\* 耗时含 CPU offload 的换入换出开销（offload 用时间换显存）；512 那次额外含首轮权重下载。

**结论：48GB 的 L40S（~$1.86/hr）足以跑满 1536³ 全档，不需要大显存卡。** 官方 96GB 要求偏保守，
offload 模式下峰值显存只有 ~15GB。关掉 offload 会更快但显存占用更高（未测）。

## 实测效果（法线渲染，前 / 3-4 / 侧 三视图）

### 输入参考图
<img src="../assets/hi3d/input_ref.png" width="260">

### 阶梯对比：Coarse → 512 → 1024 → 1536
从上到下：Hunyuan 粗网格 → Hi3D 512 → 1024 → 1536。
<img src="../assets/hi3d/comparison_ladder.png" width="900">

逐档观察：
- **Coarse（Hunyuan mini）**：轮廓/项链吊坠/手镯/发丝大形已经不错，但表面偏平滑、发丝成块。
- **Hi3D 512**：发丝出现条状起伏，**针织背心出现罗纹织物纹理**，手镯珠子分明，五官更清晰。
- **Hi3D 1024**：发丝更锐利、流向更细；罗纹更规整、下摆针织成形；五官更精细。
- **Hi3D 1536**：发丝细到单根纤维级（侧视最明显）；罗纹锐利规整；2M 面带来最高几何密度。

细化是**真·逐级增加几何细节**，不是简单平滑——印证了官方“high-resolution geometry refinement”的说法。

## 复现

环境（L40S / DLAMI，Python 3.10）：

```bash
# 1) Hi3D 本体（锁定内核栈）
git clone https://github.com/hi3d-official/Hi3Dv1.0.git && cd Hi3Dv1.0
python3.10 -m venv .venv && . .venv/bin/activate
pip install torch==2.5.0+cu124 torchvision==0.20.0+cu124 --extra-index-url https://download.pytorch.org/whl/cu124
pip install packaging ninja psutil
pip install --no-build-isolation flash-attn==2.7.4.post1
pip install -c docker/constraints.txt -e ".[inference]"
pip install -c docker/constraints.txt -e ".[demo]" onnxruntime   # rembg 去背景

# 2) 上游粗生成器 Hunyuan3D-2 mini（第三方，另装）
cd .. && git clone https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git
echo "$PWD/Hunyuan3D-2" > "$(python -c 'import site;print(site.getsitepackages()[0])')/hunyuan.pth"
pip install einops opencv-python-headless pymeshlab scikit-image tqdm pyyaml xatlas
```

**依赖冲突修复（重要）**：Hunyuan 会把 `diffusers` 顶到 0.41.0，在 torch 2.5 上报
`torch.accelerator` 缺失；需锁 **`diffusers==0.31.0` + `huggingface-hub==0.28.1`**
（同时满足 sparc3d `>=0.28,<1` 和 transformers 4.46.3 的 `<1.0`）。transformers 保持 Hi3D 锁定的
4.46.3（hy3dgen 虽警告要 `>=4.48`，但非致命）。

**首次运行坑**：Hi3D 的 loader 拒绝 HF 缓存里的符号链接；需把
`~/.cache/huggingface/hub/models--hi3d-official--Hi3Dv1.0/snapshots/*/` 下的所有 symlink 解引用为实体文件
（或下载时禁用 symlink）。否则 1024/1536 报 `model repository has an unexpected symlink`。

端到端跑一张图：

```bash
python demo/image_to_mesh.py \
  --model hi3d-official/Hi3Dv1.0 \
  --image input.png --output refined.glb --coarse-output coarse.glb \
  --resolution 1536 --seed 0 --remove-background --sequential-cpu-offload
```

已有 coarse mesh 时只做细化（不依赖 Hunyuan）：`demo/refine_mesh.py --image ... --coarse-mesh coarse.glb ...`。

## 评价小结

- **优点**：几何细节是真的强（发丝/织物纹理/相对小的配件都能细化出来）；48GB 卡就能跑满 1536³，门槛比官方宣称低很多；许可允许商用。
- **限制**：只出几何、无纹理/颜色；必须配上游粗生成器（demo 绑定 Hunyuan3D-2 mini，依赖冲突需手工解）；offline 还要本地化 DINOv2/CLIP/Hunyuan；隐藏面是“合理补全”不是真实重建；输出做了归一化，不保留原始世界坐标/绝对尺度。
- **适用**：已有/能生成粗网格、需要把它细化到可用于渲染或打印的高精度几何的场景。
