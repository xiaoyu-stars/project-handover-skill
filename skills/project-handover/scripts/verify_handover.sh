#!/usr/bin/env bash
# -----------------------------------------------------------------------------------------------------------
# verify_handover.sh — 接收方开局自检（交接包拿到手后第一件事）
#
# 用法:
#   bash verify_handover.sh <归档.tar.gz> [--git-root <src-dir>] [--branch <base>..<branch>] [--expect-commits N] [--bundle <file>]
#
# 做这些检查（任一失败即非 0 退出）:
#   1) 归档可解、根目录唯一
#   2) SHA256 全量校验（MANIFEST-SHA256.txt）
#   3) 文本文件 NUL 检查
#   4) 可选：git 副本的分支/提交数/工作区干净
#   5) 可选：git bundle 可验证
# -----------------------------------------------------------------------------------------------------------
set -euo pipefail

archive="${1:?用法: $0 <归档.tar.gz> [--git-root <dir>] [--branch a..b] [--expect-commits N] [--bundle <file>]}"
shift || true
git_root=""; branch_range=""; expect=""; bundle=""
while [ $# -gt 0 ]; do
  case "$1" in
    --git-root) git_root="$2"; shift 2 ;;
    --branch)   branch_range="$2"; shift 2 ;;
    --expect-commits) expect="$2"; shift 2 ;;
    --bundle)   bundle="$2"; shift 2 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

[ -f "$archive" ] || { echo "[FAIL] 归档不存在: $archive" >&2; exit 1; }
# 归一化：切到归档所在目录只传 basename。Git Bash 的 tar 会把 "C:/x" 当成远程主机 host:path
# （"Cannot connect to C: resolve failed"），切目录后即可规避；Linux/macOS 下无副作用。
archive_dir="$(cd "$(dirname "$archive")" && pwd)"
archive="$(basename "$archive")"
cd "$archive_dir"
echo "归档: $archive_dir/$archive"
echo "SHA256: $(sha256sum "$archive" | awk '{print $1}')"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

echo "== [1/4] 解包"
if ! tar -xzf "$archive" -C "$tmp"; then echo "[FAIL] 解包失败（是否不是 tar.gz？）" >&2; exit 1; fi
roots=$(find "$tmp" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')
[ "$roots" -eq 1 ] || { echo "[FAIL] 归档根目录数为 $roots（期望 1）" >&2; exit 1; }
root="$(find "$tmp" -maxdepth 1 -mindepth 1 -type d)"
echo "   根目录: $(basename "$root")  文件数: $(find "$root" -type f | wc -l | tr -d ' ')"

echo "== [2/4] SHA256 全量校验"
[ -f "$root/MANIFEST-SHA256.txt" ] || { echo "[FAIL] 缺 MANIFEST-SHA256.txt" >&2; exit 1; }
set +e
( cd "$root" && sha256sum -c MANIFEST-SHA256.txt > "$tmp/v.log" 2>&1 )
rc=$?
set -e
ok=$(grep -c ': OK$' "$tmp/v.log" || true)
total=$(wc -l < "$root/MANIFEST-SHA256.txt" | tr -d ' ')
if [ "$rc" -ne 0 ]; then
  echo "[FAIL] 校验未通过（OK=$ok/$total）：" >&2
  grep -v ': OK$' "$tmp/v.log" | head -n 20 >&2
  exit 1
fi
echo "   OK：$ok/$total 全部通过"

echo "== [3/4] 文本 NUL 检查"
nul=0
while IFS= read -r -d '' f; do
  case "$f" in
    *.md|*.txt|*.sh|*.ps1|*.py|*.yml|*.yaml|*.json|*.toml|*.ini|*.cfg)
      # 不能用 grep $'\x00'：bash 无法把 NUL 放进参数，会退化成空模式匹配所有行（假阳性）
      if [ "$(wc -c < "$f")" -ne "$(tr -d '\000' < "$f" | wc -c)" ]; then
        echo "   [FAIL] NUL: ${f#$root/}"; nul=$((nul+1))
      fi ;;
  esac
done < <(find "$root" -type f -print0)
[ "$nul" -eq 0 ] || { echo "[FAIL] $nul 个文件含 NUL" >&2; exit 1; }
echo "   OK：无 NUL"

echo "== [4/4] 信息文档格式校验（HANDOVER.md）"
if [ -f "$root/HANDOVER.md" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 "$(cd "$(dirname "$0")" && pwd)/check_info_doc.py" "$root/HANDOVER.md" || {
      echo "[FAIL] HANDOVER.md 不符合 v1 固定格式（见 references/info-doc-format.md）" >&2; exit 1; }
  else
    echo "   [WARN] 无 python3，跳过格式校验；请手动跑 check_info_doc.py"
  fi
else
  echo "[FAIL] 归档内缺 HANDOVER.md —— 交接包必须包含固定格式的项目信息文档" >&2
  exit 1
fi

if [ -n "$git_root" ]; then
  echo "== 附加：git 副本检查"
  if [ -n "$branch_range" ]; then
    n=$(git -C "$git_root" log --oneline "$branch_range" | wc -l | tr -d ' ')
    echo "   $branch_range 提交数: $n"
    [ -z "$expect" ] || { [ "$n" -eq "$expect" ] || { echo "[FAIL] 期望 $expect 个提交，实际 $n" >&2; exit 1; }; }
  fi
  dirty=$(git -C "$git_root" status --porcelain | wc -l | tr -d ' ')
  echo "   未提交改动: $dirty（期望 0）"
  [ "$dirty" -eq 0 ] || echo "   [WARN] 工作区不干净"
fi

if [ -n "$bundle" ]; then
  echo "== 附加：bundle 校验"
  git bundle verify "$bundle" >/dev/null 2>&1 && echo "   OK：bundle 可验证" || { echo "[FAIL] bundle verify 失败" >&2; exit 1; }
fi

echo
echo "全部自检通过。下一步：按 01-交接流程与启动指令.md 的 [按序执行] 开工。"
