# 一键启动（Windows PowerShell）：建 venv -> 装依赖 -> 构建前端(若有 Node) -> 启动后端
# 用法：  ./start.ps1            # 默认 8000 端口
#         ./start.ps1 --port 9000
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1) 虚拟环境
if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] 创建虚拟环境 .venv ..." -ForegroundColor Cyan
    python -m venv .venv
}
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# 2) 后端依赖
Write-Host "[2/4] 安装后端依赖 ..." -ForegroundColor Cyan
& $py -m pip install -q -r requirements.txt

# 3) 构建前端（有 npm 才构建；构建失败/无 Node 都回退到已提交的 fe-main/dist，不影响启动）
if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path "fe-main")) {
    Write-Host "[3/4] 构建前端 fe-main ..." -ForegroundColor Cyan
    Push-Location fe-main
    try {
        if (-not (Test-Path "node_modules")) { npm install }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build 退出码 $LASTEXITCODE" }
    } catch {
        Write-Host "前端构建失败（$_），改用已提交的 fe-main/dist" -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[3/4] 未检测到 npm，使用已提交的 fe-main/dist" -ForegroundColor Yellow
}

# 4) 启动后端（同源托管前端）
Write-Host "[4/4] 启动服务，打开 http://127.0.0.1:8000/ ..." -ForegroundColor Green
& $py run.py @args
