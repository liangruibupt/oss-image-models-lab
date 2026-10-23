# 测试矩阵 — Vincent DESIGN 场景

5 个高质量商业广告场景，每个默认跑 **4 个 seed**（`batch=4`），全部图像作为资产存入 `assets/` 并 checkin。详见 `tests/prompts.jsonl`。

| id | 场景 | 任务 | 尺寸 | 考察点 |
|---|---|---|---|---|
| `food_sandwich_bread` | 悬浮夹心烤面包 | t2i | 1024×1408 竖 | 美食质感、芝士拉丝、中文标题+书法体+装饰边框 |
| `cosmetic_lancome_essence` | 兰蔻精华水动态广告 | t2i | 1024×1408 竖 | 液体丝绸环绕、金色背景、品牌文字排版 |
| `food_hainan_milan` | 海南儋州米兰国潮插画 | t2i | 1024×1408 竖 | 国潮插画质感、竖排书法大字、木牌卖点文字 |
| `character_three_view` | 超写实人物三视图 | t2i | 1408×1024 横 | 多视角角色设定表、配色板、细节模块布局 |
| `portrait_knit_cardigan` | 居家休闲人像 | t2i | 1024×1408 竖 | 自然光写实人像、三分法、浅景深 |

## 运行
实例上：
```bash
ONLY=food_sandwich_bread ./scripts/run-test.sh   # 先只跑场景1（4 张）
./scripts/run-test.sh                              # 跑全部 5 个场景（20 张）
```
产出：`assets/<id>_seed<n>.png` + `assets/report.json`（每张耗时）。本地 `git add assets && git commit && git push` checkin。

## 已知难点 / 评估重点
- **中文长文字 + 书法体 + 精确小字排版**：Qwen-Image-2.1 对复杂中文标题常出错或变形。样图主要看**画面构图与质感**；文字类通常需要抽卡挑选，或在后期用设计软件叠字（Photoshop/Figma）。
- **装饰边框（点线 + 桃花花瓣）**：模型不一定精确还原，视为"氛围"而非像素级约束。
- **三视图（场景4）**：对布局一致性要求高，单次生成大概率不完美，适合作为参考稿。

## 评估维度（人工 1–5 分）
提示词遵从度 / 中文文字正确性 / 画质与质感 / 构图 / 耗时（见 report.json）。
