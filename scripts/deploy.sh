#!/bin/bash
# 部署腳本
echo "Deploying MD.Piece..."

uvicorn backend.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --workers "${WORKERS:-1}"
