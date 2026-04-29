<#
文件：scripts/start_dashboard_prod.ps1
作用：以 Waitress 启动本地生产模式 Web 服务。
调用方式：在仓库根目录运行 `powershell -File scripts/start_dashboard_prod.ps1`。
调用来源：单机部署、演示环境或需要更接近生产行为时使用。
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonCmd = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "[启动] 正在启动生产模式看板..."
& $PythonCmd wsgi.py
