#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""project-handover 共用小库：极简 YAML front-matter 解析 + 固定格式常量。

只依赖标准库；不引入 PyYAML（交接脚本要能在裸机上直接跑）。
支持 front-matter 子集：
    key: value
    key: 123
    key: true / false
    key: null
    key: "quoted"
    key: [a, b, "c"]
"""

import re
import datetime

# ---- 固定格式常量（v1）----------------------------------------------------

REQUIRED_KEYS = [
    "handover_version", "project_id", "project_name", "kind", "status",
    "created", "deadline", "priority", "resources", "depends_on",
    "verified", "submitted", "next_action",
]
OPTIONAL_KEYS = ["owner", "repo", "base_commit", "blocking_reason", "tags", "gated_actions"]

ENUMS = {
    "kind": {"project", "task", "experiment", "research"},
    "status": {"planning", "in_progress", "blocked", "stage_done", "done"},
    "priority": {"P0", "P1", "P2"},
}
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}

SECTIONS = [
    "## 1. 目标与验收标准",
    "## 2. 规则与硬约束",
    "## 3. 工作区地图",
    "## 4. 环境与前置",
    "## 5. 结论清单",
    "## 6. 红线（已否决 / 已重复 / 已占用）",
    "## 7. 已实现但未验证",
    "## 8. 未完成事项（按优先级）",
    "## 9. 合规 / 提交清单",
    "## 10. 复核方法",
    "## 11. 数据与文件索引",
    "## 12. 交接边界",
]

INFO_DOC_NAME = "HANDOVER.md"


def _strip_comment(value: str) -> str:
    """去掉行内注释（不在引号内的 ' #'）。"""
    out, quote = [], None
    i = 0
    while i < len(value):
        ch = value[i]
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and i > 0 and value[i - 1] in " \t":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).strip()


def _scalar(raw: str):
    v = _strip_comment(raw).strip()
    if v == "" or v.lower() in ("null", "~", "none"):
        return None
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        items = []
        for part in re.split(r",(?![^\[]*\])", inner):
            items.append(_scalar(part))
        return items
    if (v.startswith('"') and v.endswith('"') and len(v) >= 2) or \
       (v.startswith("'") and v.endswith("'") and len(v) >= 2):
        return v[1:-1]
    return v


def parse_front_matter(text: str):
    """返回 (meta dict, body str, errors list)。"""
    errors = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text, ["front-matter 缺失：文件必须以单独的 '---' 开头"]
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, ["front-matter 未闭合：缺少结束的 '---'"]
    meta = {}
    for i in range(1, end):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if not m:
            errors.append("front-matter 第 %d 行无法解析：%s" % (i + 1, line.strip()))
            continue
        meta[m.group(1)] = _scalar(m.group(2))
    body = "\n".join(lines[end + 1:])
    return meta, body, errors


def parse_iso8601(value):
    """尽量解析 ISO8601；返回 datetime 或 None。"""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def fmt_deadline(value):
    return "null" if value is None else str(value)


def section_map(body: str):
    """返回 {章节标题: 该章节正文}。"""
    found = {}
    current = None
    buf = []
    for line in body.split("\n"):
        if line.strip() in SECTIONS:
            if current:
                found[current] = "\n".join(buf)
            current = line.strip()
            buf = []
        elif current:
            buf.append(line)
    if current:
        found[current] = "\n".join(buf)
    return found


def read_info_doc_from_path(path: str) -> str:
    """从目录或归档(tar.gz/zip)里读出 HANDOVER.md 文本；失败抛 RuntimeError。"""
    import os
    import tarfile
    import zipfile

    if os.path.isdir(path):
        direct = os.path.join(path, INFO_DOC_NAME)
        if os.path.isfile(direct):
            with open(direct, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        hits = []
        for root, _dirs, files in os.walk(path):
            if INFO_DOC_NAME in files:
                hits.append(os.path.join(root, INFO_DOC_NAME))
        if len(hits) == 1:
            with open(hits[0], "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        if not hits:
            raise RuntimeError("目录内找不到 %s" % INFO_DOC_NAME)
        raise RuntimeError("目录内有 %d 个 %s（必须恰好 1 个）" % (len(hits), INFO_DOC_NAME))

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            cands = [n for n in zf.namelist()
                     if n.endswith("/" + INFO_DOC_NAME) or n == INFO_DOC_NAME]
            if len(cands) != 1:
                raise RuntimeError("压缩包内有 %d 个 %s（必须恰好 1 个）" % (len(cands), INFO_DOC_NAME))
            return zf.read(cands[0]).decode("utf-8", errors="replace")

    try:
        with tarfile.open(path, "r:*") as tf:
            cands = [m for m in tf.getmembers()
                     if m.isfile() and (m.name.endswith("/" + INFO_DOC_NAME) or m.name == INFO_DOC_NAME)]
            if len(cands) != 1:
                raise RuntimeError("压缩包内有 %d 个 %s（必须恰好 1 个）" % (len(cands), INFO_DOC_NAME))
            fh = tf.extractfile(cands[0])
            return fh.read().decode("utf-8", errors="replace")
    except tarfile.TarError as exc:
        raise RuntimeError("既不是目录，也不是可读的 tar/zip 归档：%s" % exc)
