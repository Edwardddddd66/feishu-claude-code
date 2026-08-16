# 使用说明

在 Lark / 飞书里和本机 Claude Code 对话，并管理两个常驻 bot。

## 一、在 Lark 里聊天（主要用法）

直接发普通消息即与 Claude Code 对话。输入 `/` 弹出按钮菜单，也可手敲命令。

### 后端切换（Provider）

| 命令 | 作用 |
|------|------|
| `/provider` | 查看当前后端 + 按钮切换 |
| `/provider mimo` | 切到小米 MiMo API（自动开新 session，模型固定 `mimo-v2.5-pro`） |
| `/provider anthropic` | 切回 Claude Max/Pro 订阅（用 `/model` 设的模型） |

> 订阅额度耗尽时切 `mimo` 顶上。切换会**自动开启新 session**——两端历史格式不兼容
> （MiMo 返回的 thinking 块 signature 为空，复用旧历史会触发 400）。旧会话仍可 `/resume` 找回。

### 会话管理

| 命令 | 作用 |
|------|------|
| `/new` / `/clear` | 开新 session |
| `/new plan` | 新 session 并进入 Plan 模式 |
| `/resume` | 列出历史 session（按钮选择） |
| `/resume 3` | 恢复第 3 个 session |
| `/stop` | 停止正在运行的任务 |
| `/status` | 当前 session 信息（含后端、模型、目录） |

### 模型与模式

| 命令 | 作用 |
|------|------|
| `/model opus` / `sonnet` / `haiku` | 切换模型（仅订阅后端生效；MiMo 模型固定） |
| `/mode bypass` | 跳过所有确认（默认） |
| `/mode plan` | 只规划不执行 |
| `/mode accept` | 自动接受文件编辑 |
| `/mode default` | 每次工具调用需确认 |

### 工作目录

| 命令 | 作用 |
|------|------|
| `/cd ~/project` | 切换工作目录 |
| `/ls [路径]` | 查看目录内容 |
| `/ws save <名> <路径>` | 保存命名工作空间 |
| `/ws use <名>` | 绑定当前会话到工作空间 |
| `/ws list` / `/ws remove <名>` | 列出 / 删除工作空间 |

### 信息查询

| 命令 | 作用 |
|------|------|
| `/usage` | Claude Max 用量与重置时间 |
| `/skills` | 已安装的 Claude Skills |
| `/mcp` | 已配置的 MCP Servers |
| `/help` | 帮助 |

未注册的斜杠命令（如 `/commit`、`/review`）直接转发给 Claude CLI 执行。

### 其他

- 群聊需 **@机器人** 才响应；不 @ 的消息静默忽略
- 直接发**截图**，Claude 会自动下载并分析

---

## 二、运维（Mac 终端）

项目位置：`~/Projects/lark-claudecode`

```bash
# 状态 / 进程
launchctl list | grep lark-claude
ps aux | grep main.py | grep -v grep

# 日志（排查首选）
tail -f ~/Projects/lark-claudecode/logs/huapishe.log
tail -f ~/Projects/lark-claudecode/logs/badminton.log

# 重启某个 bot（改代码 / .env 后必须重启才生效；只改 plist 文件内容不够，
# 必须 bootout 再 bootstrap 一次 launchd 才会真正加载新配置）
launchctl bootout   gui/$(id -u)/com.lark-claude.huapishe
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lark-claude.huapishe.plist
# badminton 同理替换名字，或者直接跑 ./redeploy.sh 两个一起重启+验证

# 手动前台运行（调试）
cd ~/Projects/lark-claudecode
./start.sh huapishe          # 或 badminton
```

> ⚠️ 项目目录如果整体挪过地方（比如从 `~/Claude/Projects/` 挪到 `~/Projects/`），至少三处要跟着改，
> 漏一处都会导致"看起来连上了但实际调用报错"：`~/Library/LaunchAgents/com.lark-claude.<bot>.plist`
> 里的路径、`.env.<bot>` 里的 `DEFAULT_CWD`、以及已经持久化在
> `~/.feishu-claude/<app_id>/sessions.json` 里的 `current.cwd`。当前已知状态见 `HANDOFF.md`。

