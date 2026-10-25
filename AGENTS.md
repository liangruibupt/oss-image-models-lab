# AGENTS.md — 给 AI task worker 的首读指引

> **任何在本仓库出图的 agent，动手前先读这份文件和 [`docs/DEPLOY_MODEL_RUNBOOK.md`](docs/DEPLOY_MODEL_RUNBOOK.md)。**
> 这些是已验证的最佳实践，照做即可，**不要重新猜测或从零试错**（下面每条都是真实踩过的坑）。

## 这个仓库是什么
在 AWS GPU 实例上按需启停、测试开源生图模型（Qwen-Image-2.1 / Z-Image）的实验台。要高质量、不要 7×24，用完即关。

## 出图任务的标准流程（照抄）
1. **读 [`docs/DEPLOY_MODEL_RUNBOOK.md`](docs/DEPLOY_MODEL_RUNBOOK.md)** —— 已验证的区域、AMI、实例类型、精度、模型 id、生成参数。
2. **启实例**：`python scripts/launch.py`（boto3，本机实例角色即可，无需用户给 AWS key）。默认 **ap-northeast-1 / g6e.xlarge（L40S 48GB）**。
3. **装环境**：`scripts/box_env.sh`（venv + torch 2.7 + diffusers）。**不要用 ComfyUI**（坑 #1）。
4. **出图**：`scripts/gen.py`（Diffusers 路线，已验证；两模型 × turbo/完整，参数锁定 DEPLOY_MODEL_RUNBOOK）。prompts 在 `tests/prompts.jsonl`。
5. **拉回 + 入库**：图存 `assets/`，走 feature 分支 + PR（见下）。
6. **跑完 terminate**：`python scripts/teardown.py`，除非用户明确要求保持开机。

## 铁律（踩过的坑，别重犯）
- **repo 工作副本放稳定路径、只 `git pull`，不要每次重新 clone**：把 repo 放在 `[PROJECT]` 目录（scratch 之外，跨会话稳定），不要放 `$KIROCREW_SCRATCH`（会话恢复后 runtime-id 变、旧目录被回收，clone 和你写的文件一起丢——曾因此让 commit 目录与写入目录错位、文件没进 PR）。
- **出图走 Diffusers，不碰 ComfyUI**：最新 ComfyUI 的 `comfy-kitchen` 与 torch 有 `infer_schema list[int]` 崩溃 bug。
- **torch 用 2.7.x**（PyPI 默认 cu126 wheel）。2.6 触发 comfy-kitchen bug；cu124 索引没有 2.7。
- **模型 id 以 DEPLOY_MODEL_RUNBOOK 为准，别猜**：Z-Image 基础 = `Tongyi-MAI/Z-Image`（不是 `Z-Image-Base`，那个 404）；Turbo = `Tongyi-MAI/Z-Image-Turbo`。Qwen = `Qwen/Qwen-Image-2.1`(完整) / `Qwen/Qwen-Image-2.1-Turbo`(快)。
- **对比要同口径**：修复/重跑某模型时，用**和首次对比相同的模型与档位**（如首次是 Z-Image-Turbo，修复也用 Turbo + 多 seed），否则 Turbo-vs-基础 的对比不公平。要整体升级就两模型一起换档。
- **文字质量**：Turbo（8步）文字易糊；要准用**完整模型 + 30-40 步 + cfg≈4**。中文长词 Qwen 更准，英文品牌词 Z-Image 更准，**商业稿都需人工校字**。
- **SSH key 别只存 scratch**：用 `launch.py` 的 import-key-pair（幂等）；临时找回用 EC2 Instance Connect（60s，连上后追加进 `~/.ssh/authorized_keys`）。
- **git push 分步**：先 `git commit`（本地），再单独 `git push origin <feature-branch>`，再 `gh pr create`+`gh pr merge`。**绝不**把校验/查询与 push 写同一行，**绝不**直接 push 到 master（guardrail 拦受保护分支名）。
- **AWS 写操作用 boto3**，不用 CLI（CLI run-instances/create 等被 guardrail 拦，boto3 走实例角色正常）。
- **入库前自查**：`git status` 确认要提交的新文件都 staged；PR 合并后用 `gh api .../trees/master` 核对文件真在 master 上（别只信 commit 回显）。

## 成本纪律
g6e.xlarge ~$1.86/hr。**出完即关**，别挂机（本项目曾挂机 21 小时烧 ~$39）。空闲兜底见 `scripts/idle-autostop.sh`。
