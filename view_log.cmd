@echo off
chcp 65001 >nul
setlocal

echo 正在跟踪今日日志（按 Ctrl+C 退出）...
echo.
powershell -NoProfile -Command "$d = Get-Date -Format 'yyyyMMdd'; $p = Join-Path '%~dp0logs' ('ncm_rpc-' + $d + '.log'); if (Test-Path $p) { Write-Host ('===== ' + $p + ' =====') -ForegroundColor Cyan; Get-Content $p -Tail 60 -Wait -Encoding UTF8 } else { Write-Host ('今日日志不存在: ' + $p) -ForegroundColor Yellow; Write-Host '提示：用 .vbs / pythonw 启动后才会生成日志；用 python.exe 启动时输出直接显示在控制台。' }"