两个 bot 由 launchd 守护（`KeepAlive`），崩溃会自动拉起。

---

## 三、两个 bot 对照

| bot | Lark App | 回调端口 | 默认工作目录 |
|-----|----------|---------|-------------|
| huapishe（画皮师） | `cli_aa9159…` | 9981 | `~/Projects/manga_workflow` |
| badminton（来一球） | `cli_aa915a…` | 9982 | `~/Projects/badminton_app` |

> 每个 bot 经 `BOT_ENV_FILE` 加载各自的 `.env.<bot>`，互不干扰（不再共享 `.env`）。

---

## 四、新增 bot

1. 在 [Lark 开放平台](https://open.larksuite.com/app) 创建应用，拿到 App ID / Secret
2. 复制一份 `.env.example` 为 `.env.<新名>`，填好凭证、`DEFAULT_CWD`、`CALLBACK_PORT`（错开端口）
3. 仿照 `com.lark-claude.huapishe.plist` 建一份新 plist，指向 `start.sh <新名>`
4. `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lark-claude.<新名>.plist`

## （可选）启用交互按钮：ngrok 隧道

按钮（plan 审批、选项点击、命令菜单、`/provider` 按钮）需要把本机回调端口暴露给 Lark。
不配也能用——所有命令都能手敲，按钮只是便利。

**前提与限制（重要）：**
- 需要 ngrok 账号（免费）：`ngrok config add-authtoken <你的token>`
- 想重启后 URL 不变，需固定域名（ngrok 免费提供 1 个）：在对应 `.env.<bot>` 设 `NGROK_DOMAIN=xxx.ngrok-free.app`
- **免费版同时只能开 1 条隧道**，两个 bot（端口 9981/9982）要按钮得各一条 → 免费版只能覆盖其中一个 bot，两个都要需付费
- 每个 bot 是独立 Lark 应用，回调要在**各自**开发者后台配：事件与回调 → 卡片交互配置 → 回调地址填 `https://<域名>/callback`
- 配额耗尽期间按钮也发不出卡片更新（按钮交互同样吃发送额度），建议额度恢复/升级后再启用

**步骤：**
1. `ngrok config add-authtoken <token>`
2. 在 `.env.<bot>` 设 `NGROK_DOMAIN=<你的固定域名>`
3. `./redeploy.sh` 重启，启动日志会打印回调 URL
4. 把该 URL 填进对应 Lark 应用后台的卡片交互回调地址

## 五、配置 MiMo 后端

在对应 `.env.<bot>` 填入 `MIMO_API_KEY`（其余 MiMo 变量见 `.env.example`，有默认值），
重启 bot 后即可在 Lark 用 `/provider mimo` 切换。

## 六、终端 ↔ 飞书 双向切换

同一条 Claude Code session 可以在终端和飞书之间来回接续（底层共用同一份
`~/.claude/projects/**/*.jsonl`），两个方向各有一条命令，`~/.zshrc` 里已经配好别名：

```bash
lark-in badminton       # 飞书 → 终端：接上 badminton 当前在聊的那条 session
lark-in huapishe        # 同理

lark-out "对话里一段独特文本"   # 终端 → 飞书：把当前终端会话推给对应的 bot
```

- `lark-in <bot>`（`lark-resume.sh`）：读该 bot 的 `sessions.json`，按 `ALLOWED_OPEN_IDS`
  白名单找到当前 session，自动 `cd` 到记录的工作目录并 `claude --resume`，一条命令接上，
  不用去 `sessions.json` 里翻 session_id。
- `lark-out "文本"`（`handover.py`）：在 `~/.claude/projects/` 里搜索这段指纹文本找到当前
  终端 session，**按 session 的 cwd 自动匹配应该通知哪个 bot**（huapishe 项目目录 → 通知
  huapishe 的 9981，badminton 项目目录 → 通知 badminton 的 9982），不用手动指定端口；
  匹配不到已知项目时退回默认端口，也可以 `--port <端口>` 手动指定。

两个方向接的是同一条 session，谁发消息都会往同一份历史里追加，来回切不会丢上下文。
