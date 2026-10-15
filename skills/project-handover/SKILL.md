---
name: project-handover
description: "项目交接的两个功能：**交出**（把一个项目/任务的全部内容与信息打成一个压缩包，含固定格式的项目信息文档）与**接入**（为每个项目建独立命名目录、读完全部项目信息再决定接入细节；资源无关的读取与整理自动执行，编译/跑测/基准/训练/推送等**依赖机器资源配置的操作必须先汇报、审核通过后才执行**）。Use when the user says 交出 / 交接 / 导出交接包 / 项目交接 / hand over / handoff out, OR 接入 / 接手 / 继续这个项目 / 接入多个项目 / take over / handoff in / resume from a handover archive."
argument-hint: "交出 <project-dir> | 接入 <pkg.tar.gz|dir> [<pkg2> ...] [--apply]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(*)
---

# /project-handover：项目交接（交出 / 接入）

> 本 skill 只有两个功能，触发词就是它们的名字。**先判断用户要哪个，再进入对应流程；不要混着做。**

| 功能 | 触发 | 一句话 |
| --- | --- | --- |
| **交出** | 交出 / 交接 / 导出 / handover | 把**一个**项目的全部内容与信息打成**一个**压缩包；信息文档格式固定 |
| **接入** | 接入 / 接手 / 继续 / take over | 读**一个或多个**交接包 → **先读完所有项目信息** → 决定接入细节 → **自动执行** |

---

# 功能一：交出（hand out）

## 硬规则

| # | 规则 |
| --- | --- |
| **O1** | **一次只交出一个项目/任务。** 用户要求一次交出多个 → 明确拒绝并拆成多次，每次一个包（"同一时间，交出只作用于一个项目或任务"）。若多个项目同属一个任务，先与用户确认归并边界，再作为一个项目交。 |
| **O2** | **必须产出且只产出一个压缩包**，包内含"新 AI 接手所需的全部内容与信息"。缺件即失败。 |
| **O3** | **包内项目信息文档格式固定**（见 `references/info-doc-format.md`）：归档根必须恰好有一个 `HANDOVER.md`，含规定 YAML front-matter 与 12 个固定章节；用 `scripts/check_info_doc.py` 校验，必须通过。 |
| **O4** | **打包方式按实际情况决定**（见下方决策程序），并在 `HANDOVER.md` 的边界章节写明"包含/未包含 + 补齐命令"。 |
| **O5** | 未验证/未提交的内容必须显式声明（`verified` / `submitted` 字段 + 正文），否则接手方会误判。 |
| **O6** | 归档用 **tar.gz**；产出后必须**解包全量校验**（`scripts/package_handover.*` 已固化）。 |

## 打包方式决策程序（O4）

对候选内容逐项过这 5 问，答案决定取舍；**给不出理由的项不要放进去**：

| 问 | 放进去的条件 | 否则 |
| --- | --- | --- |
| ① 接手方能自己再生成吗？ | 不能 / 成本高 → **入包** | 能一行命令复现（如完整 git 历史）→ 不放入，写补齐命令 |
| ② 接手方有网络吗？ | 可能离线 → **入包源码副本** | 有网 → 可只给 patch/bundle |
| ③ 体积是否可接受？ | ≤ 约 100 MB → 入包 | 过大 → 只入可再生部分 + 说明 |
| ④ 是否含敏感信息？ | 无密钥/无个人隐私路径 → 可入包 | 有 → **绝不入包**，改用环境变量或占位符 |
| ⑤ 是否是"只存在于会话里的证据"？ | —（无论如何都进不了包） | 在边界表**明确声明并给复核命令** |

参考结论：报告/手册/补丁/脚本/核对数据/浅克隆源码 → 入包；完整 git 历史、子模块内容、会话内原始报告、外部网页原文、运行环境 → 不入包 + 补齐命令。

## 产出物（固定 6 件）

```
<slug>-<YYYYMMDD>/
├── HANDOVER.md              # ★ 项目信息文档（固定格式，机器可读）
├── 00-先读我.md             # 人读入口：清单 + 快速上手 + 包含/未包含
├── 01-交接流程与启动指令.md  # 交付方式 + 必须交代的事项 + 启动指令 + 接收方自检
├── MANIFEST-SHA256.txt      # LF + 正斜杠（脚本生成）
├── …（按决策程序放入的 artifacts：docs/ patches/ tools/ data/ src/ …）
└── <slug>-<YYYYMMDD>.tar.gz ← 归档，在包外一层
```

## 流程

