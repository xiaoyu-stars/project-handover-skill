# `HANDOVER.md` 固定格式规范（v1）

> 这是"交出"必须满足的**硬格式**，也是"接入"能**先读完所有项目信息再决定细节**的前提：格式固定 → 机器可读 → 可横向比较。
> 校验工具：`python3 scripts/check_info_doc.py <pkg>/HANDOVER.md`（必须通过才能交出）。

## 一、位置与数量

- 归档根目录**恰好一个** `HANDOVER.md`（0 个或 >1 个都算不合格）。
- 其它文件（`00-先读我.md`、`01-交接流程与启动指令.md`、`MANIFEST-SHA256.txt`、以及各家 artifacts）自由命名。

## 二、YAML front-matter 契约（必填键）

文件必须以 `---` 开头，front-matter 以单独一行的 `---` 结束。

```yaml
---
handover_version: 1                     # 固定 1
project_id: demo-project                 # 唯一标识（kebab-case），多项目接入靠它区分
project_name: 示例项目
kind: task                              # project | task | experiment | research
status: in_progress                     # planning | in_progress | blocked | stage_done | done
created: 2026-10-16T01:35+08:00         # ISO8601
deadline: 2026-10-18T18:00+08:00        # ISO8601 或 null
priority: P0                            # P0 | P1 | P2
resources: ["npu-0", "exclusive-card"]  # 需要独占的资源名（多项目串行化依据）；无则 []
depends_on: []                          # 依赖的其他 project_id；无则 []
verified: false                         # 交付物是否已实测/已编译
submitted: false                        # 是否已向外部系统提交（push / PR / issue）
next_action: "编译补丁并跑 A/B 基线对照"   # 接入时的第一个动作，必须非空、可执行
---
```

**可选键**：`owner`、`repo`、`base_commit`、`blocking_reason`、`tags`。

| 键 | 约束 | 接入时怎么用 |
| --- | --- | --- |
| `project_id` | 唯一、kebab-case | 依赖引用、冲突报告 |
| `deadline` | ISO8601 或 `null` | 排序第一依据 |
| `priority` | P0/P1/P2 | 同截止时的排序依据 |
| `resources` | 字符串列表 | **检测多项目抢同一独占资源 → 必须串行** |
| `depends_on` | project_id 列表 | 依赖方必须排在后面；缺依赖要报警 |
| `verified` / `submitted` | 布尔 | 接入方默认"未验证=不可信、未提交=还没落地" |
| `next_action` | 非空字符串 | 接入后**第一个**执行的动作 |

## 三、正文：12 个固定章节（编号与标题一字不差，顺序不可变）

```markdown
## 1. 目标与验收标准
## 2. 规则与硬约束
## 3. 工作区地图
## 4. 环境与前置
## 5. 结论清单
## 6. 红线（已否决 / 已重复 / 已占用）
## 7. 已实现但未验证
## 8. 未完成事项（按优先级）
## 9. 合规 / 提交清单
## 10. 复核方法
## 11. 数据与文件索引
## 12. 交接边界
```

| 章节 | 必含 | 说明 |
| --- | --- | --- |
| 1 | 目标 + 怎么算完成 | 接入的验收依据 |
| 2 | 截止、名额、格式、禁止事项 | 硬约束 |
| 3 | 路径 → 内容的表 | 每个交付物一行，标注能否再生 |
| 4 | 机器/依赖/前置命令/不可用能力 | 一上机就能跑 |
| 5 | 结论清单：问题 + 证据位置 + 置信度 + 状态 | **禁止无证据断言** |
| 6 | 已否决 / 已重复 / 已被占，附判定依据 | 防接手方重犯 |
| 7 | 改动 + 位置 + 验证方式 + 风险 | 明确"未编译/未实测" |
| 8 | 每条：做什么 + 命令 + 判读标准 | 接入据此自动执行 |
| 9 | 提交前逐条勾选 | 规则转成复选框 |
| 10 | 可直接粘的复核命令 | 让结论可验证 |
| 11 | 文件 → 内容 | 数据索引 |
| 12 | 未包含项 + 补齐命令 | 浅克隆/子模块/会话内证据/环境 |

## 四、机器校验规则（`check_info_doc.py`）

| 检查 | 级别 |
| --- | --- |
| root 下 HANDOVER.md 数量 == 1 | 错误 |
| front-matter 存在且 13 个必填键齐全 | 错误 |
| 枚举值合法（kind/status/priority）、`handover_version == 1` | 错误 |
| `created`/`deadline` 可解析为 ISO8601；`deadline >= created` | 错误 |
| `resources`/`depends_on` 是列表；`next_action` 非空 | 错误 |
| 12 个章节标题齐全且顺序正确 | 错误 |
| 章节 12 含"未包含"字样与"补齐/命令"线索 | 警告 |
| 章节 5 每条含证据位置（`:`+数字 或 反引号路径） | 警告 |
| 章节 8 含至少一条可执行命令（反引号/`$`/常见命令名） | 警告 |
| 正文残留 `<占位符>` | 警告（`--strict` 下降级为错误） |
| 章节 1/8 为空 | 错误 |

退出码：`0` 通过；`1` 有错误；`2` 仅警告（`--strict` 时按错误处理）。
输出：人读表格 + `--json` 机器可读结果。
