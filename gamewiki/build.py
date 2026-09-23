"""把索引渲染成可托管的静态站点。

GitHub Pages 只提供静态文件、不支持任何服务端语言，因此本模块把「运行时」
的能力搬到「构建时」：索引、分类统计与单文件预览全部预先生成为静态资源，
前端不再需要 `/api/*`。

内容范围由 `content` 参数控制，便于先跑通流程、后决定上线范围：

- `none`   只生成目录与元数据，不发布任何正文与图片
- `text`   额外发布可转文本的正文（`.txt`/`.md`/… 与 `.docx`/`.xlsx` 的抽取结果）
- `thumbs` 在 `text` 基础上额外发布图片缩略图（最长边降到 1600px）
- `all`    在 `text` 基础上额外发布图片原文件

输出一律使用相对路径（`./styles.css`），以便同时适配用户站点
（`example.com/`）与项目站点（`example.com/repo/`）两种部署形态。

构建时无法发布正文的文件不会被静默忽略：条目上会带 `preview_note`，
写明原因（源文件缺失 / 超过体积上限 / 文档无法解析 / 当前内容范围未覆盖），
由前端呈现为禁用按钮上的提示。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DEFAULT_DATABASE,
    DEFAULT_SOURCE,
    MAX_IMAGE_PREVIEW_BYTES,
    MAX_OOXML_ARCHIVE_BYTES,
    MAX_TEXT_PREVIEW_BYTES,
    OOXML_PREVIEW_EXTENSIONS,
    PROJECT_ROOT,
    TEXT_PREVIEW_EXTENSIONS,
    preview_kind,
)

WEB_ROOT = PROJECT_ROOT / "web"
DEFAULT_OUTPUT = PROJECT_ROOT / "dist"
CONTENT_MODES = ("none", "text", "thumbs", "all")
THUMB_MAX_EDGE = 1600
THUMB_QUALITY = 82
PREVIEW_DIR = "data/preview"
MEDIA_DIR = "media"


def preview_key(relative_path: str) -> str:
    """为相对路径生成稳定且文件名安全的键（中文路径直接进 URL 易出错）。"""
    return hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:16]


def _read_shell() -> str:
    """读取站点外壳，把绝对路径改写为相对路径并标记静态模式。

    相对路径是硬要求：同一份产物既要能放在用户站点根目录（`example.com/`），
    也要能放在项目站点子目录（`example.com/repo/`）。
    """
    shell = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
    shell = shell.replace('href="/styles.css"', 'href="./styles.css"')
    shell = shell.replace('src="/app.js"', 'src="./app.js"')
    shell = shell.replace('href="/" aria-label', 'href="./" aria-label')
    shell = shell.replace('<html lang="zh-CN">', '<html lang="zh-CN" data-wiki-mode="static">')
    return shell


def _text_payload(path: Path, extension: str) -> tuple[str | None, str | None]:
    """返回 (正文, 未发布原因)，二者恰好一个非空。

    体积上限与本地服务保持一致：否则一个超大文本会被整体内联进 JSON，
    把构建产物撑到无法托管。
    """
    try:
        size = path.stat().st_size
    except OSError as error:
        return None, f"源文件不可读（{error.strerror or error}）"

    if extension in TEXT_PREVIEW_EXTENSIONS:
        if size > MAX_TEXT_PREVIEW_BYTES:
            return None, f"文本超过 {MAX_TEXT_PREVIEW_BYTES // 1048576} MB，仅保留元数据"
        return path.read_text(encoding="utf-8", errors="replace"), None

    if extension in OOXML_PREVIEW_EXTENSIONS:
        if size > MAX_OOXML_ARCHIVE_BYTES:
            return None, f"文档超过 {MAX_OOXML_ARCHIVE_BYTES // 1048576} MB，仅保留元数据"
        from .ooxml import OoxmlError, extract_text

        try:
            return extract_text(path, extension), None
        except OoxmlError as error:
            return None, f"文档无法解析：{error}"

    return None, "此类型不提供正文"


def _write_image(source: Path, target_stem: Path, thumbnail: bool) -> tuple[Path | None, str | None]:
    """写出一张图片资源，返回 (实际文件, 失败原因)。"""
    try:
        size = source.stat().st_size
    except OSError as error:
        return None, f"源文件不可读（{error.strerror or error}）"

    if size > MAX_IMAGE_PREVIEW_BYTES:
        return None, f"图片超过 {MAX_IMAGE_PREVIEW_BYTES // 1048576} MB，仅保留元数据"

    target_stem.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()

    if not thumbnail:
        target = target_stem.with_suffix(suffix)
        try:
            shutil.copy2(source, target)
        except OSError as error:
            return None, f"复制失败（{error.strerror or error}）"
        return target, None

    try:
        from PIL import Image
    except ImportError:
        return None, "构建环境缺少 Pillow，无法生成缩略图"

    try:
        with Image.open(source) as image:
            image.load()
            if max(image.size) > THUMB_MAX_EDGE:
                scale = THUMB_MAX_EDGE / max(image.size)
                image = image.resize(
                    (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                    Image.LANCZOS,
                )
            # PNG 保留原生编码，其余格式统一转 JPEG（含透明通道的一律拍平底色）。
            if suffix == ".png":
                target = target_stem.with_suffix(".png")
                image.save(target, format="PNG", optimize=True)
            else:
                target = target_stem.with_suffix(".jpg")
                image.convert("RGB").save(
                    target, format="JPEG", quality=THUMB_QUALITY, optimize=True, progressive=True
                )
        return target, None
    except Exception as error:  # Pillow 对损坏文件的报错类型很杂，这里统一降级
        return None, f"缩略图生成失败（{type(error).__name__}）"


def build(
    output: Path = DEFAULT_OUTPUT,
    database: Path = DEFAULT_DATABASE,
    source: Path = DEFAULT_SOURCE,
    content: str = "text",
    domain: str | None = None,
    clean: bool = True,
) -> dict:
    """生成静态站点，返回构建清单（同时写入 output/build-manifest.json）。"""
    if content not in CONTENT_MODES:
        raise ValueError(f"content 必须是 {CONTENT_MODES} 之一，收到 {content!r}")

    output = Path(output)
    if clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        kinds = [dict(row) for row in connection.execute(
            "SELECT kind, COUNT(*) count FROM files GROUP BY kind ORDER BY count DESC")]
        games = [dict(row) for row in connection.execute(
            "SELECT game, COUNT(*) count, SUM(size) size FROM files "
            "GROUP BY game ORDER BY count DESC, game COLLATE NOCASE")]
        rows = [dict(row) for row in connection.execute(
            "SELECT id, relative_path, name, extension, kind, size, modified_ns, modified_at, game "
            "FROM files ORDER BY modified_ns DESC, name COLLATE NOCASE")]
    finally:
        connection.close()

    # 站点外壳与前端资源
    (output / "index.html").write_text(_read_shell(), encoding="utf-8")
    for asset in ("styles.css", "app.js"):
        shutil.copy2(WEB_ROOT / asset, output / asset)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    if domain:
        (output / "CNAME").write_text(domain.strip() + "\n", encoding="utf-8")

    files: list[dict] = []
    published_text = published_image = 0
    unavailable = missing_source = 0
    text_bytes = image_bytes = 0

    for row in rows:
        relative = row["relative_path"]
        absolute = Path(source) / relative
        extension = row["extension"]
        wants = preview_kind(extension)
        present = absolute.is_file()
        if not present:
            missing_source += 1

        entry = dict(row)
        entry["preview"] = None
        entry["preview_key"] = None
        entry["url"] = None
        entry["preview_note"] = None

        if wants is None:
            entry["preview_note"] = "此类型不提供内容预览"
            files.append(entry)
            continue

        if not present:
            entry["preview_note"] = "源文件缺失，站点中无内容"
            files.append(entry)
            continue

        if content == "none":
            entry["preview_note"] = "当前构建为纯目录快照，未发布内容"
            files.append(entry)
            continue

        if wants == "text":
            # 正文：text / thumbs / all 三种范围都发布
            payload, note = _text_payload(absolute, extension)
            if payload is None:
                entry["preview_note"] = note
                unavailable += 1
            else:
                key = preview_key(relative)
                target = output / PREVIEW_DIR / f"{key}.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    json.dumps({"path": relative, "type": "text", "content": payload},
                               ensure_ascii=False),
                    encoding="utf-8",
                )
                entry["preview"] = "text"
                entry["preview_key"] = key
                published_text += 1
                text_bytes += target.stat().st_size
        elif content == "text":
            # 图片：thumbs 出缩略图，all 出原文件，text 范围不含图片
            entry["preview_note"] = "当前内容范围不含图片，仅保留元数据"
        else:
            key = preview_key(relative)
            written, note = _write_image(
                absolute, output / MEDIA_DIR / key, thumbnail=(content == "thumbs")
            )
            if written is None:
                entry["preview_note"] = note
                unavailable += 1
            else:
                entry["preview"] = "image"
                entry["preview_key"] = key
                entry["url"] = f"./{written.relative_to(output).as_posix()}"
                published_image += 1
                image_bytes += written.stat().st_size

        files.append(entry)

    library = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "content_mode": content,
        "metadata": metadata,
        "kinds": kinds,
        "games": games,
        "files": files,
    }
    data_dir = output / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "library.json").write_text(
        json.dumps(library, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "built_at": library["generated_at"],
        "content_mode": content,
        "source": str(source),
        "files_total": len(files),
        "published_text": published_text,
        "published_image": published_image,
        "unavailable": unavailable,
        "missing_source": missing_source,
        "text_bytes": text_bytes,
        "image_bytes": image_bytes,
        "site_bytes": sum(p.stat().st_size for p in output.rglob("*") if p.is_file()),
        "output": str(output),
    }
    (output / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="把索引渲染成静态站点")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--content", choices=CONTENT_MODES, default="text")
    parser.add_argument("--domain", default=None, help="写入 CNAME，例如 xiaomenghua.top")
    parser.add_argument("--keep", action="store_true", help="不清理输出目录（增量覆盖）")
    args = parser.parse_args()

    manifest = build(args.output, args.database, args.source,
                     args.content, args.domain, clean=not args.keep)
    print(
        f"构建完成：{manifest['files_total']} 条索引，"
        f"正文 {manifest['published_text']} 个，图片 {manifest['published_image']} 个，"
        f"未发布 {manifest['unavailable']} 个，源文件缺失 {manifest['missing_source']} 个，"
        f"站点 {manifest['site_bytes'] / 1048576:.2f} MB → {manifest['output']}"
    )


if __name__ == "__main__":
    main()
