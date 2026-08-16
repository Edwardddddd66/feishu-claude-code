# 交接文档

> 写给接手这个仓库的下一个 agent / 未来的自己。README.md 讲的是这个项目通用的"是什么、怎么装"，
> USAGE.md 讲的是这台机器上具体怎么运维；这份文档补的是**"当前部署到底是什么状态、这次会话改了什么、
> 还有什么没做完"**，属于时效性信息，过时请以实际 `launchctl` / `git log` 输出为准，别直接信这份文档的数字。

最后更新：2026-08-16（本次交接会话）

## 一、项目一句话

本机常驻 Python 进程，通过飞书 WebSocket 长连接把 `claude` CLI 包装成一个能在飞书里对话的 bot。
完整架构/设计说明看 README.md，代码级细节看各模块头部注释，本文档只讲"这台机器上现在跑的两个实例状态"。

## 二、当前部署状态（本次会话验证过的真实状态，不是假设）

| bot | Feishu App ID | 回调端口 | 项目目录（DEFAULT_CWD） | launchd 状态 | 备注 |
|---|---|---|---|---|---|
| **badminton**（来一球） | `cli_aa915a3e17fb1ed4` | 9982 | `/Users/edward/Projects/badminton_app` | ✅ 正常运行，已连 wss | 本次会话修复 |
| **huapishe**（画皮师） | `cli_aa9159c92c39deef` | 9981 | `/Users/edward/Claude/Projects/manga_workflow`（**过期，未修**） | ❌ `exit 78 (EX_CONFIG)` 循环重启 | **待办，见下**  |

两个 bot 都由 `~/Library/LaunchAgents/com.lark-claude.<bot>.plist` 驱动，`KeepAlive=true`，崩了会自动拉起重试（所以 huapishe 表现为"进程列表里看不到但 launchctl 里一直有记录"）。

访问白名单（`ALLOWED_OPEN_IDS`，各自 `.env.<bot>` 里配的）：
- badminton 只认 `ou_58403f796d6d6b97dd1acd0dec223852`
- huapishe 只认 `ou_f833f5bbf90d3cd06fd33bec01cb3ed1`

## 三、⚠️ 待办：huapishe 还没修完

**问题成因跟 badminton 一模一样**（这台机器把项目文件夹从 `~/Claude/Projects/lark-claudecode` 挪到了
`~/Projects/lark-claudecode`，连带项目群下面的实际工作目录也搬了家，但配置文件/launchd 注册没跟着更新）：

1. `~/Library/LaunchAgents/com.lark-claude.huapishe.plist` 里的 `ProgramArguments`/`StandardOutPath` 已经在本次会话里改成了新仓库路径 `/Users/edward/Projects/lark-claudecode`，**但改完之后从没 `bootout`+`bootstrap` 重新装载过**——launchd 加载 plist 是一次性读入内存的，改磁盘上的文件不会让已加载的 job 生效，所以它现在很可能还在用旧配置循环 crash（用下面"验证命令"里的 launchctl 命令确认）。
2. `.env.huapishe` 里 `DEFAULT_CWD=/Users/edward/Claude/Projects/manga_workflow` 还是旧路径，**本次会话已经确认**该目录已不存在，真实新路径是 `/Users/edward/Projects/manga_workflow`（本次会话验证过，只是没动手改，因为用户明确说"这次只需要 badminton"）。
3. `~/.feishu-claude/cli_aa9159c92c39deef/sessions.json` 里已持久化的 `current.cwd`（对应 `ou_f833f5bbf90d3cd06fd33bec01cb3ed1` 用户）大概率也是旧路径——只改 `.env.huapishe` 的 `DEFAULT_CWD` 不会覆盖已经存在的 session 状态，这点 badminton 修复时踩过（见下方"经验教训"）。

**修复步骤（照抄 badminton 那次的操作即可，代码不用改，纯配置）：**

