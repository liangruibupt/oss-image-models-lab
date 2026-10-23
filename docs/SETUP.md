# SETUP — 从零到出图

## 前置条件
- 本地装好 AWS CLI 并 `aws configure`（或 SSO 登录），账号有 EC2 权限。
- 一个已存在的 **EC2 key pair**（用于 SSH），把 `.pem` 路径填进 `config.env`。
- 一个与实例**同区域**的 **S3 桶**（可选，用于存结果）。
- 账号在目标区域有 `g6e.xlarge` 的 vCPU 配额（首次可能需提工单申请 G 实例配额）。

## 步骤

### 1. 配置
```bash
cp config.env.example config.env
vi config.env     # 填 REGION / KEY_NAME / SSH_KEY_PATH / S3_BUCKET / MY_IP_CIDR
chmod +x scripts/*.sh
```
强烈建议设 `MY_IP_CIDR=<你的公网IP>/32`，把 SSH 锁到你自己。

### 2. 首次创建（只跑一次）
```bash
./scripts/provision.sh
```
它会：解析最新 Deep Learning AMI → 建安全组 → 起 `g6e.xlarge`（按需）→ 建并挂载一块独立的权重 EBS 卷。结束后打印实例 IP 和后续命令。

### 3. 把仓库同步到实例
```bash
source config.env
IP=$(./scripts/status.sh | awk '/Public IP/{print $NF}')
rsync -av -e "ssh -i $SSH_KEY_PATH" ./ ubuntu@$IP:~/oss-image-models-lab/
```

### 4. 实例上：装 ComfyUI + 下权重（首次约 15–30 分钟，取决于下载速度）
```bash
ssh -i "$SSH_KEY_PATH" ubuntu@$IP
cd ~/oss-image-models-lab
./scripts/setup-comfyui.sh          # 格式化/挂载权重卷、装 ComfyUI、下载 Qwen-Image-2.1
./scripts/idle-autostop.sh          # （建议）装空闲自动关机兜底
```
权重落在挂载的 EBS 卷 `/mnt/weights`，`stop` 后保留，**下次无需重下**。

### 5. 跑测试用例
```bash
./scripts/run-test.sh               # 跑 tests/prompts.jsonl，出图 → /mnt/weights/outputs/<ts>/ → S3
```
或交互式用 UI：
```bash
cd /mnt/weights/ComfyUI && source .venv/bin/activate
python main.py --listen 127.0.0.1 --port 8188
# 本地另开一个终端做隧道：
ssh -i "$SSH_KEY_PATH" -L 8188:localhost:8188 ubuntu@$IP
# 浏览器打开 http://localhost:8188
```

### 6. 用完即关（回到本地笔记本）
```bash
./scripts/stop.sh                   # 停止计费；权重卷保留
```

## 日常循环（之后每次）
```bash
./scripts/start.sh      # 开机，打印 IP
# ...ssh 上去 ./scripts/run-test.sh 或用 UI...
./scripts/stop.sh       # 关机
```

## 工作流节点校准（重要）
`workflows/*.json` 是**起始模板**，节点 id 与 `tests/prompts.jsonl` 的 overrides 对应。不同 ComfyUI 版本的 Qwen 专用节点（加载器/采样器）可能略有差异。第一次请在 UI 里打开一次官方 Qwen-Image-2.1 工作流、确认能出图，再用 **Save (API Format)** 导出覆盖本仓库的 JSON，并保持节点 id 与 prompts 的 overrides 一致（或反过来改 overrides）。

## 清理（彻底不用了）
```bash
# 终止实例（root 卷随之删除）；按需保留或删除权重卷
source config.env
aws --region "$REGION" ec2 terminate-instances --instance-ids "$INSTANCE_ID"
# 权重卷要删的话（⚠️ 不可逆，确认后由你手动执行）：
# aws --region "$REGION" ec2 delete-volume --volume-id "$WEIGHTS_VOLUME_ID"
```
> 注意：删除类操作（terminate/delete-volume）请你本人确认后执行，脚本不替你删。