| 步 | 动作 | 工具 |
| --- | --- | --- |
| O-P0 | 确认**单一**项目边界与 slug；对照决策程序列包含/排除清单 | 与用户确认 |
| O-P1 | 写 `HANDOVER.md`（12 节 + front-matter） | `references/handover-doc-template.md` |
| O-P2 | 写 `00-先读我.md`、`01-交接流程与启动指令.md`（含六段式启动指令） | `references/package-entry-template.md`、`references/protocol-template.md`、`references/kickoff-prompt-template.md` |
| O-P3 | 校验信息文档格式 | `python3 scripts/check_info_doc.py <pkg>/HANDOVER.md` |
| O-P4 | 打包 + 端到端校验 | `scripts/package_handover.sh`（Linux/Git-Bash）或 `scripts/package_handover.ps1`（Windows） |
| O-P5 | 回复用户：归档路径 + SHA256 + 校验结论 + 启动指令整段 | — |

## 回复模板（O-P5）

```
【交出完成】<项目名> → <归档路径>
SHA256: <sha>   大小: <n> MB   条目: <n> 个文件
校验: 解包端到端全量通过（FAIL=0）；信息文档格式校验通过
未验证: <列未编译/未实测项>；未提交: <是否已 push/PR/issue>
【启动指令】<整段可复制>（见 01-交接流程与启动指令.md §D）
```

---

# 功能二：接入（take over）

## 硬规则

| # | 规则 |
| --- | --- |
| **I1** | **收到接入指令后先读，再决定。** 若同时接入多个项目/任务，**必须先把所有项目的信息文档读完**（`HANDOVER.md`），才允许决定接入细节。禁止只读一个就开工。 |
| **I2** | **读完即自动执行 —— 但只限"资源无关"操作**：信息读取与项目整理（列清单、建目录、解包、格式/哈希校验、写索引与计划、读文档与日志、轻量文本统计）。这类不需要审批。 |
| **I9** | **资源相关操作一律先汇报、审核通过后才能执行**：任何依赖具体机器资源配置的执行/计算/分析——编译构建、跑测试/基准/性能、训练/推理、设备占用、大规模数据处理、需要凭据或外部服务、修改外部系统（push/PR/部署）、删除或覆盖数据。**未获批不得执行，也不得"先跑一下试试"。** |
| **I10** | 判定不确定 → **默认归入需审批**；审批单必须逐项写清命令、资源占用、依赖的机器配置、风险与回滚、预期产物、不执行的后果；**执行范围不得超出获批范围**。 |
| **I3** | 只有以下情况才停下来问：① 不可逆操作（push / 开 PR / 删除 / 覆盖）；② 凭据或环境缺失且无法自行获取；③ 多项目信息**互相冲突**（同一资源、同一文件、互相依赖成环）；④ 信息文档缺件或格式校验不通过。 |
| **I4** | 多项目**同抢独占资源**（NPU 卡、GPU、串口、独占锁）时必须**串行化**，并写进接入计划。 |
| **I5** | 接入结论必须**可核验**：每步按四件套回报（命令 / 日志路径 / 结论 / 下一步）。 |
| **I6** | 只做信息文档里写明的事；需要扩范围时先说明理由并等确认。 |
| **I7** | **每个项目必须建独立的项目目录并命名**：目录名 = `HANDOVER.md` 的 `project_id`（kebab-case、唯一、非法字符替换为 `-`；缺失则用归档名兜底）。**不同项目不得混在同一目录**。目录已存在时默认**追加日期**新建（`<project_id>-<YYYYMMDD>`），不得静默覆盖。 |
| **I8** | 工作根下维护 `INDEX.md`（人读）与 `registry.json`（机器读）；每个项目目录内维护 `ACCESS.md`（接入记录：来源归档 + SHA256 + 已读确认 + 接入细节 + 执行日志）。归档原件留存到 `_archives/`。 |

## 流程

| 步 | 动作 | 产出 |
| --- | --- | --- |
| I-P0 清单 | 找出所有交接包/目录 | `python3 scripts/scan_handovers.py <路径...>` → 对象清单 |
| **I-P1 建目录并命名** | **为每个项目建独立目录**（名 = `project_id`），把归档解进该目录；归档留存 `_archives/`；生成 `INDEX.md` / `registry.json` / 各项目 `ACCESS.md` | `python3 scripts/prepare_projects.py --root <工作根> <pkg...>` |
| I-P2 **全读** | **逐个读完所有 `<project_id>/HANDOVER.md`**（含边界与红线章节） | 每项目一页要点 + 比较表 |
| I-P3 决策 | 横向比较，定接入细节：**顺序 / 并行度 / 串行化 / 冲突处理 / 每项目的"接入完成"定义 / 首先执行的动作** | 接入计划表（见下） |
| I-P4 校验前置 | 每包跑接收方自检（`verify_handover.sh`）+ 格式校验（`check_info_doc.py`） | 自检结果 |
| I-P5 **自动执行（阶段 A · 资源无关）** | 只做信息读取与项目整理：读完全部 `HANDOVER.md`、建目录、写 `INDEX`/`registry`/`ACCESS`、产出接入计划 | 目录 + 索引 + 接入计划 |
| I-P6 **汇报待审（阶段 B · 资源相关）** | 把要执行的资源相关操作写成**审批单**（`<工作根>/APPROVALS.md`，并在 `ACCESS.md` 记一行 `pending`），**等用户显式审核通过** | 待审清单（含命令/资源/风险/产物） |
| I-P7 获批后执行 + 汇总 | 仅在获批范围内执行，四件套回报；未获批项留在待审 | 执行日志 + 接入报告 |

