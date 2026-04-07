#!/bin/bash
# MD.Piece Worktree Manager
# 快速建立/管理多個 Claude Code 工作環境

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_DIR="${REPO_ROOT}/../md-piece-worktrees"

usage() {
    echo "MD.Piece Worktree Manager"
    echo ""
    echo "用法："
    echo "  $0 create <name> [base-branch]   建立新 worktree（預設基於 main）"
    echo "  $0 list                           列出所有 worktrees"
    echo "  $0 remove <name>                  移除 worktree"
    echo "  $0 launch <name>                  在 worktree 中啟動 Claude Code"
    echo "  $0 launch-all                     在所有 worktrees 中啟動 Claude Code"
    echo ""
    echo "範例："
    echo "  $0 create auth-feature            建立 auth-feature worktree"
    echo "  $0 create bugfix-123 main         基於 main 建立 bugfix worktree"
    echo "  $0 launch auth-feature            在 auth-feature 中啟動 Claude Code"
}

create_worktree() {
    local name="$1"
    local base="${2:-main}"
    local branch="claude/${name}"
    local path="${WORKTREE_DIR}/${name}"

    mkdir -p "${WORKTREE_DIR}"

    echo "建立 worktree: ${name}"
    echo "  分支: ${branch}"
    echo "  路徑: ${path}"
    echo "  基於: ${base}"

    git worktree add -b "${branch}" "${path}" "${base}"

    echo ""
    echo "Worktree 已建立！"
    echo "進入方式: cd ${path}"
    echo "啟動 Claude Code: $0 launch ${name}"
}

list_worktrees() {
    echo "目前的 worktrees："
    echo ""
    git worktree list
}

remove_worktree() {
    local name="$1"
    local path="${WORKTREE_DIR}/${name}"

    echo "移除 worktree: ${name} (${path})"
    git worktree remove "${path}"
    echo "已移除。"
}

launch_worktree() {
    local name="$1"
    local path="${WORKTREE_DIR}/${name}"

    if [ ! -d "${path}" ]; then
        echo "錯誤：worktree '${name}' 不存在。先用 create 建立。"
        exit 1
    fi

    echo "在 ${path} 啟動 Claude Code..."
    cd "${path}" && claude
}

launch_all() {
    echo "在所有 worktrees 中啟動 Claude Code..."
    echo ""
    git worktree list --porcelain | grep "^worktree " | while read -r _ path; do
        if [ "${path}" != "${REPO_ROOT}" ]; then
            echo "啟動: ${path}"
            (cd "${path}" && claude &)
        fi
    done
    echo ""
    echo "所有 worktree 的 Claude Code 已在背景啟動。"
}

case "${1:-}" in
    create)
        [ -z "${2:-}" ] && { echo "錯誤：請提供 worktree 名稱"; usage; exit 1; }
        create_worktree "$2" "${3:-main}"
        ;;
    list)
        list_worktrees
        ;;
    remove)
        [ -z "${2:-}" ] && { echo "錯誤：請提供 worktree 名稱"; usage; exit 1; }
        remove_worktree "$2"
        ;;
    launch)
        [ -z "${2:-}" ] && { echo "錯誤：請提供 worktree 名稱"; usage; exit 1; }
        launch_worktree "$2"
        ;;
    launch-all)
        launch_all
        ;;
    *)
        usage
        ;;
esac
