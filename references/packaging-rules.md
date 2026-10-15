# 打包与校验规范（细则）

> 这些规则来自真实踩坑，**每条都对应一次失败**。脚本 `scripts/package_handover.sh` / `.ps1` 已把这些检查固化，但要知道它们在防什么。

## R1 归档格式：优先 tar.gz

| 格式 | 结论 |
| --- | --- |
| **`.tar.gz`** | ✅ 默认选择。UTF-8 文件名原生支持、正斜杠路径、Linux/macOS/Windows 10+ 自带 `tar` 都能解 |
| `.zip` | ⚠️ 谨慎。必须同时满足：① 条目名用 `/`；② 非 ASCII 名**置了 UTF-8 标志（general purpose bit 11）** |
| `.7z` / `.rar` | 需要额外工具，不选 |

**为什么 ZIP 会出事**：
- .NET `[System.IO.Compression.ZipFile]::CreateFromDirectory` 在 Windows 上把条目名写成 **`\` 分隔**（ZIP 规范要求 `/`），Linux 解压会把整棵目录**平铺成一堆名字里带反斜杠的文件**；
- 即使改用 bsdtar 生成（路径正确），若中文条目**没有置 bit 11**，Linux `unzip`/多数工具会按 CP437 解码 → 中文名乱码。

**ZIP 自查（若不得不用）**：
```powershell
# 路径分隔符与标志位检查（解析中央目录）
$b = [IO.File]::ReadAllBytes($zip); $p=0; $bad=0; $n=0
while (($i = [Array]::IndexOf($b, [byte]0x50, $p)) -ge 0) {
  if ($i+3 -lt $b.Length -and $b[$i+1] -eq 0x4B -and $b[$i+2] -eq 0x01 -and $b[$i+3] -eq 0x02) {
    $flag = $b[$i+8] + ($b[$i+9] -shl 8); $len = $b[$i+28] + ($b[$i+29] -shl 8)
    $hasNonAscii = $false; for ($k=0; $k -lt $len; $k++) { if ($b[$i+46+$k] -gt 127) { $hasNonAscii = $true; break } }
    if ($hasNonAscii) { $n++; if (-not ($flag -band 0x0800)) { $bad++ } }
  }
  $p = $i + 1
}
"非 ASCII 条目=$n 未置 UTF-8 标志=$bad  → 必须为 0"
```

## R2 校验清单：正斜杠 + 解包后端到端全量比对

```bash
# 生成（正斜杠！Windows 下 $f.FullName 直接拼会写成反斜杠）
find . -type f ! -name 'MANIFEST-SHA256.txt' -print0 | sort -z | xargs -0 sha256sum > MANIFEST-SHA256.txt
# Windows PowerShell 等价：$rel = $f.FullName.Substring($root.Length+1).Replace('\','/')
```

**必须解包后再比对一次**——只生成清单而不验证，等于没验证：
```bash
tmp=$(mktemp -d); tar -xzf pkg.tar.gz -C "$tmp"
(cd "$tmp/<pkg>" && sha256sum -c MANIFEST-SHA256.txt | grep -c ': OK$')   # 应等于条目数
```

## R3 文本文件不得含 NUL

一个 NUL 字节就会让编辑器/AI 的文件读取工具判定"二进制文件"而拒绝编辑。

```bash
# 检查包内所有文本类文件
find <pkg> -type f \( -name '*.md' -o -name '*.txt' -o -name '*.sh' -o -name '*.yml' -o -name '*.json' \) -print0 |
  while IFS= read -r -d '' f; do if grep -qP '\x00' "$f" 2>/dev/null; then echo "NUL: $f"; fi; done
