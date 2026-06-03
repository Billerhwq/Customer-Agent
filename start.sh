#!/usr/bin/env bash
# 一键启动（macOS / Linux）：建 venv -> 装依赖 -> 构建前端(若有 Node) -> 启动后端
# 用法：  ./start.sh            # 默认 8000 端口
#         ./start.sh --port 9000
set -e
cd "$(dirname "$0")"

# 1) 虚拟环境
PY=python3; command -v python3 >/dev/null 2>&1 || PY=python
if [ ! -d .venv ]; then
  echo "[1/4] 创建虚拟环境 .venv ..."
  "$PY" -m venv .venv
fi
# 兼容 Linux/mac(bin) 与 Git-Bash(Scripts)
VPY=.venv/bin/python
[ -x "$VPY" ] || VPY=.venv/Scripts/python

# 2) 后端依赖
echo "[2/4] 安装后端依赖 ..."
"$VPY" -m pip install -q -r requirements.txt

# 3) 构建前端（有 npm 才构建；构建失败/无 Node 都回退到已提交的 fe-main/dist，不影响启动）
if command -v npm >/dev/null 2>&1 && [ -d fe-main ]; then
  echo "[3/4] 构建前端 fe-main ..."
  ( cd fe-main && { [ -d node_modules ] || npm install; } && npm run build ) \
    || echo "前端构建失败，改用已提交的 fe-main/dist"
else
  echo "[3/4] 未检测到 npm，使用已提交的 fe-main/dist"
fi

# 4) 启动后端（同源托管前端）
echo "[4/4] 启动服务，打开 http://127.0.0.1:8000/ ..."
exec "$VPY" run.py "$@"
