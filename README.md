# project-handover

> **给 AI 的项目交接技能（Skill）：一个功能「交出」，一个功能「接入」。**
> 让下一个 AI（或下一个人）**读一个压缩包就能独立接手**，不再需要你每次手写交接提示词。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 它解决什么问题

长会话/多阶段项目的交接通常靠"再写一段提示词"，结果是：接手方不知道状态、不知道下一步、不知道什么不能做，还会重复踩已经踩过的坑。

这个 skill 把交接变成**可校验的规范**：

- **交出**：把一个项目的全部内容与信息打成一个压缩包，包内项目信息文档**格式固定**（机器可读）；
- **接入**：读一个或多个交接包，**先把所有项目信息读完**再决定接入细节，然后**自动执行**；每个项目落到**独立的命名目录**里，不互相污染。

## 两个功能

### 交出（hand out）

| 规则 | 内容 |
| --- | --- |
| **O1** | **一次只交出一个项目/任务**（要求一次交多个 → 拆成多次） |
| **O2** | 只产出一个压缩包，内含接手所需的全部内容与信息 |
| **O3** | 包内 `HANDOVER.md` **格式固定**：13 个必填 front-matter 键 + 12 个固定章节，`check_info_doc.py` 校验不通过不得交出 |
| **O4** | 打包方式按实际情况决定（5 问决策：能否再生 / 有无网络 / 体积 / 敏感信息 / 是否只存在于会话） |
| **O5** | 未验证、未提交必须显式声明（`verified` / `submitted`） |
| **O6** | 归档用 tar.gz，产出后**解包全量校验** |

产出（固定 6 件）：

```
<slug>-<YYYYMMDD>/
├── HANDOVER.md              # 项目信息文档（固定格式，机器可读）
├── 00-先读我.md             # 人读入口
├── 01-交接流程与启动指令.md  # 交付方式 + 启动指令
├── MANIFEST-SHA256.txt      # LF + 正斜杠
└── …（报告/补丁/脚本/数据/源码副本）
```

### 接入（take over）

| 规则 | 内容 |
| --- | --- |
| **I1** | **先读全部，再决定**：接入 N 个项目就必须读完 N 份 `HANDOVER.md` |
| **I2** | **读完即自动执行 —— 但只限"资源无关"操作**：信息读取与项目整理（列清单、建目录、解包、格式/哈希校验、写索引与计划、读文档与日志） |
| **I9** | **资源相关操作一律先汇报、审核通过后才能执行**：编译构建、跑测试/基准/性能、训练/推理、设备占用、大规模数据处理、需要凭据或外部服务、push/PR/部署、删除覆盖。**未获批不得执行，也不得"先跑一下试试"** |
| **I10** | 判定不确定 → **默认归入需审批**；审批单须写清命令、资源占用、依赖配置、风险与回滚、预期产物；执行不得超出获批范围 |
| **I3** | 只有 4 种情况才停下来问：不可逆操作 / 缺凭据 / 信息冲突 / 格式不合格 |
| **I4** | 多项目抢同一独占资源（卡/机时/锁）→ **必须串行** |
| **I5** | 每步四件套回报：命令 / 日志路径 / 结论 / 下一步 |
| **I6** | 只做信息文档写明的事 |
| **I7** | **每个项目建独立目录并命名**：目录名 = `project_id`；冲突默认追加日期新建，**不覆盖** |
| **I8** | 工作根维护 `INDEX.md` + `registry.json`；每个项目目录内 `ACCESS.md`（接入记录与执行日志） |

### 接入后的执行门禁（Resource Gate）

接入**不等于**立刻开工。按"是否依赖机器资源配置"分两阶段：

| 阶段 | 内容 | 例子 | 审批 |
| --- | --- | --- | --- |
| **A · 自动** | 信息读取 + 项目整理 | 列清单、建 `project_id/` 目录、解包、格式/哈希校验、写 INDEX/registry/ACCESS、出接入计划、静态读代码 | **不需要** |
| **B · 待审** | 具体执行/计算/分析 | 编译构建、跑测试/基准/性能、训练/推理、设备占用、大规模数据处理、需要凭据或外部服务、push/PR/部署、删除覆盖 | **必须先汇报，审核通过后执行** |

