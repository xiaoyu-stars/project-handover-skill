#!/usr/bin/env bash
# -----------------------------------------------------------------------------------------------------------
# package_handover.sh — 交接包打包 + 端到端校验（POSIX，Linux/macOS/Git-Bash/WSL 可用）
#
# 用法:
#   bash package_handover.sh <包目录> <输出目录> <归档名(不含扩展名)>
# 例:
#   bash package_handover.sh ./my-pkg ./dist my-project-20261016
#
# 做四件事（任一失败即非 0 退出）:
#   1) 重新生成 MANIFEST-SHA256.txt（正斜杠路径，排除自身）
#   2) 扫描文本类文件的 NUL 字节（一个都不能有）
#   3) 打 tar.gz（UTF-8 名 + 正斜杠，跨平台安全）
#   4) 解包后逐文件比对 SHA256（全量，不是抽样）
# -----------------------------------------------------------------------------------------------------------
set -euo pipefail

pkg="${1:?用法: $0 <包目录> <输出目录> <归档名>}"
out="${2:?缺少 <输出目录>}"
name="${3:?缺少 <归档名>}"

pkg="$(cd "$pkg" && pwd)"
mkdir -p "$out"
out="$(cd "$out" && pwd)"
base="$(basename "$pkg")"
archive="$out/${name}.tar.gz"

echo "== [1/4] 生成 MANIFEST-SHA256.txt（正斜杠）"
# shellcheck disable=SC2016
( cd "$pkg" && find . -type f ! -name 'MANIFEST-SHA256.txt' -print0 | sort -z | xargs -0 sha256sum | sed 's|  \./|  |' > MANIFEST-SHA256.txt )
count="$(wc -l < "$pkg/MANIFEST-SHA256.txt" | tr -d ' ')"

if grep -q $'\r' "$pkg/MANIFEST-SHA256.txt"; then
  echo "   [FAIL] 清单含 CR —— 请以 UTF-8/LF 重写" >&2; exit 1
fi
if grep -q '\\' "$pkg/MANIFEST-SHA256.txt"; then
  echo "   [FAIL] 清单含反斜杠路径 —— Linux sha256sum -c 会失败" >&2; exit 1
fi
echo "   OK：$count 条"

echo "== [2/4] 文本文件 NUL 检查"
nul_hits=0
while IFS= read -r -d '' f; do
  case "$f" in
    *.md|*.txt|*.sh|*.ps1|*.py|*.yml|*.yaml|*.json|*.toml|*.ini|*.cfg|*.csv|*.c|*.h|*.cpp|*.hpp|*.inl)
      # 不能用 grep $'\x00'：bash 无法把 NUL 放进参数，会退化成空模式匹配所有行（假阳性）
      if [ "$(wc -c < "$f")" -ne "$(tr -d '\000' < "$f" | wc -c)" ]; then
        echo "   [FAIL] NUL: ${f#$pkg/}"; nul_hits=$((nul_hits+1))
      fi ;;
  esac
done < <(find "$pkg" -type f -print0)
if [ "$nul_hits" -ne 0 ]; then echo "   [FAIL] $nul_hits 个文件含 NUL" >&2; exit 1; fi
echo "   OK：无 NUL"

echo "== [3/4] 打 tar.gz"
rm -f "$archive"
tar -czf "$archive" -C "$(dirname "$pkg")" "$base"
echo "   OK：$archive"

echo "== [4/4] 解包后全量校验"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -xzf "$archive" -C "$tmp"
extracted="$(find "$tmp/$base" -type f | wc -l | tr -d ' ')"
if ! ( cd "$tmp/$base" && sha256sum -c MANIFEST-SHA256.txt > "$tmp/verify.log" 2>&1 ); then
  echo "   [FAIL] 校验未全部通过，失败条目：" >&2
  grep -v ': OK$' "$tmp/verify.log" | head -n 20 >&2
  exit 1
fi
ok="$(grep -c ': OK$' "$tmp/verify.log" || true)"
echo "   OK：解包 $extracted 个文件，SHA256 全部通过（$ok/$count）"

sha="$(sha256sum "$archive" | awk '{print $1}')"
size="$(du -h "$archive" | awk '{print $1}')"
cat <<EOF

================ 交付摘要 ================
归档    : $archive
大小    : $size
条目    : $count 个文件（解包后 $extracted 个）
SHA256  : $sha
校验    : 解包端到端全量通过（FAIL=0）
==========================================
把上面这段（归档路径 + SHA256 + 校验结论）连同启动指令一起发给接收方。
EOF