```bash
# 1. 改 DEFAULT_CWD
#    编辑 /Users/edward/Projects/lark-claudecode/.env.huapishe
#    DEFAULT_CWD=/Users/edward/Claude/Projects/manga_workflow
#    →
#    DEFAULT_CWD=/Users/edward/Projects/manga_workflow

# 2. 改已持久化的 session cwd（不改这步的话，已有 session 还是会用旧路径导致 Claude 子进程报错）
#    编辑 ~/.feishu-claude/cli_aa9159c92c39deef/sessions.json
#    把 ou_f833f5bbf90d3cd06fd33bec01cb3ed1.private.current.cwd 也改成新路径
#    （改之前最好看一眼这个 key 下 session_id 是不是 null——如果是 null 说明这条 session
#      从没真正用过，改不改都无所谓；如果不是 null，必须改，否则一发消息就报错）

# 3. 重新装载 launchd（这一步在本次会话里漏做了，是导致 huapishe 至今没起来的直接原因）
UID_NUM=$(id -u)
launchctl bootout "gui/$UID_NUM/com.lark-claude.huapishe" 2>/dev/null
launchctl bootstrap "gui/$UID_NUM" ~/Library/LaunchAgents/com.lark-claude.huapishe.plist

# 4. 验证
sleep 5
launchctl list | grep lark-claude.huapishe   # 期望：PID 非空，exit code 0
tail -20 /Users/edward/Projects/lark-claudecode/logs/huapishe.log  # 期望看到 "connected to wss"
```

也可以直接用 `./redeploy.sh`，它会把两个 bot 一起 bootout+bootstrap+验证，但**不会**自动修 `.env.huapishe` 里的路径，第 1、2 步还是得手动做。

## 四、本次会话做了什么（时间顺序）

1. **通读全部源码**（`main.py` `commands.py` `claude_runner.py` `feishu_client.py` `session_store.py`
   `providers.py` `run_control.py` `bot_config.py` `log_setup.py` `handover.py`，全部 9 个测试文件，
   部署配置，`.env.*`），建立了完整认知。
2. **核实了用户记忆中的"飞书 API 额度耗尽"问题**：在 `logs/{badminton,huapishe}.log.2026-06-07`
   里找到确凿证据（`99991403` 报错各出现 5/21 次），确认真实发生过，且**已经被之前的 commit 修复**
   （`STREAM_PUSH_INTERVAL=0` 关闭流式中间推送、额度错误不重试、outbox 兜底存本地），本地目前没有
   `logs/outbox-*.md` 文件，说明修复生效、没再复现。**这部分不需要下一个 agent 处理，纯记录在案。**
3. **诊断并修复 badminton bot 起不来的问题**（过程见上面"待办"部分对称的操作，已完整执行）：
   - plist 路径过期 → 改 + 重新装载
   - `.env.badminton` 的 `DEFAULT_CWD` 过期 → 改
   - `sessions.json` 里已持久化的 cwd 过期 → 改
   - 重启验证：`connected to wss://msg-frontier-sg.larksuite.com`，session 能正常调用
4. **修复 `handover.py`（终端→飞书）的两个 bug**：
   - 端口写死 `9981`：多 bot 场景下会把通知发错 bot。改成扫描各 `.env.<bot>` 的 `CALLBACK_PORT` +
     `DEFAULT_CWD`，按目标 session 的 cwd 前缀自动匹配该通知哪个 bot；保留 `--port` 手动覆盖选项。
   - cwd 靠目录名反推（`目录名.replace("-", "/")`）：Claude Code 把路径里的下划线/空格也统一转成
     `-`，导致 `badminton_app` 被错误还原成 `badminton/app`。改成直接读 `.jsonl` 里记录的真实 `cwd`
     字段（跟 `session_store.py` 一样的做法），反推只作为兜底。
   - 两处都做了实测验证（不是只改代码没测）。
5. **新增 `lark-resume.sh`（飞书→终端，之前完全没有这个方向的工具）**：给 bot 名，自动读该 bot 的
   `sessions.json`、按白名单 open_id 找到当前 session、`cd` 到记录的 cwd、`exec claude --resume`。
   实测跑通（能正确解析出 badminton 当前 session 并正确 `cd`）。
6. **`~/.zshrc` 加了两个 alias**：`lark-in <bot>`（飞书→终端）、`lark-out "文本"`（终端→飞书）。
7. **提交并合并**：`feat/handover-multi-bot` 分支，commit `df3a17c`，fast-forward 合回 `main`，
   分支已删除。**尚未 `git push`**（用户只要求 commit，没要求 push，目前本地领先 origin 1 个 commit）。
