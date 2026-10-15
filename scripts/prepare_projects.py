#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prepare_projects.py — 接入时为每个项目建立**独立的项目目录并命名**。

用法:
    python3 prepare_projects.py --root <工作根> <pkg1> [<pkg2> ...] [--dry-run]
                                [--on-collision version|update|skip] [--keep-archives]

做的事（对应 SKILL 的 I-P1）:
    1) 从每个交接包/目录读 HANDOVER.md，取 project_id 作为**目录名**
    2) 在 <工作根> 下建 <project_id>/，把归档内容解到该目录（不与其他项目混在一起）
    3) 原始归档留存到 <工作根>/_archives/
    4) 生成/更新 <工作根>/INDEX.md（人读）与 <工作根>/registry.json（机器读）
    5) 在每个项目目录写 ACCESS.md（接入记录：来源、SHA256、时间、已读确认、进度区）

命名规则:
    - 目录名 = project_id（kebab-case、唯一）；非法字符替换为 '-'
    - project_id 缺失 → 用归档文件名（去扩展名）作为兜底名
    - 目录已存在：默认 version → 新建 <project_id>-<YYYYMMDD>；update → 覆盖刷新；skip → 跳过并报告

退出码: 0 全部就绪；1 有项目失败。
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _handover_lib import (  # noqa: E402
    INFO_DOC_NAME, PRIORITY_RANK, parse_front_matter, parse_iso8601, read_info_doc_from_path,
)

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
ACCESS_TEMPLATE = """# ACCESS.md — 接入记录（{pid}）

| 项 | 值 |
| --- | --- |
| project_id | `{pid}` |
| 项目名 | {pname} |
| 来源 | `{src}` |
| 归档 SHA256 | `{sha}` |
| 首次接入 | {ts} |
| 工作目录 | `{dir}` |

## 已读确认（I1：必须读完全部信息文档才能决定细节）
- [x] `HANDOVER.md`（13 个 front-matter 键 + 12 章节，格式校验：{fmt}）
- [ ] `00-先读我.md`
- [ ] `01-交接流程与启动指令.md`

## 接入细节（决策留痕）
- 首动作（来自 next_action）：{next_action}
- 依赖：{deps}
- 独占资源：{res}
- 串行/并行：<由资源冲突决定>

## 执行日志（每步四件套：命令 / 日志路径 / 结论 / 下一步）
| 时间 | 动作 | 命令 | 结论 | 日志 |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
"""


def now_iso():
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sanitize(name):
    n = SAFE_NAME.sub("-", (name or "").strip()).strip("-.")
    return n or ""


def safe_members_tar(tf, dest):
    dest = os.path.abspath(dest)
    out = []
    for m in tf.getmembers():
        target = os.path.abspath(os.path.join(dest, m.name))
        if not target.startswith(dest + os.sep) and target != dest:
            raise RuntimeError("归档含越界路径（拒绝解包）: %s" % m.name)
        if m.issym() or m.islnk():
            continue  # 不还原链接，避免逃逸
        out.append(m)
    return out


def extract(archive, dest):
    os.makedirs(dest, exist_ok=True)
    if os.path.isdir(archive):
        # 目录输入：复制树（跳过目标自身）
        for item in os.listdir(archive):
            s = os.path.join(archive, item)
            d = os.path.join(dest, item)
            if os.path.abspath(s) == os.path.abspath(dest):
                continue
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True, symlinks=False)
            else:
                shutil.copy2(s, d)
        return "dir"
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for n in zf.namelist():
                t = os.path.abspath(os.path.join(dest, n))
                if not t.startswith(os.path.abspath(dest) + os.sep):
                    raise RuntimeError("归档含越界路径（拒绝解包）: %s" % n)
            zf.extractall(dest)
        return "zip"
    with tarfile.open(archive, "r:*") as tf:
        members = safe_members_tar(tf, dest)
        try:
            tf.extractall(dest, members=members, filter="data")  # py>=3.12
        except TypeError:
            tf.extractall(dest, members=members)
    return "tar"


