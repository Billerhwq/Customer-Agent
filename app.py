"""CLI 入口。

用法：
    python app.py "Can you make custom stainless steel brackets based on my drawing?"
    python app.py --session demo-001 --country Germany "What is the MOQ for CNC aluminum parts?"
    echo '...' | python app.py            # 从 stdin 读取（可选）

输出：合法 JSON（UTF-8）。
"""
from __future__ import annotations

import argparse
import json
import sys

from src.agent import Agent
from src.errors import AgentError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="外贸独立站客服 Agent (CLI)")
    parser.add_argument("message", nargs="*", help="访客消息")
    parser.add_argument("--session", default="cli-session", help="会话 ID（用于多轮线索累积）")
    parser.add_argument("--country", default="", help="访客国家")
    parser.add_argument("--email", default="", help="访客邮箱")
    args = parser.parse_args(argv)

    message = " ".join(args.message).strip()
    if not message and not sys.stdin.isatty():
        message = sys.stdin.read().strip()

    visitor = {"country": args.country or None, "email": args.email or None}

    agent = Agent()
    try:
        result = agent.chat(message, session_id=args.session, visitor=visitor)
    except AgentError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