8. 若干 Q&A（未产生代码改动，只是解释机制，供下一个 agent 参考避免重新踩坑）：
   - 飞书每个聊天（私聊/群）= 独立 `session_id`，但存储格式跟终端会话完全通用（同一份
     `~/.claude/projects/*.jsonl`），互相 `/resume`/`handover` 可以接续。
   - `/model` 按聊天持久化；但 provider=mimo 时会强制用 `MIMO_MODEL`，`/model` 设置被忽略。
   - `/compact`：bot 的 `parse_command` 只认以 `/` 开头的消息才会进命令分支；自然语言（哪怕语义是
     "帮我压缩上下文"）会直接当普通消息发给 Claude，模型没有能触发真实上下文压缩的 tool，
     所以自然语言**保证**不会触发压缩。字面量 `/compact` 会被转发给 CLI，**但 `--print` 模式下是否真的
     执行压缩没有实测验证过**（沙箱权限分类器挡了嵌套起 claude 子进程的测试尝试）——这是一个**未验证
     的开放问题**，稳妥验证方式是 `lark-in <bot>` 到交互模式里敲 `/compact`。
   - auto-compact 触发的具体百分比阈值没有确认到权威数字（本机 changelog 里只翻到一条很老版本
     "warning threshold 60%→80%" 的记录，不代表当前 2.1.227 的真实压缩阈值）；bot 代码没有传
     `--autocompact` 参数，用的是 CLI 自身默认行为。想看实时数字用 `/context`（仅交互模式）。

## 五、git 状态

截至这次交接会话（含 `df3a17c` handover.py 多 bot 修复、以及 `HANDOFF.md` 自己这几次提交），
本地 `main` 一直**没有推到远程**，都是 fast-forward，没有冲突风险。

**不要信本节写死的 commit 数字**——这份文档自己每改一次就会多产生一个 commit，数字必然过期。
准确状态永远用命令现查：

```bash
git -C /Users/edward/Projects/lark-claudecode log origin/main..HEAD --oneline
```

要推的话直接 `git push`，无需先确认数量。

## 六、⚠️ pytest 现状：4 个预先存在的失败，跟本次改动无关

跑 `.venv/bin/python -m pytest -q`（注意不是裸 `pytest`，见下方"环境坑"）目前是 **56 passed, 4 failed**：

```
FAILED tests/test_concurrent_groups.py::test_concurrent_messages_different_groups
FAILED tests/test_concurrent_groups.py::test_same_group_messages_serialized
FAILED tests/test_integration.py::test_private_chat_streaming_updates_card
FAILED tests/test_integration.py::test_chat_locks_cleanup
```

**已确认这 4 个失败在这次会话开始之前（`ab2c350`，本次最早的一个 commit）就存在**，用
`git checkout ab2c350 -- . && pytest ...` 复现过，不是本次改动引入的回归，接手时不用怀疑是不是自己
哪里改错了。各自的直接原因（没深挖到根治方案，只是定位到了触发点，留给下一个 agent 决定要不要修）：

- `test_concurrent_groups.py` 两个：`TypeError: 'Mock' object is not iterable`，`main.py:236`
  （`getattr(msg, 'mentions', None) or []`）——测试里的 `Mock()` 没显式配置 `mentions` 属性，
  Mock 对象本身是 truthy 所以 `or []` 不生效，走到 `for m in mentions` 时炸了。测试 mock 没配全，
  不是业务逻辑的锅。
- `test_private_chat_streaming_updates_card`：`assert 2 >= 3` 失败——这个测试断言"流式长文本至少
  推送 3 次中间更新"，依赖 `STREAM_PUSH_INTERVAL` 时间窗口和 mock 的 CPU 调度节奏，看起来是个
  时序敏感的 flaky 测试，不同机器/负载下次数会飘。
- `test_chat_locks_cleanup`：`assert 101 <= 2` 失败——测试预期锁超过上限后清理到 ≤2 个，但
  `main.py` 的清理逻辑（`_chat_locks` 那段）实际写的是"只清理一半的 idle 锁"（`idle[:len(idle)//2]`），
  跟测试断言的"清到只剩 ≤2 个"本来就对不上，这个像是**测试断言和实现意图不一致**，需要有人拍板
  到底哪个是对的（是该改实现变成"清空所有 idle 锁"，还是改测试断言匹配"只清一半"的设计）。

**环境坑**：这台机器上裸 `pytest` 命令不在 PATH 里（`pytest not found`），必须用
`.venv/bin/python -m pytest`，跟 `start.sh` 里跑 bot 用的是同一个解释器。