def flatten_if_single_dir(dest):
    """归档里若只有一个顶层目录，把它的内容上提到 dest（去掉多余一层）。"""
    items = [i for i in os.listdir(dest)]
    if len(items) == 1 and os.path.isdir(os.path.join(dest, items[0])):
        inner = os.path.join(dest, items[0])
        for name in os.listdir(inner):
            shutil.move(os.path.join(inner, name), os.path.join(dest, name))
        os.rmdir(inner)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pkgs", nargs="+")
    ap.add_argument("--root", required=True, help="工作根：所有项目目录建在这里")
    ap.add_argument("--on-collision", choices=["version", "update", "skip"], default="version")
    ap.add_argument("--keep-archives", action="store_true", default=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    archives_dir = os.path.join(root, "_archives")
    registry_path = os.path.join(root, "registry.json")
    index_path = os.path.join(root, "INDEX.md")

    registry = {"updated": now_iso(), "root": root, "projects": []}
    if os.path.isfile(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as fh:
                registry = json.load(fh)
            registry.setdefault("projects", [])
        except (OSError, ValueError):
            pass
    known = {p.get("project_id"): p for p in registry["projects"]}

    if not args.dry_run:
        os.makedirs(root, exist_ok=True)
        if args.keep_archives and not os.path.isdir(archives_dir):
            os.makedirs(archives_dir, exist_ok=True)

    results = []
    for pkg in args.pkgs:
        pkg_abs = os.path.abspath(pkg)
        rec = {"source": pkg_abs, "ok": False, "error": None, "dir": None, "project_id": None}
        try:
            text = read_info_doc_from_path(pkg_abs)
            meta, _body, _errs = parse_front_matter(text)
        except RuntimeError as exc:
            rec["error"] = str(exc)
            results.append(rec)
            continue

        pid = sanitize(str(meta.get("project_id") or "")) or \
            sanitize(os.path.splitext(os.path.basename(pkg_abs))[0]) or "project"
        rec["project_id"] = pid
        target = os.path.join(root, pid)

        if os.path.exists(target):
            if args.on_collision == "skip":
                rec["error"] = "目录已存在（--on-collision=skip）: %s" % target
                results.append(rec)
                continue
            if args.on_collision == "version":
                stamp = datetime.datetime.now().strftime("%Y%m%d")
                target = os.path.join(root, "%s-%s" % (pid, stamp))
                i = 2
                while os.path.exists(target):
                    target = os.path.join(root, "%s-%s-%d" % (pid, stamp, i))
                    i += 1
            # update → 原地刷新

        sha = sha256_file(pkg_abs) if os.path.isfile(pkg_abs) else "-"
        rec["dir"] = target
        rec["sha256"] = sha
        rec["meta"] = meta

        if args.dry_run:
            rec["ok"] = True
            results.append(rec)
            continue

        try:
            if args.on_collision == "update" and os.path.isdir(target):
                for name in os.listdir(target):
                    if name == "ACCESS.md":
                        continue
                    p = os.path.join(target, name)
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
            os.makedirs(target, exist_ok=True)
            kind = extract(pkg_abs, target)
            flatten_if_single_dir(target)
            # 归档留存
            if args.keep_archives and os.path.isfile(pkg_abs) and \
                    os.path.abspath(os.path.dirname(pkg_abs)) != archives_dir:
                shutil.copy2(pkg_abs, os.path.join(archives_dir, os.path.basename(pkg_abs)))
            # ACCESS.md
            access = os.path.join(target, "ACCESS.md")
            body = ACCESS_TEMPLATE.format(
                pid=pid, pname=meta.get("project_name", ""), src=pkg_abs, sha=sha,
                ts=now_iso(), dir=target, fmt="见 check_info_doc.py",
                next_action=meta.get("next_action", ""),
                deps=", ".join(map(str, meta.get("depends_on") or [])) or "-",
                res=", ".join(map(str, meta.get("resources") or [])) or "-")
            if os.path.isfile(access):
                with open(access, "a", encoding="utf-8") as fh:
                    fh.write("\n---\n\n## 再次接入 %s（来源 %s，SHA256 %s）\n" % (now_iso(), pkg_abs, sha))
            else:
                with open(access, "w", encoding="utf-8") as fh:
                    fh.write(body)
            rec["ok"] = True
            rec["extract"] = kind
        except (OSError, RuntimeError, tarfile.TarError, zipfile.BadZipFile) as exc:
            rec["error"] = "解包失败: %s" % exc
        results.append(rec)

    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]

    print("== 接入准备：%d 个对象 → 工作根 %s ==" % (len(results), root))
    for r in results:
        if r["ok"]:
            print("  [OK  ] %s → %s" % (os.path.basename(r["source"]), r["dir"]))
        else:
            print("  [FAIL] %s → %s" % (os.path.basename(r["source"]), r["error"]))

    if not args.dry_run:
        for r in ok:
            m = r.get("meta") or {}
            entry = {"project_id": r["project_id"], "dir": r["dir"],
                     "project_name": m.get("project_name"), "priority": m.get("priority"),
                     "deadline": m.get("deadline"), "status": m.get("status"),
                     "resources": m.get("resources") or [], "depends_on": m.get("depends_on") or [],
                     "verified": m.get("verified"), "submitted": m.get("submitted"),
                     "source": r["source"], "sha256": r.get("sha256"),
                     "attached_at": now_iso()}
            known[r["project_id"]] = entry
        registry["projects"] = list(known.values())
        registry["updated"] = now_iso()
        with open(registry_path, "w", encoding="utf-8") as fh:
            json.dump(registry, fh, ensure_ascii=False, indent=2)

        lines = ["# 项目索引（INDEX）", "",
                 "> 由 `prepare_projects.py` 生成；每个项目一个独立目录。更新于 %s" % registry["updated"], "",
                 "| project_id | 目录 | 优先级 | 截止 | 依赖 | 独占资源 | 已验证 | 已提交 | 来源归档 |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for p in sorted(registry["projects"],
                        key=lambda x: (PRIORITY_RANK.get(x.get("priority"), 9), str(x.get("deadline") or "zzz"))):
            lines.append("| %s | `%s` | %s | %s | %s | %s | %s | %s | `%s` |" % (
                p.get("project_id"), os.path.relpath(p.get("dir"), root), p.get("priority"),
                p.get("deadline"), ", ".join(p.get("depends_on") or []) or "-",
                ", ".join(p.get("resources") or []) or "-", p.get("verified"), p.get("submitted"),
                os.path.basename(str(p.get("source")))))
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print("\n已写出：\n  - %s\n  - %s" % (index_path, registry_path))
        print("每个项目目录内已生成 ACCESS.md（含已读确认与执行日志表）。")
    else:
        print("\n（--dry-run：未落盘）")

    if bad:
        print("\n%d 个对象未就绪，先解决再加。" % len(bad))
        return 1
    print("\n下一步：对每个项目目录跑 `check_info_doc.py` 与 `verify_handover.sh`，"
          "读完全部 HANDOVER.md 后再定接入细节（见 references/take-in-protocol.md）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
