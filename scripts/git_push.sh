#!/usr/bin/env bash
# git_push.sh — 把本 skill 推送到 GitHub（token 安全：只在推送瞬间用，绝不写进 .git/config）
#
# 设计原则：
#   - PAT 存在 ~/.dsh/secrets/github_token（git 仓库树之外，chmod 600），永不进 git
#   - remote origin 只存无 token 的干净 HTTPS 地址
#   - 推送时临时拼一个带 token 的 URL 发给 git，推完即弃，不 set-url、不留 config
#   - 当前分支：默认推当前所在分支；可传分支名参数，或传 "all" 推所有本地分支
#
# 用法:
#   bash scripts/git_push.sh            # 推当前分支
#   bash scripts/git_push.sh main       # 推指定分支
#   bash scripts/git_push.sh all        # 推所有本地分支
#
# 退出码: 0 成功 | 1 缺 token | 2 缺 remote | 3 git 推送失败
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

# 1) 读 token（优先环境变量 GITHUB_TOKEN，其次 secrets 文件）
TOKEN="${GITHUB_TOKEN:-}"
if [[ -z "$TOKEN" && -f "$HOME/.dsh/secrets/github_token" ]]; then
  TOKEN="$(tr -d '[:space:]' < "$HOME/.dsh/secrets/github_token")"
fi
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: 未找到 GitHub token。请设 GITHUB_TOKEN 或写入 ~/.dsh/secrets/github_token" >&2
  exit 1
fi

# 2) 读无 token 的 origin URL（clean）
CLEAN_URL="$(git remote get-url origin 2>/dev/null || true)"
if [[ -z "$CLEAN_URL" ]]; then
  echo "ERROR: 仓库未配置 origin remote" >&2
  exit 2
fi
if [[ "$CLEAN_URL" == *'@github.com/'* ]]; then
  # 若 origin 意外带了凭据，剥掉（只保留 https://github.com/<owner>/<repo>.git）
  CLEAN_URL="https://$(printf '%s' "$CLEAN_URL" | sed -E 's#^[a-z]*://[^@/]*@#https://#')"
fi

# 3) 用带 token 的 URL 推送（一次性，不改 config）
AUTH_URL="${CLEAN_URL/#https:\/\//https:\/\/${TOKEN}@}"

BRANCH_ARG="${1:-}"
if [[ "$BRANCH_ARG" == "all" ]]; then
  echo "→ 推所有本地分支到 $CLEAN_URL"
  git push --all "$AUTH_URL"
else
  BRANCH="${BRANCH_ARG:-$(git branch --show-current)}"
  if [[ -z "$BRANCH" ]]; then
    echo "ERROR: 无法确定要推的分支（请传分支名）" >&2
    exit 2
  fi
  echo "→ 推 $BRANCH → $CLEAN_URL"
  # 注意：绝不能对 $AUTH_URL 用 -u（会把带 token 的 URL 写进 branch.<b>.remote 造成泄漏）。
  # 推送到一次性 auth URL，然后用命名的 origin remote 设 upstream，config 里只留干净地址。
  git push "$AUTH_URL" "$BRANCH"
  if ! git config "branch.${BRANCH}.remote" >/dev/null 2>&1; then
    git branch --set-upstream-to="origin/${BRANCH}" "$BRANCH" 2>/dev/null || true
  fi
fi

# 4) 推完同步本地 tracking ref（推送用的是一次性 auth URL，不会更新 refs/remotes/origin/<b>，
#    需用干净的 origin 做个只读 fetch 让 git status 不再误报 ahead）。顺带确认 remote 干净。
if git remote get-url origin | grep -q 'github_pat'; then
  echo "WARN: origin 含 token，正在清理…" >&2
  git remote set-url origin "$CLEAN_URL"
fi
git fetch origin --quiet 2>/dev/null || true
echo "✓ 已推送（token 未写入 .git/config）"