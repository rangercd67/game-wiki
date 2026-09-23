"""检查构建产物里的站内引用是否都指向真实存在的文件。

静态站点最容易出的问题不是构建报错，而是**静默的死链**：构建成功、页面能开，
但某张图 404。改图片投递格式（PNG → WebP）时就属于这一类——内容源里写的是
`.png`，磁盘上是 `.webp`，只有把每个 `src` 落到实处才能证明没写坏。

除了死链，还检查两条本项目的硬性约定：

1. 产物里不允许出现根路径引用（`href="/..."` / `src="/..."`）。
   一旦出现，站点就无法部署在 `example.com/repo/` 这类子路径下。
2. 顶层不允许有下划线开头的文件——GitHub Pages 的 Jekyll 会把它吞掉。

用法：

    py -m gamewiki.checklinks                    # 默认检查 dist-wiki/
    py -m gamewiki.checklinks --output dist      # 指定产物目录
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

from .config import PROJECT_ROOT

DEFAULT_OUTPUT = PROJECT_ROOT / "dist-wiki"
_ATTR = re.compile(r'(?:href|src)\s*=\s*"([^"]*)"', re.I)
_SKIP_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:", "#")


def _is_external(target: str) -> bool:
    return not target or target.startswith(_SKIP_PREFIXES)


def check(output: Path) -> tuple[list[str], list[str], int]:
    """返回（死链, 约定违规, 检查过的引用数）。"""
    dead: list[str] = []
    violations: list[str] = []
    checked = 0

    pages = sorted(output.rglob("*.html"))
    for page in pages:
        relative_page = page.relative_to(output)
        text = page.read_text(encoding="utf-8", errors="replace")
        for raw in _ATTR.findall(text):
            target = raw.strip()
            if _is_external(target):
                continue
            checked += 1

            # 根路径引用：部署到子目录时会全部 404
            if target.startswith("/"):
                violations.append(f"{relative_page} → {target}（根路径引用，子目录部署会失效）")
                continue

            path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not path:
                continue
            resolved = (page.parent / path).resolve()
            try:
                exists = resolved.exists()
            except OSError:
                exists = False
            if not exists:
                dead.append(f"{relative_page} → {target}")

    for entry in sorted(output.iterdir()):
        if entry.name.startswith("_") and entry.name != ".nojekyll":
            violations.append(f"{entry.name}（顶层下划线开头，Jekyll 会忽略）")

    return dead, violations, checked


def main() -> None:
    parser = argparse.ArgumentParser(description="检查静态产物的站内引用")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = Path(args.output)
    if not output.is_dir():
        raise SystemExit(f"产物目录不存在：{output}")

    dead, violations, checked = check(output)
    print(f"检查完成：{len(list(output.rglob('*.html')))} 个页面，{checked} 条站内引用")

    for label, items in (("死链", dead), ("约定违规", violations)):
        if not items:
            continue
        print(f"\n{label} {len(items)} 条：")
        for item in items[:40]:
            print(f"  {item}")
        if len(items) > 40:
            print(f"  …另有 {len(items) - 40} 条")

    if dead or violations:
        raise SystemExit(1)
    print("站内引用全部有效，且未出现根路径引用。")


if __name__ == "__main__":
    main()
