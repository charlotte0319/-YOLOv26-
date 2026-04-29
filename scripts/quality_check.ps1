<#
文件：scripts/quality_check.ps1
作用：执行本地质量检查（静态检查 + 单元测试）。
调用方式：在仓库根目录运行 `powershell -File scripts/quality_check.ps1`。
调用来源：开发者本地自检，或被 `scripts/run_all.ps1` 间接调用。
#>

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonCmd = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Write-Host "[质量] 运行 Ruff 检查..."
& $PythonCmd -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "Ruff 检查未通过" }

Write-Host "[质量] 运行 Pytest..."
& $PythonCmd -m pytest
if ($LASTEXITCODE -ne 0) { throw "Pytest 未通过" }

Write-Host "[质量] 全部通过。"
