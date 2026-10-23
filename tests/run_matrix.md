# 测试矩阵

针对 Qwen-Image-2.1 的能力覆盖，每条对应 `prompts.jsonl` 里的一个用例。

| id | 任务 | 考察点 | 期望产出 |
|---|---|---|---|
| `photoreal_portrait` | 文生图 | 写实质量基线、景深、光影 | 1024×1536 写实人像，细节锐利 |
| `chinese_text_poster` | 文生图 | **中文**排版/文字渲染 | 海报，标题文字可辨认、无乱码 |
| `english_text_signage` | 文生图 | 英文长文字、小字清晰度 | 菜单板，价格文字清晰 |
| `transparent_sticker` | 文生图 | **原生透明 PNG (RGBA)** | 带真实 alpha 通道的贴纸，无白底 |
| `complex_scene_2k` | 文生图 | 复杂场景 + **2K** 分辨率 | 2048×1152 赛博朋克夜市，构图完整 |
| `product_shot` | 文生图 | 商业产品图 | 干净背景的产品渲染 |
| `edit_bg_swap` | 编辑 | 保主体换背景 | 主体不变，背景替换 |

## 评估维度（人工打分建议 1–5）
- **提示词遵从度**：是否画出了要求的内容
- **文字正确性**：标题/价格等文字是否无误（中英文分别记）
- **画质**：清晰度、伪影、解剖/结构合理性
- **透明度**：`transparent_sticker` 的 alpha 是否干净（用带透明格的查看器确认）
- **耗时**：`report.json` 里每条的 `seconds`（g6e/L40S BF16 的参考基线）

## 如何跑
实例上：`./scripts/run-test.sh` → 结果与 `report.json` 落在 `/mnt/weights/outputs/<时间戳>/`，并同步到 S3（若配了 `S3_BUCKET`）。

## 编辑用例的输入图
`edit_bg_swap` 需要一张输入图：把图命名为 `input.png` 放进 ComfyUI 的 `input/` 目录（或改 overrides 里的文件名）。仓库默认不附带图片（见 `.gitignore`）。