判据三问（任一"是"→ 阶段 B）：① 需要特定机器能力（NPU/GPU/核数/内存/驱动/编译器/许可证/网络）？② 消耗不可忽略资源或有副作用？③ 换台配置不同的机器结论会变？
**不确定 → 归入阶段 B。** 完整分类表与审批单模板见 [`references/approval-gate.md`](references/approval-gate.md)。

审批单追加到 `<工作根>/APPROVALS.md`，并在项目 `ACCESS.md` 记一行 `pending`；`HANDOVER.md` 可用可选键 `gated_actions` 预声明哪些操作需要审批。

工作根布局（`prepare_projects.py` 生成）：

```
<工作根>/
├── INDEX.md              # 人读：项目 → 目录/优先级/截止/依赖/资源
├── registry.json         # 机器读：含来源归档与 SHA256
├── _archives/            # 原始归档留存
└── <project_id>/         # 每个项目一个独立目录
    ├── HANDOVER.md
    ├── ACCESS.md         # 来源 + SHA256 + 已读确认 + 接入细节 + 执行日志
    └── …
```

## 安装

### A. 作为 DSH 插件（推荐）

本仓库就是一个 DeepSeek Harness bundle：`package.json` 声明 `dsh.bundle.patch`，`dsh/index.mjs` 把 `skills/` 挂到 harness 的 skills 服务。

```bash
# 1) 装到 profile 里（npm 名 / git URL / 本地路径三选一）
cd ~/.dsh/profiles/<你的 profile>
pnpm add github:xiaoyu-stars/project-handover-skill      # 或 pnpm add /path/to/clone

# 2) 在 profile 的 package.json 里把包名加入 bundles
#    "dsh": { "profile": { "bundles": [ ..., "dsh-project-handover" ] } }

# 3) 重启 DSH
```

> 插件形式的好处：随 profile 一起版本化、可通过 `pnpm` 升级、与内置技能并列加载；
> 同名时**用户/项目技能仍然优先**（skills 提供者的排序规则）。

### B. 直接放技能目录（不走插件，最省事）

```bash
git clone --depth 1 https://github.com/xiaoyu-stars/project-handover-skill.git /tmp/ph
cp -r /tmp/ph/skills/project-handover ~/.dsh/skills/          # DSH
cp -r /tmp/ph/skills/project-handover ~/.claude/skills/       # Claude Code 等兼容目录
```

### C. 只用脚本（任何环境）

```bash
git clone --depth 1 https://github.com/xiaoyu-stars/project-handover-skill.git
ls /path/to/clone/skills/project-handover/scripts
```

## 使用

| 你说 | 它做 |
| --- | --- |
| 「**交出**这个项目」/「交接一下」 | 走交出流程：定范围 → 写 `HANDOVER.md` → 校验格式 → 打包 → 给出归档 + SHA256 + 启动指令 |
| 「**接入**这几个包」/「接手」/「继续这个项目」 | 走接入流程：列清单 → **建独立目录** → **读完所有信息文档** → 出接入计划 → **自动执行** |

脚本也可单独用：

```bash
# 交出：校验信息文档格式 → 打包并端到端校验
python3 scripts/check_info_doc.py  <pkg>/HANDOVER.md
bash    scripts/package_handover.sh <pkg> <out-dir> <archive-name>      # Linux/macOS/Git-Bash
pwsh -File scripts/package_handover.ps1 -Pkg <pkg> -Out <out-dir> -Name <archive-name>   # Windows

# 接入：多项目清单 → 建独立目录 → 接收方自检
python3 scripts/scan_handovers.py pkg1.tar.gz pkg2.tar.gz
python3 scripts/prepare_projects.py --root ~/handover pkg1.tar.gz pkg2.tar.gz
bash    scripts/verify_handover.sh pkg1.tar.gz
```

## `HANDOVER.md` 固定格式（v1）

13 个必填键：

```yaml
---
handover_version: 1
project_id: demo-project        # 唯一标识，接入方据此建目录
project_name: 示例项目
kind: task                      # project|task|experiment|research
status: in_progress             # planning|in_progress|blocked|stage_done|done
created: 2026-10-16T01:35+08:00
deadline: 2026-10-18T18:00+08:00   # 或 null
priority: P0                    # P0|P1|P2
resources: ["npu-0"]            # 独占资源 → 多项目串行化依据
depends_on: []                  # 依赖的其他 project_id
verified: false                 # 是否已实测/已编译
submitted: false                # 是否已 push/PR/issue
next_action: "编译并跑基线对照"   # 接入后的第一个动作
---
```

