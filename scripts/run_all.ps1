<#
文件：scripts/run_all.ps1
作用：执行一键全流程检查（编译检查 + 可选测试）。
调用方式：
- `powershell -File scripts/run_all.ps1`
- `powershell -File scripts/run_all.ps1 -SkipTests`
调用来源：开发阶段的批量自检脚本。
#>

param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonCmd = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

Push-Location $ProjectRoot
try {
    Write-Host "[脚本] 开始执行项目全流程检查..."

    # 仅检查当前工程实际使用的代码目录与入口，避免误引用已移除文件。
    & $PythonCmd -m compileall train.py predict.py project_config.py wsgi.py inference_pipeline web_dashboard data_preprocessing evaluation scripts tests
    if ($LASTEXITCODE -ne 0) { throw "编译检查失败" }

    if (-not $SkipTests) {
        Write-Host "[脚本] 开始执行测试..."
        & $PythonCmd -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw "测试失败" }
    }

    Write-Host "[脚本] 全流程检查完成。"
}
finally {
    Pop-Location
}
