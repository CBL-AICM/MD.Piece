#!/bin/bash
# 資料初始化腳本
# 使用方式：bash scripts/seed.sh [backend_url]
# 預設 backend URL：http://localhost:8000

set -e

API_URL="${1:-http://localhost:8000}"

echo "=== MD.Piece 資料初始化 ==="
echo "Backend URL: $API_URL"
echo ""

# 確認後端是否啟動
echo "[1/2] 確認後端連線..."
if ! curl -sf "$API_URL/" > /dev/null 2>&1; then
    echo "錯誤：無法連線到 $API_URL，請確認後端已啟動"
    exit 1
fi
echo "後端連線正常"

# 初始化預設科別
echo ""
echo "[2/2] 初始化預設科別..."
RESULT=$(curl -sf -X POST "$API_URL/departments/seed" \
    -H "Content-Type: application/json" 2>&1)

if [ $? -eq 0 ]; then
    echo "$RESULT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('message', '完成'))
" 2>/dev/null || echo "$RESULT"
else
    echo "科別初始化失敗（可能已存在）"
fi

echo ""
echo "=== 初始化完成 ==="
