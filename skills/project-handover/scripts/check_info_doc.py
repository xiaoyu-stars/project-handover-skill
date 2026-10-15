#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_info_doc.py — 校验 HANDOVER.md 是否符合 v1 固定格式。

用法:
    python3 check_info_doc.py <pkg_dir|HANDOVER.md|pkg.tar.gz> [--strict] [--json out.json]

退出码:
    0 通过
    1 有错误
    2 仅有警告（--strict 时按错误处理）
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _handover_lib import (  # noqa: E402
    ENUMS, INFO_DOC_NAME, OPTIONAL_KEYS, REQUIRED_KEYS, SECTIONS,
    parse_front_matter, parse_iso8601, read_info_doc_from_path, section_map,
)

PLACEHOLDER_RE = re.compile(r"<[^<>\n]{1,60}>")
EVIDENCE_RE = re.compile(r"(`[^`]+`|[\w./-]+:\d+|#\d+|\bhttps?://\S+)")


def check(text, strict=False):
    errors, warnings = [], []

    meta, body, fm_errs = parse_front_matter(text)
    errors.extend(fm_errs)

    # --- front-matter ---
    for key in REQUIRED_KEYS:
        if key not in meta:
            errors.append("front-matter 缺必填键: %s" % key)
        elif meta[key] in (None, "", []) and key not in ("deadline", "resources", "depends_on"):
            errors.append("front-matter 键 %s 为空" % key)
    for key in meta:
        if key not in REQUIRED_KEYS and key not in OPTIONAL_KEYS:
            warnings.append("front-matter 出现未声明键: %s" % key)

    if meta.get("handover_version") not in (1, "1"):
        errors.append("handover_version 必须为 1，实际 %r" % meta.get("handover_version"))
    for key, allowed in ENUMS.items():
        val = meta.get(key)
        if val is not None and val not in allowed:
            errors.append("%s 取值非法: %r（允许 %s）" % (key, val, "/".join(sorted(allowed))))
    for key in ("resources", "depends_on"):
        val = meta.get(key)
        if val is not None and not isinstance(val, list):
            errors.append("%s 必须是列表（如 [\"a\", \"b\"] 或 []），实际 %r" % (key, val))
    for key in ("verified", "submitted"):
        if key in meta and not isinstance(meta[key], bool):
            errors.append("%s 必须是 true/false，实际 %r" % (key, meta[key]))
    created = parse_iso8601(meta.get("created"))
    if created is None:
        errors.append("created 不是可解析的 ISO8601: %r" % meta.get("created"))
    dl = meta.get("deadline")
    if dl is not None:
        deadline = parse_iso8601(dl)
        if deadline is None:
            errors.append("deadline 不是可解析的 ISO8601: %r（无截止请写 null）" % dl)
        elif created is not None and deadline < created:
            errors.append("deadline(%s) 早于 created(%s)" % (dl, meta.get("created")))
    if not isinstance(meta.get("next_action"), str) or not meta.get("next_action", "").strip():
        errors.append("next_action 必须是非空字符串（接入方的第一个动作）")

    # --- 章节 ---
    smap = section_map(body)
    body_lines = [l.strip() for l in body.split("\n")]
    positions = []
    for title in SECTIONS:
        if title in smap:
            positions.append(body_lines.index(title))
        else:
            errors.append("缺少固定章节: %s" % title)
    if positions != sorted(positions) and len(positions) == len(SECTIONS):
        errors.append("12 个固定章节顺序不正确")

    def sec(idx):
        return smap.get(SECTIONS[idx], "").strip()

    if not sec(0):
        errors.append("章节 1（目标与验收标准）为空")
    if not sec(7):
        errors.append("章节 8（未完成事项）为空")
    if "未包含" not in sec(11):
        warnings.append("章节 12 未出现“未包含”字样（可能漏写边界）")
    if not re.search(r"(补齐|命令|git |command)", sec(11)):
        warnings.append("章节 12 未见补齐命令线索")

    sec5 = sec(4)
    if sec5 and not EVIDENCE_RE.search(sec5):
        warnings.append("章节 5 未见证据位置（file:line / `path` / #issue）")
    sec8 = sec(7)
    if sec8 and not re.search(r"(`|\\$|python|bash|tar|git|make|cmake|pytest)", sec8):
        warnings.append("章节 8 未见可执行命令（接入方无法自动执行）")

    ph = PLACEHOLDER_RE.findall(body)
    if ph:
        msg = "正文残留占位符 %d 处：%s" % (len(ph), ", ".join(sorted(set(ph))[:6]))
        (errors if strict else warnings).append(msg)

    return meta, errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="包目录 / HANDOVER.md / 归档(tar.gz|zip)")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    target = args.target
    try:
        if os.path.isfile(target):
            base = os.path.basename(target)
            if base == INFO_DOC_NAME:
                with open(target, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            else:
                text = read_info_doc_from_path(target)
        else:
            text = read_info_doc_from_path(target)
    except RuntimeError as exc:
        print("[FAIL] %s" % exc)
        if args.json_out:
            with open(args.json_out, "w", encoding="utf-8") as fh:
                json.dump({"ok": False, "errors": [str(exc)], "warnings": []}, fh, ensure_ascii=False, indent=2)
        return 1

    meta, errors, warnings = check(text, strict=args.strict)
    ok = not errors

    print("== HANDOVER.md 格式校验 ==")
    print("  项目      : %s (%s)" % (meta.get("project_id", "?"), meta.get("project_name", "?")))
    print("  状态/优先 : %s / %s" % (meta.get("status", "?"), meta.get("priority", "?")))
    print("  截止      : %s" % meta.get("deadline"))
    print("  资源      : %s" % (meta.get("resources") or []))
    print("  依赖      : %s" % (meta.get("depends_on") or []))
    print("  已读章节  : %d/12" % sum(1 for s in SECTIONS if s in section_map(text.split("---", 2)[-1] if text.startswith("---") else text)))
    print("  错误 %d 项 / 警告 %d 项" % (len(errors), len(warnings)))
    for e in errors:
        print("  [ERROR] %s" % e)
    for w in warnings:
        print("  [WARN ] %s" % w)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"ok": ok, "project_id": meta.get("project_id"), "meta": meta,
                       "errors": errors, "warnings": warnings}, fh, ensure_ascii=False, indent=2)

    if errors:
        print("结果: FAIL（格式不符合 v1 规范，不得交出）")
        return 1
    if warnings:
        print("结果: PASS（有警告）")
        return 2 if not args.strict else 1
    print("结果: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
