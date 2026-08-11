#!/bin/bash
# 反方向 handover：把飞书里某个 bot 当前的 Claude session 接到终端继续聊。
# 跟 handover.py（终端→飞书）配对，这个是 飞书→终端。
#
#   用法: ./lark-resume.sh badminton
#         ./lark-resume.sh huapishe
#
# 原理：session 存储是共用的（~/.claude/projects/*.jsonl），飞书这边只是
# 记录了"当前指向哪个 session_id"，直接读出来 cd 过去 --resume 即可，
# 不需要经过任何网络请求。
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
BOT="${1:?用法: lark-resume.sh <bot名>，如 badminton / huapishe}"
ENV_FILE="$DIR/.env.$BOT"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 找不到配置文件: $ENV_FILE" >&2
    echo "可用的 bot: $(ls "$DIR"/.env.* 2>/dev/null | grep -v example | sed -E 's#.*/\.env\.##' | tr '\n' ' ')" >&2
    exit 1
fi

_get() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }

APP_ID="$(_get FEISHU_APP_ID)"
ALLOWED="$(_get ALLOWED_OPEN_IDS)"
SESS="$HOME/.feishu-claude/$APP_ID/sessions.json"

if [ ! -f "$SESS" ]; then
    echo "❌ 找不到 session 存储: $SESS（这个 bot 可能还没在飞书里聊过）" >&2
    exit 1
fi

# 优先取白名单里第一个 open_id 的 session（避免历史遗留的其它用户数据干扰），
# 没配白名单就取第一个有 session_id 的私聊。
OUT="$(ALLOWED="$ALLOWED" python3 - "$SESS" <<'PY'
import json, os, sys

data = json.load(open(sys.argv[1]))
allowed = [x.strip() for x in os.environ.get("ALLOWED", "").split(",") if x.strip()]

candidates = allowed if allowed else list(data.keys())
for uid in candidates:
    cur = data.get(uid, {}).get("private", {}).get("current", {})
    sid = cur.get("session_id")
    if sid:
        print(sid, cur.get("cwd", ""))
        break
PY
)"
read -r SID CWD <<< "$OUT"

if [ -z "${SID:-}" ]; then
    echo "❌ 该 bot 当前没有活跃 session（私聊里还没聊出一条 session，先在飞书发条消息）" >&2
    exit 1
fi

if [ -z "${CWD:-}" ] || [ ! -d "$CWD" ]; then
    echo "⚠️  记录的工作目录不存在或为空: '$CWD'，仍尝试 resume（不 cd）" >&2
else
    cd "$CWD"
fi

echo "🔗 接上 $BOT 的会话: $SID" >&2
echo "📁 工作目录: $(pwd)" >&2
exec claude --resume "$SID"
