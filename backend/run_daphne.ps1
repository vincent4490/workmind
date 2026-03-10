# 启动 daphne ASGI 服务（常驻）
# 用法: .\run_daphne.ps1  或  .\run_daphne.ps1 -Port 8009
param([int]$Port = 8009)

# 脚本位于 backend\run_daphne.ps1，工作目录设为 backend
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "未找到 venv: $venvPython" -ForegroundColor Red
    exit 1
}

Write-Host "Starting daphne on 127.0.0.1:$Port ..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Gray
& $venvPython -m daphne -b 127.0.0.1 -p $Port backend.asgi:application 2>&1 | ForEach-Object { Write-Host $_ }
