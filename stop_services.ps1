# Stop all services script
# Usage: .\stop_services.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Stopping All Services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop backend service (port 8000)
Write-Host "[1/3] Stopping backend service (Django, port 8000)..." -ForegroundColor Yellow
$backendPids = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }).OwningProcess | Select-Object -Unique
if ($backendPids) {
    $backendPids | ForEach-Object {
        $procId = $_
        # 过滤掉无效的PID（0或系统进程）
        if ($procId -gt 0) {
            try {
                $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($process) {
                    Stop-Process -Id $procId -Force -ErrorAction Stop
                    Write-Host "  [OK] Backend service stopped (PID: $procId)" -ForegroundColor Green
                }
            } catch {
                Write-Host "  [WARN] Failed to stop process (PID: $procId): $_" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "  [INFO] No service found on port 8000" -ForegroundColor Gray
}
Write-Host ""

# Stop frontend service (port 8888)
Write-Host "[2/3] Stopping frontend service (Vue/Node, port 8888)..." -ForegroundColor Yellow
$frontendPids = (Get-NetTCPConnection -LocalPort 8888 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }).OwningProcess | Select-Object -Unique
if ($frontendPids) {
    $frontendPids | ForEach-Object {
        $procId = $_
        # 过滤掉无效的PID（0或系统进程）
        if ($procId -gt 0) {
            try {
                $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($process) {
                    Stop-Process -Id $procId -Force -ErrorAction Stop
                    Write-Host "  [OK] Frontend service stopped (PID: $procId)" -ForegroundColor Green
                }
            } catch {
                Write-Host "  [WARN] Failed to stop process (PID: $procId): $_" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "  [INFO] No service found on port 8888" -ForegroundColor Gray
}
Write-Host ""

# Stop Celery Worker
Write-Host "[3/3] Stopping Celery Worker..." -ForegroundColor Yellow
$celeryProcesses = Get-Process -Name celery -ErrorAction SilentlyContinue
if ($celeryProcesses) {
    $celeryProcesses | ForEach-Object {
        Stop-Process -Id $_.Id -Force
        Write-Host "  [OK] Celery process stopped (PID: $($_.Id))" -ForegroundColor Green
    }
} else {
    Write-Host "  [INFO] No Celery process found" -ForegroundColor Gray
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   All services stopped" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
