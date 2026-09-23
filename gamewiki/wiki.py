"""把 Markdown 内容源渲染成静态 wiki 站点。

与 `gamewiki.build`（文件索引器）是两条独立的轨道：那一条产出「资料清单」，
这一条产出「攻略页面」。wiki 的产物是页面、导航与站内搜索，因此这里
不复用索引器的任何页面逻辑，只共用图片管道与静态托管约定。

内容源约定：

```
content/
  site.json              站点标题与各游戏的分组定义
  media.json             图片映射（输出名 → library 内相对路径），避免把原图塞进 git
  p5r/                   一个游戏一个目录
    index.md             该游戏首页 → dist/p5r/index.html
    palace-shido.md      普通页面   → dist/p5r/palace-shido/index.html
```

页面用 front-matter 声明元数据：

```
---
title: 色欲的城堡（鸭志田）
group: palace
order: 1
summary: 鸭志田殿堂全楼层走法与欲石位置。
---
```

`group` 对应 site.json 里该游戏的分组 id；`order` 决定组内顺序（缺省按标题）。
Markdown 中以 `/` 开头的链接与图片会被改写为相对当前页面深度的路径，
因此同一份产物既能部署在站点根目录，也能部署在 `example.com/repo/` 子目录。
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import PROJECT_ROOT
from .mdrender import render

CONTENT_ROOT = PROJECT_ROOT / "content"
WIKI_ROOT = PROJECT_ROOT / "wiki"
DEFAULT_OUTPUT = PROJECT_ROOT / "dist-wiki"
MEDIA_DIR = "media"
ASSET_DIR = "assets"
DATA_DIR = "data"
FALLBACK_GROUP = ("other", "其他")
# content/ 下的保留目录：存放数据文件与资源，不是游戏目录，扫描时静默跳过
RESERVED_DIRS = {"data", "media", "assets", "_drafts"}

_FRONT_MATTER = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)
_REBASE = re.compile(r'(?P<attr>href|src)="/(?!/)')
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


@dataclass
class Page:
    """一个 wiki 页面。"""

    game: str
    slug: str
    title: str
    group: str
    order: float
    summary: str
    body: str
    source: Path
    output: str = ""           # 相对 dist 的输出路径，如 p5r/palace-shido/index.html
    prefix: str = "./"         # 回到站点根的相对前缀
    url: str = ""
    html: str = ""
    text: str = ""
    updated: str = ""
    prev: "Page | None" = None
    next: "Page | None" = None
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def is_index(self) -> bool:
        return self.slug == "index"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """拆分 front-matter 与正文。

    只支持扁平的 `key: value`，不引入 YAML 依赖：wiki 的元数据就是这么简单，
    一个只读一半的 YAML 解析器反而容易埋坑。
    """
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[match.end():]


def to_plain_text(markup: str) -> str:
    """把渲染后的 HTML 压成搜索用的纯文本。"""
    text = _TAG.sub(" ", markup)
    return _SPACE.sub(" ", html.unescape(text)).strip()


def _depth(output: str) -> int:
    """输出文件相对 dist 的目录层数，用于计算回退到根的前缀。"""
    return len(Path(output).parent.parts)


def collect_pages(content_root: Path, site: dict) -> tuple[list[Page], list[str]]:
    """扫描内容源，返回页面列表与告警。"""
    warnings: list[str] = []
    games = site.get("games", [])
    known_games = {game["id"]: game for game in games}
    pages: list[Page] = []

    for directory in sorted(p for p in content_root.iterdir() if p.is_dir()):
        game_id = directory.name
        if game_id in RESERVED_DIRS:
            continue
        if game_id not in known_games:
            warnings.append(f"目录 content/{game_id}/ 未在 site.json 的 games 中声明，已跳过")
            continue
        for source in sorted(directory.rglob("*.md")):
            meta, body = parse_front_matter(source.read_text(encoding="utf-8"))
            relative = source.relative_to(directory).with_suffix("")
            slug = meta.get("slug") or relative.as_posix().replace("/", "-")
            group = meta.get("group", "")
            valid_groups = {item["id"] for item in known_games[game_id].get("groups", [])}
            if group and group not in valid_groups:
                warnings.append(
                    f"{source.relative_to(content_root).as_posix()} 的 group={group!r} "
                    f"未在 site.json 中定义，已归入「{FALLBACK_GROUP[1]}」"
                )
                group = FALLBACK_GROUP[0]
            try:
                order = float(meta.get("order", "nan"))
            except ValueError:
                warnings.append(
                    f"{source.relative_to(content_root).as_posix()} 的 order 不是数字，已忽略"
                )
                order = float("nan")

            output = (
                f"{game_id}/index.html" if slug == "index" else f"{game_id}/{slug}/index.html"
            )
            page = Page(
                game=game_id,
                slug=slug,
                title=meta.get("title") or relative.name,
                group=group or FALLBACK_GROUP[0],
                order=order,
                summary=meta.get("summary", ""),
                body=body,
                source=source,
                output=output,
                prefix="../" * _depth(output) or "./",
                extra=meta,
            )
            page.updated = datetime.fromtimestamp(
                source.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d")
            pages.append(page)

    for page in pages:
        page.url = _url_for(page)

    # 同组内按 order 排序，order 缺失的排在后面并按标题排
    def sort_key(page: Page) -> tuple:
        missing = page.order != page.order  # NaN 判定
        return (1 if missing else 0, 0.0 if missing else page.order, page.title)

    for game_id in known_games:
        for group_id, _ in _groups_for(site, game_id):
            bucket = [p for p in pages if p.game == game_id and p.group == group_id]
            bucket.sort(key=sort_key)
            for position, page in enumerate(bucket):
                page.prev = bucket[position - 1] if position else None
                page.next = bucket[position + 1] if position + 1 < len(bucket) else None

    return pages, warnings


def _url_for(page: Page) -> str:
    """站点根相对 URL，用于导航与站内链接。"""
    return "/" + page.output.replace("index.html", "")


def _groups_for(site: dict, game_id: str) -> list[tuple[str, str]]:
    for game in site.get("games", []):
        if game["id"] == game_id:
            return [(item["id"], item["title"]) for item in game.get("groups", [])]
    return []


def build_media(content_root: Path, output: Path, library: Path) -> dict:
    """按 content/media.json 把原图处理进 dist/media/，返回统计。

    刻意不把图片放进内容源：原图合计上百 MB，进 git 会让仓库无法使用。
    构建时从 library 取、按需缩放重编码，产物体积可控且可随时重建。
    """
    mapping = _load_json(content_root / "media.json")
    stats = {"written": 0, "missing": 0, "bytes": 0, "failed": 0}
    if not mapping:
        return stats

    try:
        from PIL import Image
    except ImportError:
        Image = None  # type: ignore[assignment]

    for name, spec in mapping.items():
        source = library / (spec["source"] if isinstance(spec, dict) else spec)
        target = output / MEDIA_DIR / name
        if not source.is_file():
            stats["missing"] += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)

        max_edge = int(spec.get("max_edge", 0)) if isinstance(spec, dict) else 0
        if max_edge and Image is not None:
            try:
                with Image.open(source) as image:
                    image.load()
                    if max(image.size) > max_edge:
                        scale = max_edge / max(image.size)
                        image = image.resize(
                            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                            Image.LANCZOS,
                        )
                    if target.suffix.lower() == ".png":
                        image.save(target, format="PNG", optimize=True)
                    else:
                        image.convert("RGB").save(
                            target, format="JPEG", quality=88, optimize=True, progressive=True
                        )
                stats["written"] += 1
                stats["bytes"] += target.stat().st_size
                continue
            except Exception:
                stats["failed"] += 1
                # 缩放失败就退回原样复制，宁可大一点也不要缺图
        shutil.copy2(source, target)
        stats["written"] += 1
        stats["bytes"] += target.stat().st_size
    return stats


def _render_nav(site: dict, pages: list[Page], current: Page | None) -> str:
    """渲染侧边导航：游戏 → 分组 → 页面。"""
    current_url = _url_for(current) if current else ""
    parts: list[str] = []
    for game in site.get("games", []):
        game_pages = [p for p in pages if p.game == game["id"]]
        if not game_pages:
            continue
        index_page = next((p for p in game_pages if p.is_index), None)
        parts.append('<div class="nav-game">')
        heading = html.escape(game["title"])
        if index_page:
            parts.append(
                f'<a class="nav-game-title" href="{_rel(index_page.prefix, _url_for(index_page))}">'
                f"{heading}</a>"
            )
        else:
            parts.append(f'<span class="nav-game-title">{heading}</span>')

        listed: set[str] = set()
        for group_id, group_title in _groups_for(site, game["id"]):
            bucket = [p for p in game_pages if p.group == group_id and not p.is_index]
            if not bucket:
                continue
            listed.update(p.slug for p in bucket)
            parts.append(f'<div class="nav-group"><span>{html.escape(group_title)}</span><ul>')
            for page in bucket:
                active = ' class="active"' if page.url == current_url else ""
                href = _rel(current.prefix if current else "./", _url_for(page))
                parts.append(
                    f'<li><a href="{href}"{active}>{html.escape(page.title)}</a></li>'
                )
            parts.append("</ul></div>")

        orphans = [p for p in game_pages if not p.is_index and p.slug not in listed]
        if orphans:
            parts.append('<div class="nav-group"><span>未分组</span><ul>')
            for page in sorted(orphans, key=lambda p: p.title):
                href = _rel(current.prefix if current else "./", _url_for(page))
                parts.append(f'<li><a href="{href}">{html.escape(page.title)}</a></li>')
            parts.append("</ul></div>")
        parts.append("</div>")
    return "\n".join(parts)


def _rel(prefix: str, url: str) -> str:
    """把站点根相对 URL 转成相对当前页面的路径。"""
    return prefix + url.lstrip("/")


def _render_game_tabs(site: dict, current: Page | None, pages: list[Page]) -> str:
    parts = []
    for game in site.get("games", []):
        game_pages = [p for p in pages if p.game == game["id"]]
        if not game_pages:
            continue
        index_page = next((p for p in game_pages if p.is_index), None)
        if index_page is None:
            continue
        active = ' class="active"' if current and current.game == game["id"] else ""
        href = _rel(current.prefix if current else "./", _url_for(index_page))
        parts.append(f'<a href="{href}"{active}>{html.escape(game["title"])}</a>')
    return "\n".join(parts)


def _render_data_table(content_root: Path, page: Page) -> str:
    """渲染 front-matter `data:` 指向的结构化表格。

    上千行的图鉴表格不该内联进 Markdown：那样内容源既没法读也没法改。
    数据留在 JSON 里，由生成器转成 HTML，并交给前端做筛选。
    """
    name = page.extra.get("data")
    if not name:
        return ""
    path = content_root / DATA_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"{page.source.name} 声明的数据文件不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    columns = payload.get("columns", [])
    rows = payload.get("rows", [])
    if not columns:
        return ""

    def escape_cell(value: object) -> str:
        return html.escape(str(value))

    head = "".join(f"<th>{escape_cell(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{escape_cell(row[i]) if i < len(row) else ''}</td>"
                        for i in range(len(columns)))
        body.append(f"<tr>{cells}</tr>")
    caption = payload.get("caption", "")
    caption_html = f"<caption>{escape_cell(caption)}</caption>" if caption else ""
    return (
        '<figure class="data-table">'
        f'<table data-rows="{len(rows)}">{caption_html}<thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
        "</figure>"
    )


def _render_page_nav(page: Page) -> str:
    """组内上一页 / 下一页，用于攻略的连续阅读。"""
    if not page.prev and not page.next:
        return ""
    parts = ['<nav class="page-nav">']
    if page.prev:
        parts.append(
            f'<a class="prev" href="{_rel(page.prefix, page.prev.url)}">'
            f'<small>← 上一页</small><strong>{html.escape(page.prev.title)}</strong></a>'
        )
    else:
        parts.append("<span></span>")
    if page.next:
        parts.append(
            f'<a class="next" href="{_rel(page.prefix, page.next.url)}">'
            f'<small>下一页 →</small><strong>{html.escape(page.next.title)}</strong></a>'
        )
    parts.append("</nav>")
    return "\n".join(parts)


def _fill_template(template: str, values: dict[str, str]) -> str:
    """`{{key}}` 占位替换；未提供的键保持原样，便于发现模板与代码不一致。"""
    def replace(match: re.Match[str]) -> str:
        return values.get(match.group(1), match.group(0))

    return re.sub(r"\{\{([a-z_]+)\}\}", replace, template)


def build(
    content: Path = CONTENT_ROOT,
    output: Path = DEFAULT_OUTPUT,
    library: Path | None = None,
    domain: str | None = None,
    clean: bool = True,
) -> dict:
    """生成静态 wiki，返回构建清单。"""
    from .config import DEFAULT_SOURCE

    library = library or DEFAULT_SOURCE
    content, output = Path(content), Path(output)
    site = _load_json(content / "site.json")
    if not site.get("games"):
        raise ValueError(f"{content / 'site.json'} 缺少 games 定义，无法生成导航")

    if clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    pages, warnings = collect_pages(content, site)
    template = (WIKI_ROOT / "page.html").read_text(encoding="utf-8")
    (output / ASSET_DIR).mkdir(parents=True, exist_ok=True)
    for asset in sorted((WIKI_ROOT / "assets").iterdir()):
        shutil.copy2(asset, output / ASSET_DIR / asset.name)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    if domain:
        (output / "CNAME").write_text(domain.strip() + "\n", encoding="utf-8")

    for page in pages:
        body_html = render(page.body) + _render_data_table(content, page)
        page.html = _REBASE.sub(lambda m: f'{m.group("attr")}="{page.prefix}', body_html)
        page.text = to_plain_text(body_html)

    # 页面
    for page in pages:
        target = output / page.output
        target.parent.mkdir(parents=True, exist_ok=True)
        game = next(g for g in site["games"] if g["id"] == page.game)
        values = {
            "lang": site.get("lang", "zh-CN"),
            "site_title": site.get("title", "Wiki"),
            "site_subtitle": site.get("subtitle", ""),
            "title": page.title,
            "description": page.summary or f"{page.title} · {site.get('title', 'Wiki')}",
            "prefix": page.prefix,
            "nav": _render_nav(site, pages, page),
            "game_tabs": _render_game_tabs(site, page, pages),
            "content": page.html,
            "breadcrumb_game": html.escape(game["title"]),
            "breadcrumb_title": html.escape(page.title),
            "updated": page.updated,
            "page_nav": _render_page_nav(page),
            "footer": site.get("footer", ""),
        }
        target.write_text(_fill_template(template, values), encoding="utf-8")

    # 站点首页：游戏列表
    if pages:
        template_home = template
        root_prefix = "./"
        cards = []
        for game in site["games"]:
            game_pages = [p for p in pages if p.game == game["id"]]
            if not game_pages:
                continue
            index_page = next((p for p in game_pages if p.is_index), game_pages[0])
            groups = []
            for group_id, group_title in _groups_for(site, game["id"]):
                bucket = [p for p in game_pages if p.group == group_id and not p.is_index]
                if not bucket:
                    continue
                links = "".join(
                    f'<li><a href="{_rel(root_prefix, p.url)}">{html.escape(p.title)}</a></li>'
                    for p in bucket[:8]
                )
                more = (
                    f'<li class="more">另有 {len(bucket) - 8} 页</li>' if len(bucket) > 8 else ""
                )
                groups.append(
                    f'<div class="home-group"><h3>{html.escape(group_title)}</h3>'
                    f"<ul>{links}{more}</ul></div>"
                )
            cards.append(
                f'<section class="home-game"><h2>'
                f'<a href="{_rel(root_prefix, _url_for(index_page))}">{html.escape(game["title"])}</a>'
                f"</h2>"
                f'<p class="home-meta">{len(game_pages) - 1} 个页面</p>'
                f'<div class="home-groups">{"".join(groups)}</div></section>'
            )
        values = {
            "lang": site.get("lang", "zh-CN"),
            "site_title": site.get("title", "Wiki"),
            "site_subtitle": site.get("subtitle", ""),
            "title": site.get("title", "Wiki"),
            "description": site.get("description", site.get("subtitle", "")),
            "prefix": root_prefix,
            "nav": _render_nav(site, pages, None),
            "game_tabs": _render_game_tabs(site, None, pages),
            "content": "\n".join(cards),
            "breadcrumb_game": "",
            "breadcrumb_title": "首页",
            "updated": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "page_nav": "",
            "footer": site.get("footer", ""),
        }
        (output / "index.html").write_text(_fill_template(template_home, values), encoding="utf-8")

    # 站内搜索索引
    search = [
        {
            "title": page.title,
            "url": _url_for(page),
            "game": page.game,
            "group": page.group,
            "summary": page.summary,
            "text": page.text[:1500],
        }
        for page in pages
    ]
    (output / "search.json").write_text(
        json.dumps(search, ensure_ascii=False), encoding="utf-8")

    media = build_media(content, output, library)

    manifest = {
        "built_at": datetime.now(tz=timezone.utc).isoformat(),
        "pages": len(pages),
        "by_game": {game["id"]: sum(1 for p in pages if p.game == game["id"])
                    for game in site.get("games", [])},
        "media": media,
        "site_bytes": sum(p.stat().st_size for p in output.rglob("*") if p.is_file()),
        "warnings": warnings,
        "output": str(output),
    }
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="把 Markdown 内容源渲染成静态 wiki")
    parser.add_argument("--content", type=Path, default=CONTENT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--library", type=Path, default=None)
    parser.add_argument("--domain", default=None, help="写入 CNAME，例如 xiaomenghua.top")
    parser.add_argument("--keep", action="store_true", help="不清理输出目录")
    args = parser.parse_args()

    manifest = build(args.content, args.output, args.library, args.domain, clean=not args.keep)
    print(
        f"构建完成：{manifest['pages']} 个页面，"
        f"图片 {manifest['media']['written']} 张（缺失 {manifest['media']['missing']}），"
        f"站点 {manifest['site_bytes'] / 1048576:.2f} MB → {manifest['output']}"
    )
    for warning in manifest["warnings"]:
        print(f"  警告：{warning}")


if __name__ == "__main__":
    main()