## 阶段 A / 阶段 B 速判（I2 / I9 / I10）

| 阶段 | 内容 | 例子 | 审批 |
| --- | --- | --- | --- |
| **A · 自动** | 信息读取、项目整理 | 列清单、建 `project_id/` 目录、解包、格式/哈希校验、写 INDEX/registry/ACCESS、出接入计划、静态阅读代码 | **不需要** |
| **B · 待审** | 具体执行/计算/分析，依赖机器资源配置 | 编译构建、跑测试/基准/性能、训练/推理、设备占用、大规模数据处理、需要凭据或外部服务、push/PR/部署、删除或覆盖 | **必须先汇报，审核通过后执行** |

判据三问（任一"是"→ 阶段 B）：① 需要特定机器能力（NPU/GPU/核数/内存/驱动/编译器/许可证/网络）？② 消耗不可忽略资源或有副作用？③ 换台配置不同的机器结论会变？
**不确定 → 归入阶段 B。** 完整分类表、审批单模板与示例见 `references/approval-gate.md`。

## 工作根布局（I-P1 结果）

```
<工作根>/
├── INDEX.md              # 人读：项目 → 目录/优先级/截止/依赖/资源/状态
├── registry.json         # 机器读：含来源归档路径与 SHA256
├── _archives/            # 原始交接归档留存
└── <project_id>/         # ★ 每个项目一个独立目录（归档内容解到这里）
    ├── HANDOVER.md
    ├── 00-先读我.md
    ├── ACCESS.md         # 接入记录：来源 + SHA256 + 已读确认 + 接入细节 + 执行日志
    └── …（该项目自己的 artifacts）
```

命名规则：目录名 = `project_id`；冲突默认 `version`（新建 `<project_id>-<YYYYMMDD>`），可 `--on-collision update|skip`；支持 `--dry-run` 预览。

## 接入计划表（I-P2 必须产出）

| 项目 | 优先级 | 截止 | 依赖 | 独占资源 | 首动作 | 串行/并行 | 接入完成定义 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<project_id>` | P0 | `<deadline>` | `<dep>` | `<res>` | `<first action>` | 串行（资源冲突） | `<done criteria>` |

## 接入报告模板（I-P7）

```
【接入完成】共 N 个项目：<ids>
读取情况: 全部 HANDOVER.md 已读（N/N）；格式校验通过；自检通过
接入顺序与理由: <按截止+优先级+资源串行化>
阶段 A 已完成（资源无关）: <建目录 / 索引 / ACCESS / 接入计划 …>
待审（阶段 B，未执行）: <AR-编号 — 项目 — 操作 — 资源占用 — 状态 pending>
已获批并执行: <项目 — 动作 — 命令 — 结论>
阻塞: <项目 — 原因 — 需要的输入>
下一个动作: <具体；若要开工，请批准 AR-xxx>
四件套证据: <日志路径列表>
```

---

# 两个功能共用的规范

| # | 规范 | 为什么 |
| --- | --- | --- |
| R1 | 零上下文自包含：接手方不需读原会话 | 它读不到 |
| R2 | 边界必须显式：未包含项 + 补齐命令 | 浅克隆/空子模块/会话内证据，不声明就被当成已包含 |
| R3 | 清单 **LF + 正斜杠**，且**解包后全量**校验 | Windows 默认 CRLF/反斜杠 → Linux `sha256sum -c` 全 FAILED |
| R4 | 归档优先 tar.gz；ZIP 需验 UTF-8 标志位与 `/` | .NET ZIP 在 Windows 写反斜杠且不置 bit11 → Linux 乱码/平铺 |
| R5 | 文本文件不得含 NUL（脚本自检） | 一个 NUL 就让读取工具判为二进制、无法编辑 |
| R6 | 启动指令六段式：角色/必读/状态/环境/按序执行/禁止+回报 | 缺"禁止"会发生未授权 push；缺"回报"拿不到可核验进展 |
| R7 | 显式声明 `verified` / `submitted` | 否则接手方默认已实测/已提交 |
| R8 | 改文本用 editor 工具，不要在 shell 字符串里拼内容 | PowerShell `` `01 `` 会解析成 NUL，静默吃掉字符 |
| R9 | 回复必须带校验证据（SHA256、OK/FAIL、格式校验结论） | "应该没问题"不是交付 |
| R10 | 把时间约束写进信息文档与启动指令 | 第一动作常由截止时间决定 |

