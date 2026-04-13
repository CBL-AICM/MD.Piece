@echo off
chcp 65001 >nul
title MD.Piece 醫師端啟動器

echo ============================================
echo   MD.Piece 醫師端（Vite + React）
echo ============================================
echo.

start "MD.Piece Backend" cmd /k "cd /d %~dp0 && uvicorn backend.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul

start "MD.Piece Doctor Frontend" cmd /k "cd /d %~dp0frontend-doctor && npm run dev"
timeout /t 4 /nobreak >nul

start "" "http://localhost:3001"

echo 後端：http://localhost:8000
echo 前端：http://localhost:3001
echo.
echo 首次使用請先在 frontend-doctor/ 執行 npm install
echo 按任意鍵關閉此視窗（後端與前端會繼續執行）
pause >nul
