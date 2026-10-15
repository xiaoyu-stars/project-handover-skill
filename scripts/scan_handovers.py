#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_handovers.py — 接入前把多个交接包/项目横向读一遍。

用法:
    python3 scan_handovers.py <pkg_or_dir> [<pkg2> ...] [--json out.json]

做四件事（对应 SKILL 的 I-P0/I-P1/I-P2）:
    1) 从每个包/目录抽取 HANDOVER.md（读全文解析，不执行任何项目动作）
    2) 列出所有项目的关键信号（优先级/截止/依赖/独占资源/是否已验证/首动作）
    3) 检测：资源冲突（需串行）、依赖缺失、依赖序、未验证/未提交
    4) 给出建议接入顺序，并打印每个项目的 next_action

退出码: 0 全部读成功；1 有包读不到或格式不合法。
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _handover_lib import (  # noqa: E402
    INFO_DOC_NAME, PRIORITY_RANK, parse_front_matter, parse_iso8601,
    read_info_doc_from_path, section_map, REQUIRED_KEYS, SECTIONS,
)


def load(path):
    rec = {"path": path, "ok": False, "error": None, "meta": {}, "next_steps": ""}
    try:
        text = read_info_doc_from_path(path)
    except RuntimeError as exc:
        rec["error"] = str(exc)
        return rec
    meta, body, fm_errs = parse_front_matter(text)
    missing = [k for k in REQUIRED_KEYS if k not in meta]
    smap = section_map(body)
    missing_secs = [s for s in SECTIONS if s not in smap]
    if fm_errs or missing or missing_secs:
        rec["error"] = "格式不合法（缺键 %s；缺章节 %d 个）" % (",".join(missing) or "无", len(missing_secs))
        rec["meta"] = meta
        return rec
    rec["ok"] = True
    rec["meta"] = meta
    rec["next_steps"] = smap.get("## 8. 未完成事项（按优先级）", "").strip()
    return rec


def sort_key(rec):
    m = rec["meta"]
    dl = parse_iso8601(m.get("deadline"))
    return (PRIORITY_RANK.get(m.get("priority"), 9),
            0 if dl else 1,
            dl.timestamp() if dl else 0.0,
            str(m.get("project_id")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    recs = [load(p) for p in args.paths]
    bad = [r for r in recs if not r["ok"]]

    print("== 接入前扫描：共 %d 个交接对象 ==" % len(recs))
    for r in recs:
        if r["ok"]:
            print("  [OK  ] %s" % r["path"])
        else:
            print("  [FAIL] %s -> %s" % (r["path"], r["error"]))

    good = [r for r in recs if r["ok"]]
    if not good:
        print("\n没有任何可接入的项目（全部读取失败）。")
        return 1

    ids = {str(r["meta"].get("project_id")): r for r in good}

    print("\n=== 项目信号一览（I-P1 全读结果）===")
    print("| project_id | 优先级 | 截止 | 依赖 | 独占资源 | 已验证 | 已提交 | 首动作 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in sorted(good, key=sort_key):
        m = r["meta"]
        print("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            m.get("project_id"), m.get("priority"), m.get("deadline") or "null",
            ", ".join(m.get("depends_on") or []) or "-",
            ", ".join(m.get("resources") or []) or "-",
            m.get("verified"), m.get("submitted"),
            (m.get("next_action") or "").replace("|", "/")[:60]))

    # 资源冲突 → 必须串行
    res_map = defaultdict(list)
    for r in good:
        for res in (r["meta"].get("resources") or []):
            res_map[str(res)].append(str(r["meta"].get("project_id")))
    conflicts = {k: v for k, v in res_map.items() if len(v) > 1}

    # 依赖
    missing_deps, dep_edges = [], []
    for r in good:
        pid = str(r["meta"].get("project_id"))
        for dep in (r["meta"].get("depends_on") or []):
            dep = str(dep)
            if dep in ids:
                dep_edges.append((dep, pid))
            else:
                missing_deps.append((pid, dep))

    # 拓扑序（Kahn），同层按 sort_key
    order, remaining = [], list(good)
    while remaining:
        ready = [r for r in remaining
                 if all(d not in [str(x["meta"].get("project_id")) for x in remaining]
                        for d in [str(d) for d in (r["meta"].get("depends_on") or [])])]
        if not ready:  # 依赖成环
            ready = [min(remaining, key=sort_key)]
        ready.sort(key=sort_key)
        order.append(ready[0])
        remaining.remove(ready[0])

    print("\n=== 接入细节决策（I-P2）===")
    print("建议顺序：%s" % " → ".join(str(r["meta"].get("project_id")) for r in order))
    print("排序依据：依赖序优先，其次 优先级(P0<P1<P2)，再次 截止时间升序")
    if conflicts:
        print("\n[必须串行] 以下独占资源被多个项目共用：")
        for res, pids in conflicts.items():
            print("  - %s : %s  → 串行执行，前一个结束再启动后一个" % (res, ", ".join(pids)))
    else:
        print("\n无独占资源冲突 → 可并行（仍建议按依赖序启动）")
    if missing_deps:
        print("\n[依赖缺失] 依赖不在本次接入集合内：")
        for pid, dep in missing_deps:
            print("  - %s 依赖 %s（需要先取得该项目，或确认外部已就绪）" % (pid, dep))
    if dep_edges:
        print("\n依赖序：%s" % ", ".join("%s→%s" % e for e in dep_edges))

    unver = [str(r["meta"].get("project_id")) for r in good if r["meta"].get("verified") is False]
    unsub = [str(r["meta"].get("project_id")) for r in good if r["meta"].get("submitted") is False]
    print("\n[可信度] verified=false（结论按待复核处理）：%s" % (", ".join(unver) or "无"))
    print("[落地状态] submitted=false（本次接入需完成提交才算完成）：%s" % (", ".join(unsub) or "无"))

    print("\n=== 各项目首动作（接入后自动执行）===")
    for r in order:
        m = r["meta"]
        print("- [%s] %s" % (m.get("project_id"), m.get("next_action")))
        steps = r["next_steps"]
        if steps:
            first = [l.strip() for l in steps.split("\n") if l.strip()][:3]
            for l in first:
                print("      %s" % l[:110])

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({
                "projects": [{k: r["meta"].get(k) for k in r["meta"]} for r in order],
                "resources": {k: v for k, v in res_map.items()},
                "resource_conflicts": conflicts,
                "missing_dependencies": missing_deps,
                "dependency_edges": dep_edges,
                "verify_false": unver, "submitted_false": unsub,
                "failed": [{"path": r["path"], "error": r["error"]} for r in bad],
            }, fh, ensure_ascii=False, indent=2)
        print("\nJSON 已写出: %s" % args.json_out)

    print("\n下一步：按上面顺序执行各项目第 8 节；共享独占资源的项目串行；"
          "遇到不可逆操作/缺凭据/信息冲突才停下确认（见 references/take-in-protocol.md）。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
