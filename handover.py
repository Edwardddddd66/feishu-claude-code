#!/usr/bin/env python3
"""
CLI → 飞书 Bot 会话移交工具。

用法:
  python3 handover.py "对话中的独特文本"

通过内容指纹在所有 ~/.claude/projects/ 下的 .jsonl 中搜索，
匹配到的文件就是当前会话，读出其真实 cwd，按 cwd 自动匹配应该通知
哪个 bot（多 bot 场景下每个 bot 是独立飞书应用 + 独立回调端口），
然后调用对应 bot 的 handover 端点完成移交。
"""

import glob
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 9981  # 未识别出对应 bot 时的兜底端口


def _find_session(fingerprint: str) -> tuple[str, str] | None:
    """在所有项目目录的 .jsonl 中搜索指纹文本。返回 (session_id, cwd) 或 None"""
    try:
        result = subprocess.run(
            ["grep", "-rl", "--include=*.jsonl", fingerprint, CLAUDE_PROJECTS_DIR],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return None

    matches = [l.strip() for l in result.stdout.strip().splitlines() if l.strip().endswith(".jsonl")]
    if not matches:
        return None

    if len(matches) > 1:
        matches.sort(key=lambda f: os.path.getmtime(f), reverse=True)

    best = matches[0]
    session_id = os.path.basename(best).replace(".jsonl", "")
    cwd = _read_cwd(best)
    if not cwd:
        # 兜底：目录名反推（不精确，路径里的 _ . 空格等都会被还原成 /，
        # 只有找不到真实 cwd 字段时才用）
        project_name = os.path.basename(os.path.dirname(best))
        cwd = project_name.replace("-", "/")
    return session_id, cwd


def _read_cwd(fpath: str) -> str:
    """从 .jsonl 里读出真实记录的 cwd 字段（比从目录名反推准确，
    目录名里 / _ 空格等都会被 Claude Code 统一替换成 -，反推不出原样）。"""
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("cwd"):
                    return d["cwd"]
    except OSError:
        pass
    return ""


def _discover_bots() -> list[tuple[str, int, str]]:
    """扫描项目目录下所有 .env.<bot>，取 DEFAULT_CWD + CALLBACK_PORT。
    返回 [(cwd_prefix, port, bot_name), ...]，用于按 session 的 cwd
    自动判断该通知哪个 bot（每个 bot 是独立飞书应用/独立回调端口）。"""
    bots = []
    for env_path in glob.glob(os.path.join(BOT_DIR, ".env.*")):
        name = os.path.basename(env_path)[len(".env."):]
        if name == "example":
            continue
        cwd = port = None
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DEFAULT_CWD="):
                        cwd = os.path.expanduser(line.split("=", 1)[1].strip())
                    elif line.startswith("CALLBACK_PORT="):
                        port = int(line.split("=", 1)[1].strip())
        except OSError:
            continue
        if cwd:
            bots.append((cwd, port or DEFAULT_PORT, name))
    return bots


def _pick_port(cwd: str, bots: list[tuple[str, int, str]]) -> tuple[int, str]:
    """按 cwd 最长前缀匹配选中对应 bot；匹配不到就退回默认端口。"""
    best = None
    for bot_cwd, port, name in bots:
        bot_cwd = bot_cwd.rstrip("/")
        if cwd == bot_cwd or cwd.startswith(bot_cwd + "/"):
            if best is None or len(bot_cwd) > len(best[0]):
                best = (bot_cwd, port, name)
    if best:
        return best[1], best[2]
    return DEFAULT_PORT, f"未匹配到项目，退回默认端口 {DEFAULT_PORT}"


def main():
    if len(sys.argv) < 2:
        print("Usage: handover.py <fingerprint> [--port PORT]", file=sys.stderr)
        sys.exit(1)

    fingerprint = sys.argv[1]
    override_port = None
    if "--port" in sys.argv:
        override_port = int(sys.argv[sys.argv.index("--port") + 1])

    found = _find_session(fingerprint)
    if not found:
        print("ERROR: 未找到匹配的 session，换一段更独特的文本试试")
        sys.exit(1)

    session_id, cwd = found

    if override_port:
        port, bot_label = override_port, "手动指定"
    else:
        bots = _discover_bots()
        port, bot_label = _pick_port(cwd, bots)
    print(f"→ 目标 bot: {bot_label}（端口 {port}），cwd={cwd}", file=sys.stderr)

    handover_url = f"http://localhost:{port}/handover"
    params = urllib.parse.urlencode({
        "session_id": session_id,
        "cwd": cwd,
        "model": os.environ.get("CLAUDE_MODEL", "claude-opus-4-6"),
    })

    try:
        with urllib.request.urlopen(f"{handover_url}?{params}", timeout=10) as resp:
            result = json.loads(resp.read())
    except ConnectionRefusedError:
        print(f"ERROR: 端口 {port} 上的飞书 Bot 未运行")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if result.get("ok"):
        print(session_id)
    else:
        print(f"ERROR: {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
