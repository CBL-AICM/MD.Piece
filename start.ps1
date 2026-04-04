# MD.Piece 啟動腳本
# 啟動後端 + Cloudflare Tunnel，讓 mdpiece.life 對外服務

Set-Location $PSScriptRoot

Write-Host "▶ 啟動 MD.Piece 後端 (port 8000)..." -ForegroundColor Cyan
$backend = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000" `
    -PassThru -NoNewWindow

Start-Sleep -Seconds 3

Write-Host "▶ 啟動 Cloudflare Tunnel (mdpiece.life)..." -ForegroundColor Cyan
$tunnel = Start-Process -FilePath "C:\Program Files (x86)\cloudflared\cloudflared.exe" `
    -ArgumentList "tunnel", "run", "mdpiece" `
    -PassThru -NoNewWindow

Write-Host ""
Write-Host "✅ MD.Piece 已啟動！" -ForegroundColor Green
Write-Host "   本機：http://localhost:8000" -ForegroundColor White
Write-Host "   公開：https://mdpiece.life" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 停止所有服務..." -ForegroundColor Yellow

try {
    Wait-Process -Id $backend.Id
} finally {
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
    Write-Host "已停止所有服務。" -ForegroundColor Red
}
