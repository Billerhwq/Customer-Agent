"""一键启动脚本：python run.py

等价于 `uvicorn src.server:app`，并默认开启 8000 端口。
clone 仓库后：
    pip install -r requirements.txt
    python run.py
然后浏览器打开 http://127.0.0.1:8000/
"""
from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="启动外贸客服 Agent 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="开发热重载")
    args = parser.parse_args()
    uvicorn.run("src.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
