#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
game-wiki 本地索引器
用法: python index_wiki.py [目标目录]
默认扫描脚本所在目录，递归梳理所有文件，输出：
  1) 目录树
  2) 每个文件的类型/大小/关键内容（md 提取标题，文本提取首段）
  3) 生成 _INDEX.md 总览（便于人读）
仅做只读扫描，不修改任何源文件。
"""
import os
import sys
import json

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".workbuddy"}
TEXT_EXT = {".md", ".markdown", ".txt", ".text", ".rst", ".json",
            ".csv", ".tsv", ".yml", ".yaml", ".log", ".bat", ".sh",
            ".py", ".js", ".ts", ".html", ".htm", ".xml", ".cfg", ".ini"}


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def read_headings(path, max_h=2):
    """提取 markdown 标题与首段。"""
    out = {"headings": [], "first_lines": []}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return out
    in_code = False
    body_started = False
    for ln in lines[:400]:
        s = ln.rstrip("\n")
        if s.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if s.startswith("#"):
            level = len(s) - len(s.lstrip("#"))
            if level <= max_h:
                out["headings"].append(s.lstrip("# ").strip())
        elif s.strip() and not body_started:
            out["first_lines"].append(s.strip())
            if len(out["first_lines"]) >= 3:
                body_started = True
    return out


def scan(root):
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            if rel == os.path.basename(__file__):
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            ext = os.path.splitext(fn)[1].lower()
            info = {"rel": rel, "size": size, "ext": ext}
            if ext in TEXT_EXT and size < 2_000_000:
                info.update(read_headings(full))
            entries.append(info)
    entries.sort(key=lambda e: e["rel"])
    return entries


def build_tree(entries):
    tree = {}
    for e in entries:
        parts = e["rel"].split(os.sep)
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = None
    lines = []

    def walk(d, prefix=""):
        for k in sorted(d.keys()):
            lines.append(f"{prefix}{k}")
            if d[k] is not None:
                walk(d[k], prefix + "    ")
    walk(tree)
    return "\n".join(lines)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(root)
    print(f"# 扫描目录: {root}\n")
    entries = scan(root)
    if not entries:
        print("（目录为空，尚未发现任何文件。请把云盘文件下载到此处后重新运行。）")
        return
    print(f"## 文件总数: {len(entries)}\n")
    print("## 目录树\n")
    print(build_tree(entries))
    print("\n## 文件明细\n")
    for e in entries:
        size = human_size(e["size"])
        print(f"- [{e['rel']}]  ({size}, {e['ext'] or 'bin'})")
        for h in e.get("headings", [])[:6]:
            print(f"    - 标题: {h}")
        for fl in e.get("first_lines", [])[:2]:
            snippet = fl if len(fl) <= 80 else fl[:80] + "…"
            print(f"    - {snippet}")

    # 写总览
    md = [f"# game-wiki 索引（自动生成）\n", f"文件总数: {len(entries)}\n", "## 目录树\n", "```", build_tree(entries), "```\n", "## 文件明细\n"]
    for e in entries:
        size = human_size(e["size"])
        md.append(f"### {e['rel']}\n- 大小: {size} | 类型: {e['ext'] or 'bin'}\n")
        for h in e.get("headings", [])[:8]:
            md.append(f"  - {h}\n")
    out_path = os.path.join(root, "_INDEX.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n[已生成总览] {out_path}")
    # 同时输出 json 供程序消费
    with open(os.path.join(root, "_INDEX.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"[已生成 JSON] {os.path.join(root, '_INDEX.json')}")


if __name__ == "__main__":
    main()
