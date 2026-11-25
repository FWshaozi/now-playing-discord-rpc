@echo off
chcp 65001 >nul
setlocal

rem 精确匹配「解释器 + 完整脚本路径」，避免误杀编辑器等进程
set "TARGET=%~dp0ncm_rpc.py"

echo 正在查找运行实例：%TARGET%
powershell -NoProfile -Command "$t='%~dp0ncm_rpc.py'; $p = Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'pythonw.exe' -or $_.Name -eq 'python.exe') -and $_.CommandLine -like ('*' + $t + '*') }; if (-not $p) { Write-Host '没有正在运行的实例。' -ForegroundColor Yellow } else { foreach ($x in $p) { Stop-Process -Id $x.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('已停止 PID ' + $x.ProcessId) -ForegroundColor Green } }"

echo.
pause
