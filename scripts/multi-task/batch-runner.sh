#!/bin/bash
# MD.Piece Batch Runner
# 使用 Claude Code 非互動模式 (-p) 批次並行處理任務

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
RESULTS_DIR="${REPO_ROOT}/output/batch-results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

usage() {
    echo "MD.Piece Batch Runner"
    echo ""
    echo "用法："
    echo "  $0 analyze                  並行分析所有後端模組"
    echo "  $0 review                   並行程式碼審查"
    echo "  $0 test-gen                 並行生成測試"
    echo "  $0 migrate <from> <to>      批次遷移檔案"
    echo "  $0 custom <tasks-file>      從檔案讀取自訂任務並行執行"
    echo ""
    echo "結果輸出到: ${RESULTS_DIR}/"
}

setup() {
    mkdir -p "${RESULTS_DIR}/${TIMESTAMP}"
}

# 並行分析所有後端路由模組
analyze_modules() {
    setup
    echo "開始並行分析後端模組..."
    echo ""

    local pids=()
    for file in "${REPO_ROOT}"/backend/routers/*.py; do
        local name=$(basename "$file" .py)
        echo "  分析中: ${name}"
        claude -p "分析 ${file} 的程式碼品質，包含：1) 錯誤處理完整性 2) API 設計是否符合 RESTful 3) 安全性檢查。以繁體中文回覆，簡潔扼要。" \
            --output-format text \
            > "${RESULTS_DIR}/${TIMESTAMP}/analyze_${name}.txt" 2>&1 &
        pids+=($!)
    done

    echo ""
    echo "等待所有分析完成（共 ${#pids[@]} 個任務）..."
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    echo "完成！結果在: ${RESULTS_DIR}/${TIMESTAMP}/"
    ls -la "${RESULTS_DIR}/${TIMESTAMP}/"
}

# 並行程式碼審查
review_code() {
    setup
    echo "開始並行程式碼審查..."
    echo ""

    # 安全性審查
    claude -p "審查 ${REPO_ROOT}/backend/ 目錄下所有 Python 檔案的安全性問題，包含 SQL injection、認證繞過、敏感資料洩漏。以繁體中文回覆。" \
        --output-format text \
        > "${RESULTS_DIR}/${TIMESTAMP}/review_security.txt" 2>&1 &
    local pid1=$!

    # 效能審查
    claude -p "審查 ${REPO_ROOT}/backend/ 目錄下所有 Python 檔案的效能問題，包含 N+1 查詢、不必要的迴圈、記憶體洩漏。以繁體中文回覆。" \
        --output-format text \
        > "${RESULTS_DIR}/${TIMESTAMP}/review_performance.txt" 2>&1 &
    local pid2=$!

    # 前端審查
    claude -p "審查 ${REPO_ROOT}/frontend/ 目錄下所有 JS 檔案的程式碼品質，包含效能、可維護性、PWA 最佳實踐。以繁體中文回覆。" \
        --output-format text \
        > "${RESULTS_DIR}/${TIMESTAMP}/review_frontend.txt" 2>&1 &
    local pid3=$!

    echo "等待所有審查完成..."
    wait "$pid1" "$pid2" "$pid3" 2>/dev/null || true

    echo "完成！結果在: ${RESULTS_DIR}/${TIMESTAMP}/"
    ls -la "${RESULTS_DIR}/${TIMESTAMP}/"
}

# 並行生成測試
generate_tests() {
    setup
    echo "開始並行生成測試..."
    echo ""

    local pids=()
    for file in "${REPO_ROOT}"/backend/routers/*.py; do
        local name=$(basename "$file" .py)
        echo "  生成測試: ${name}"
        claude -p "為 ${file} 生成 pytest 單元測試，涵蓋所有 API 端點的成功和失敗情境。只輸出 Python 程式碼。" \
            --output-format text \
            > "${RESULTS_DIR}/${TIMESTAMP}/test_${name}.py" 2>&1 &
        pids+=($!)
    done

    echo ""
    echo "等待所有測試生成完成..."
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    echo "完成！結果在: ${RESULTS_DIR}/${TIMESTAMP}/"
    ls -la "${RESULTS_DIR}/${TIMESTAMP}/"
}

# 從檔案讀取自訂任務並行執行
run_custom_tasks() {
    local tasks_file="$1"
    if [ ! -f "$tasks_file" ]; then
        echo "錯誤：任務檔案 '${tasks_file}' 不存在"
        exit 1
    fi

    setup
    echo "從 ${tasks_file} 讀取任務..."
    echo ""

    local i=0
    local pids=()
    while IFS= read -r task; do
        [ -z "$task" ] && continue
        [[ "$task" == \#* ]] && continue
        i=$((i + 1))
        echo "  任務 ${i}: ${task:0:60}..."
        claude -p "$task" \
            --output-format text \
            > "${RESULTS_DIR}/${TIMESTAMP}/task_${i}.txt" 2>&1 &
        pids+=($!)
    done < "$tasks_file"

    echo ""
    echo "等待所有任務完成（共 ${#pids[@]} 個）..."
    for pid in "${pids[@]}"; do
        wait "$pid" 2>/dev/null || true
    done

    echo "完成！結果在: ${RESULTS_DIR}/${TIMESTAMP}/"
    ls -la "${RESULTS_DIR}/${TIMESTAMP}/"
}

case "${1:-}" in
    analyze)
        analyze_modules
        ;;
    review)
        review_code
        ;;
    test-gen)
        generate_tests
        ;;
    custom)
        [ -z "${2:-}" ] && { echo "錯誤：請提供任務檔案路徑"; usage; exit 1; }
        run_custom_tasks "$2"
        ;;
    *)
        usage
        ;;
esac