12 个固定章节（标题一字不差、顺序不可变）：
目标与验收标准 / 规则与硬约束 / 工作区地图 / 环境与前置 / 结论清单 / 红线 / 已实现但未验证 / 未完成事项 / 合规清单 / 复核方法 / 数据索引 / 交接边界。

详见 [`references/info-doc-format.md`](references/info-doc-format.md)。

## 工具链

| 脚本 | 作用 |
| --- | --- |
| `scripts/check_info_doc.py` | `HANDOVER.md` 格式校验（交出前 / 接入时） |
| `scripts/scan_handovers.py` | 多项目清单 → 比较表 + 资源冲突 + 依赖序 + 建议顺序 |
| `scripts/prepare_projects.py` | 按 `project_id` 建独立目录、解包、留存归档、生成 INDEX/registry/ACCESS |
| `scripts/package_handover.sh` / `.ps1` | 打包 + 解包全量 SHA256 校验（Linux / Windows） |
| `scripts/verify_handover.sh` | 接收方开局自检（含格式校验，缺 `HANDOVER.md` 直接拒绝） |

依赖：`python3`（仅标准库）、`tar`；可选 Git Bash（Windows）或 PowerShell 5.1+。

## 这些规范来自真实踩坑

每个坑都对应一次失败，已固化进脚本与文档：

| 坑 | 后果 | 修法 |
| --- | --- | --- |
| .NET `ZipFile.CreateFromDirectory` 在 Windows 写**反斜杠**且**不置 UTF-8 标志** | Linux 解压乱码/平铺 | 归档优先 tar.gz；ZIP 必须验 bit11 与 `/` |
| `WriteAllLines` 生成 **CRLF** 清单 | Linux `sha256sum -c` 把 `\r` 当文件名 → 全部 FAILED | 强制 LF + CR 检查 |
| 清单用**反斜杠**路径 | Linux 校验直接失败 | 强制 `/` 并校验 |
| `grep $'\x00'` 查 NUL | bash 无法把 NUL 放进参数 → 退化为空模式 → **所有文件误报含 NUL** | 改比字节数 |
| PowerShell 双引号里未转义的 `` `01 `` | 解析成 **NUL 转义**，静默吃掉字符、污染文件 | 改文本用编辑器，不在 shell 拼字符串 |
| 无 BOM 的中文 `.ps1` 在 PS 5.1 下乱码 | 解析失败 | 脚本保持纯 ASCII（或加 BOM 并用 `powershell.exe` 复测） |
| Git Bash 的 `tar` 把 `C:/x` 当远程主机 | `Cannot connect to C: resolve failed` | 先 `cd` 再传 basename |

## 仓库结构

```
.
├── package.json                      # DSH 插件包（dsh.bundle.patch → dsh/cordis.patch.yml）
├── dsh/
│   ├── index.mjs                     # 适配器：把 skills/ 挂到 harness 的 skills 服务
│   └── cordis.patch.yml              # bundle 层：insert 本插件
├── skills/project-handover/
│   ├── SKILL.md                      # 技能定义（两个功能、硬规则、流程）
│   ├── references/                   # 8 份规范与模板
│   │   ├── info-doc-format.md        # HANDOVER.md 固定格式规范
│   │   ├── handover-doc-template.md  # 骨架模板（照抄即合格）
│   │   ├── package-entry-template.md
│   │   ├── protocol-template.md      # 交接流程与启动指令骨架
│   │   ├── kickoff-prompt-template.md
│   │   ├── take-in-protocol.md       # 多项目接入决策与执行规范
│   │   ├── approval-gate.md          # 资源门禁：阶段 A/B 分类表 + 审批单模板
│   │   └── packaging-rules.md        # 打包/校验细则（踩坑记录）
│   └── scripts/                      # 5 个工具 + 1 个共用小库
├── README.md
└── LICENSE
```

## License

[MIT](LICENSE)