```

**来源**：在 PowerShell 双引号字符串里写 `` `0 `` 会产生 NUL；`` `01 `` 会被解析成 "NUL + 1"，静默吃掉一个字符。**改文本一律用 editor 工具，不要在 shell 里拼字符串。**

## R4 包内名与清单必须同步
改过任何文件（哪怕只加一行）→ **重新生成清单 → 重新打包 → 重新校验**。三步少一步就会出现"清单与内容不符"。

## R4a 清单必须是 LF 换行（Windows 上最隐蔽的坑）

Windows PowerShell 的 `[IO.File]::WriteAllLines()` 写 **CRLF**。Linux 上 `sha256sum -c` 会把行尾的 `\r` 当作**文件名的最后一个字符** → 每条都报
`No such file or directory` + `FAILED open or read`，接手方会以为整个包损坏。

**正确写法**（显式 LF）：
```powershell
$nl = [string][char]10
[IO.File]::WriteAllText($manifest, ([string]::Join($nl, $lines) + $nl), (New-Object System.Text.UTF8Encoding($false)))
if ([IO.File]::ReadAllBytes($manifest) -contains 13) { throw '清单含 CR' }
```
**校验方式**：不要只用 PowerShell 比对（它会把 `\r` 当空白吃掉，掩盖问题），**必须在 Linux/Git Bash 上真跑一次 `sha256sum -c`**。

## R4b 校验脚本自身的两个坑（实测踩过）

**① 不要用 `grep $'\x00'` 查 NUL**：bash 无法把 NUL 放进参数，`$'\x00'` 会退化成**空模式**，于是匹配所有行 → 任何文件都被判为"含 NUL"（假阳性）。正确写法是**比字节数**：

```bash
if [ "$(wc -c < "$f")" -ne "$(tr -d '\000' < "$f" | wc -c)" ]; then echo "NUL: $f"; fi
```

**② 含中文的 `.ps1` 必须带 UTF-8 BOM —— 但更好的做法是让它保持纯 ASCII**：Windows PowerShell 5.1（`powershell.exe`）对无 BOM 的 `.ps1` 按 **ANSI/GBK** 解析 → 中文变乱码、甚至吞掉引号导致解析失败。PowerShell 7（`pwsh`）无此问题，所以**只在 5.1 上才暴露**。

- **推荐**：脚本消息用英文、文件纯 ASCII（本 skill 的 `package_handover.ps1` 即如此，校验标准：非 ASCII 字节数为 0）。原因是 **write/edit 类工具会剥掉 BOM**，而 `edit` 一次就复发——BOM 方案在多人/多工具维护下不稳定。
- **若坚持中文**：加 BOM，并**每次编辑后重加**，且必须用 `powershell.exe` 再跑一遍（不是只用 `pwsh`）。
```powershell
$b = [IO.File]::ReadAllBytes($ps1)
if (-not ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)) {
  [IO.File]::WriteAllBytes($ps1, [byte[]](0xEF,0xBB,0xBF) + $b)
}
```

**③ Git Bash 的 tar 会把 `C:/...` 当远程主机**（`Cannot connect to C: resolve failed`）。防御写法：先 `cd` 到目标目录、只传 basename；或统一用 `cd "$(dirname …)" && pwd` 归一化成 `/c/...`。Windows 自带的 `tar`（bsdtar）没有这个问题。

## R5 空目录与子模块
- 空目录：`tar` 会保留条目，解包后目录在但为空 —— 要在边界表里说明它"本该有内容"。
- 子模块：`git clone` 后子模块目录**是空的**。必须在边界表写明 `git submodule update --init --recursive`。
- 浅克隆：`git rev-parse --is-shallow-repository` 为 true 时，历史只有 depth 条；写明 `git fetch --unshallow`。

## R6 交付前最后一次检查（清单）

- [ ] `MANIFEST-SHA256.txt` 使用 `/`，条目数 = 包内文件数 − 1
- [ ] 解包后全量校验 `FAIL=0`
- [ ] 包内文本文件 NUL 检查通过
- [ ] 归档为 tar.gz（或已按 R1 验证 ZIP）
- [ ] 归档 SHA256 已记录并写进回复
- [ ] 边界表与包内实际目录一致
- [ ] 启动指令无 `<占位符>` 残留