## 反模式

- ❌ 一次交出多个项目（违反 O1）→ 拆成多次。
- ❌ 接入时只读一个包就开工（违反 I1）。
- ❌ **接入后直接编译/跑测试/跑基准/训练**（违反 I9）——这些是阶段 B，必须先报批。
- ❌ **用"先跑一下试试""这个很小"绕过审批**（违反 I9/I10）。
- ❌ 把阶段 A 的读文件操作也塞进审批单（制造审批噪音）。
- ❌ 获批后擅自扩大命令/资源/时长范围（违反 I10）。
- ❌ 两个项目抢同一张卡却并行跑（违反 I4）。
- ❌ 信息文档用自由格式（违反 O3）→ `check_info_doc.py` 会拒绝。
- ❌ 把误判/已重复的结论留在清单里不标注 → 接手方重复浪费。

## 验收清单

**交出**：六件齐备；`check_info_doc.py` 通过；tar.gz 解包全量 SHA256 `FAIL=0`；无 NUL；边界表与包内目录一致；启动指令无 `<占位符>`；O1 单一项目。
**接入**：`scan_handovers.py` 列全；`prepare_projects.py` 为**每个项目**建好独立目录且命名 = `project_id`（无混放、无静默覆盖）；`INDEX.md`/`registry.json`/各项目 `ACCESS.md` 已生成；**N/N 个 HANDOVER.md 全部读过**；接入计划表已产出；自检与格式校验通过；**阶段 A 只做了资源无关操作**；**所有资源相关操作都已列入审批单且未执行**（除非用户显式批准）；冲突/阻塞项已列明。

## 文件索引

| 文件 | 用途 |
| --- | --- |
| `references/info-doc-format.md` | **`HANDOVER.md` 固定格式规范**（front-matter 契约 + 12 章节 + 校验规则） |
| `references/handover-doc-template.md` | `HANDOVER.md` 骨架（照抄即合格） |
| `references/package-entry-template.md` | `00-先读我.md` 骨架 |
| `references/protocol-template.md` | `01-交接流程与启动指令.md` 骨架 |
| `references/kickoff-prompt-template.md` | 启动指令六段式模板 |
| `references/take-in-protocol.md` | 多项目接入的决策与执行规范 |
| `references/approval-gate.md` | **资源门禁**：阶段 A/B 分类表、审批单模板、执行纪律与示例 |
| `references/packaging-rules.md` | 打包/校验细则（每条对应一次真实踩坑） |
| `scripts/check_info_doc.py` | 信息文档格式校验（交出前 / 接入时都用） |
| `scripts/scan_handovers.py` | 多项目清单：抽取各包 HANDOVER.md → 比较表 + 建议顺序 + 资源冲突 |
| `scripts/prepare_projects.py` | **接入建目录**：按 `project_id` 为每个项目建独立目录、解包、留存归档、生成 INDEX/registry/ACCESS |
| `scripts/package_handover.sh` / `.ps1` | 打包 + 端到端校验（Linux / Windows） |
| `scripts/verify_handover.sh` | 接收方开局自检 |

## 安装 / 更新

**方式 A · DSH 插件（推荐）**：本 skill 也以 DeepSeek Harness bundle 形式发布（`dsh-project-handover`）。
仓库布局为 `skills/project-handover/` + `dsh/index.mjs`（把 `skills/` 挂到 harness 的 skills 服务）+ `dsh/cordis.patch.yml`（bundle 层 insert）。

```bash
cd ~/.dsh/profiles/<profile>
pnpm add github:xiaoyu-stars/project-handover-skill
# 再把 "dsh-project-handover" 加入 profile package.json 的 dsh.profile.bundles，然后重启 DSH
```

**方式 B · 直接放技能目录（免插件）**：把仓库里的 `skills/project-handover/` 整目录拷到 `~/.dsh/skills/`
（或 Claude Code 的 `~/.claude/skills/`）即可被自动发现。本机当前就是这种方式。

**同名优先级**：插件内置（bundled）技能 rank 低于用户/项目技能，因此用户级副本始终优先。