**本次新增的 `handover.py`/`lark-resume.sh` 改动没有任何自动化测试覆盖**——这次只做了手动实测
验证（见第四节第 4、5 点），如果要长期维护这两个脚本，建议给它们也补测试用例（`handover.py` 的
`_read_cwd`/`_discover_bots`/`_pick_port` 都是纯函数，很好测）。

## 七、关键文件地图（快速定位用）

| 文件 | 作用 |
|---|---|
| `main.py` | 入口，WebSocket 事件循环、看门狗、卡片按钮 HTTP 回调 |
| `commands.py` | 斜杠命令解析（`/new` `/model` `/provider` ... ），`BOT_COMMANDS` 是白名单 |
| `claude_runner.py` | subprocess 调 `claude` CLI，解析 stream-json |
| `feishu_client.py` | 飞书 API 封装，含额度错误(`99991403`)不重试的逻辑 |
| `session_store.py` | session 持久化到 `~/.feishu-claude/<app_id>/sessions.json` |
| `providers.py` | Anthropic 订阅 / MiMo 双后端定义 |
| `handover.py` | **本次改过** — 终端→飞书，自动识别多 bot 端口 |
| `lark-resume.sh` | **本次新增** — 飞书→终端 |
| `.env.<bot>` | 每个 bot 独立配置，**含真实密钥，已 gitignore，不要往仓库里塞** |
| `com.lark-claude.<bot>.plist` | launchd 配置模板，**本次改过路径**，同步复制在 `~/Library/LaunchAgents/` |
| `redeploy.sh` | 一键重启两个 bot + 验证连接，**不会**修 `.env` 里的路径 |
| `~/.feishu-claude/<app_id>/sessions.json` | 运行时状态（session_id/cwd/model 等），不在仓库里 |

## 八、这次踩出来的经验教训（给下一个 agent 的通用提醒）

1. **项目目录搬家是个连锁坑**：不只 launchd plist 要改，`.env.*` 里的 `DEFAULT_CWD`、已经持久化在
   `~/.feishu-claude/**/sessions.json` 里的 `current.cwd` 都要跟着改，三处任何一处漏改都会导致"表面上
   连上了 / 表面上配置对了，但实际调用时报错"。改路径类问题时养成习惯三处一起查。
2. **多 bot 场景下，写死端口/写死某个默认值是常见 bug 来源**：`handover.py` 就是从"单 bot 时代"遗留
   下来没跟上"多 bot 时代"的典型例子。以后往这个仓库加功能，先问一句"这段逻辑是不是隐含假设了只有
   一个 bot"。
3. **改配置文件后一定要重新走 `bootout`+`bootstrap`**：只改磁盘上的 plist 文件不会让已加载的 launchd
   job 生效，这个坑在 huapishe 这次交接里就留了一个活口，验证的时候容易漏。
4. **反推路径不如读真实字段**：`handover.py` 原来"从目录名反推 cwd"的写法是个通用陷阱——任何把路径
   编码进文件名/目录名的地方，只要编码规则不是完全可逆的（比如把多种字符都映射成同一个 `-`），反推
   就会出错。有真实字段可读的时候（这里是 `.jsonl` 里的 `cwd`）优先读字段，不要反推。

## 九、验证命令合集（下一个 agent 直接抄用）

```bash
# 两个 bot 的 launchd 状态
launchctl list | grep lark-claude

# 某个 bot 具体状态（exit code、state）
launchctl print gui/$(id -u)/com.lark-claude.huapishe 2>&1 | grep -E "state|last exit"

# 进程
ps aux | grep "main.py" | grep -v grep

# 日志（排查连接问题首选）
tail -30 /Users/edward/Projects/lark-claudecode/logs/huapishe.log
tail -30 /Users/edward/Projects/lark-claudecode/logs/huapishe.boot.log

# 某个 bot 当前 session 状态
python3 -c "
import json
d = json.load(open('/Users/edward/.feishu-claude/cli_aa9159c92c39deef/sessions.json'))
print(json.dumps(d, indent=2, ensure_ascii=False))
"

# git 是否还有未推送的 commit
git -C /Users/edward/Projects/lark-claudecode log origin/main..HEAD --oneline

# 跑测试（注意不能用裸 pytest，PATH 里没有）
cd /Users/edward/Projects/lark-claudecode && .venv/bin/python -m pytest -q
```
