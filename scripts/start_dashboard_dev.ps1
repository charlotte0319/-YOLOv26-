<#
文件：scripts/start_dashboard_dev.ps1
作用：以开发模式启动本地 Web 看板，直接运行 Flask 入口。
调用方式：在仓库根目录运行 `powershell -File scripts/start_dashboard_dev.ps1`。
调用来源：开发者本地调试看板页面、接口和前端资源时使用。
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonCmd = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "[启动] 正在启动开发模式看板..."
& $PythonCmd web_dashboard/app.py
