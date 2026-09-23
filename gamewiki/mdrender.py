"""极简 Markdown 渲染器（纯标准库）。

wiki 需要的是**可预测**的渲染，而不是完整的 CommonMark，因此这里只实现
攻略写作中真正会用到的语法子集，并且对不支持的语法保持「原样输出」，
而不是静默吞掉——内容作者能立刻看出哪里没生效。

支持的块级语法：
- 标题 `#`~`######`，自动生成锚点 id，可用 `{#custom-id}` 指定
- 段落，行尾两个空格表示强制换行
- 无序列表 `-` `*` `+` 与有序列表 `1.` `1)`，支持缩进嵌套
- 表格（管道语法，支持 `:---` / `---:` / `:---:` 对齐）
- 围栏代码块 ```` ``` ```` / `~~~`
- 引用 `>`（递归解析，适合做「注意事项」提示块）
- 分隔线 `---` `***` `___`

支持的行内语法：行内代码、图片、链接、粗体、斜体、删除线。

明确不支持：原始 HTML（会被转义后原样显示）、脚注、定义列表。
转义整篇文本后再解析，是为了让内容不可能注入标签。
"""

from __future__ import annotations

import re

__all__ = ["render", "inline", "slugify"]

# 不能用 html.escape：它会把 `>` 转成 `&gt;`，直接毁掉引用块语法。
# 只需要挡住标签注入（`<`）与实体注入（`&`）；`>` 在 HTML 文本里是合法的。
#
# 转义只做一次，发生在 render() 入口。因此 inline() 及其内部所有取值函数
# 拿到的字符串**已经是转义过的**，_attr 只补属性边界需要的 `"`，
# 绝不能再次调用 _text，否则 `&amp;` 会被放大成 `&amp;amp;`。
_ENTITY = {"&": "&amp;", "<": "&lt;"}
_ENTITY_RE = re.compile(r"[&<]")


def _text(value: str) -> str:
    """入口处的一次性转义。"""
    return _ENTITY_RE.sub(lambda match: _ENTITY[match.group(0)], value)


def _attr(value: str) -> str:
    """把已转义的文本放入双引号属性。"""
    return value.replace('"', "&quot;")

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*$")
_ANCHOR = re.compile(r"\s*\{#([A-Za-z0-9_-]+)\}$")
_HR = re.compile(r"^ {0,3}([-*_])[ \t]*(?:\1[ \t]*){2,}$")
_FENCE = re.compile(r"^ {0,3}(```+|~~~+)[ \t]*(\S*)[ \t]*$")
_QUOTE = re.compile(r"^ {0,3}>[ \t]?(.*)$")
_BULLET = re.compile(r"^(\s*)([-*+])[ \t]+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d{1,9})[.)][ \t]+(.*)$")
_TABLE_DELIM = re.compile(r"^ {0,3}\|?[ \t]*:?-{1,}:?[ \t]*(?:\|[ \t]*:?-{1,}:?[ \t]*)+\|?[ \t]*$")

_CODE_SPAN = re.compile(r"`([^`]+)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_STRONG = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
_EM = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])", re.S)
_DEL = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)

_PLACEHOLDER = "\x00{}\x00"


def slugify(text: str) -> str:
    """把标题转成锚点 id：保留字母数字与中日韩字符，其余折叠为连字符。

    ASCII 部分统一小写（中日韩字符不受 lower() 影响），与 GitHub 锚点惯例一致。
    """
    kept: list[str] = []
    for char in text.strip():
        if char.isalnum() or char in "-_":
            kept.append(char.lower())
        elif char.isspace():
            kept.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(kept)).strip("-")
    return slug or "section"


def inline(text: str) -> str:
    """渲染行内语法。

    入参必须是**已转义**的文本（render() 已处理）。单独调用时不会转义，
    因此不要用它处理未经 render() 的原始用户输入。
    """
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return _PLACEHOLDER.format(len(spans) - 1)

    text = _CODE_SPAN.sub(stash, text)

    def image(match: re.Match[str]) -> str:
        alt, src, title = match.group(1), match.group(2), match.group(3)
        attributes = f'src="{_attr(src)}" alt="{_attr(alt)}" loading="lazy" decoding="async"'
        if title:
            attributes += f' title="{_attr(title)}"'
        return f"<img {attributes}>"

    def link(match: re.Match[str]) -> str:
        label, href, title = match.group(1), match.group(2), match.group(3)
        attributes = f'href="{_attr(href)}"'
        if title:
            attributes += f' title="{_attr(title)}"'
        # 站外链接新窗口打开；站内（以 / 开头）保持同窗口。
        if href.startswith(("http://", "https://")):
            attributes += ' target="_blank" rel="noopener noreferrer"'
        return f"<a {attributes}>{label}</a>"

    text = _IMAGE.sub(image, text)
    text = _LINK.sub(link, text)
    text = _STRONG.sub(r"<strong>\1</strong>", text)
    text = _DEL.sub(r"<del>\1</del>", text)
    text = _EM.sub(r"<em>\1</em>", text)
    return re.sub(
        r"\x00(\d+)\x00",
        lambda match: f"<code>{spans[int(match.group(1))]}</code>",
        text,
    )


def _cell_split(line: str) -> list[str]:
    """按未转义的 `|` 拆单元格，支持 `\\|` 表示字面竖线。"""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", stripped)]


def _starts_block(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip():
        return True
    if _FENCE.match(line) or _HR.match(line) or _HEADING.match(line) or _QUOTE.match(line):
        return True
    if _BULLET.match(line) or _ORDERED.match(line):
        return True
    return "|" in line and index + 1 < len(lines) and bool(_TABLE_DELIM.match(lines[index + 1]))


def _table(lines: list[str], index: int) -> tuple[int, str]:
    header = _cell_split(lines[index])
    alignment = []
    for cell in _cell_split(lines[index + 1]):
        left, right = cell.startswith(":"), cell.endswith(":")
        alignment.append("center" if left and right else "left" if left else "right" if right else None)
    index += 2
    body: list[list[str]] = []
    while index < len(lines) and "|" in lines[index] and lines[index].strip():
        body.append(_cell_split(lines[index]))
        index += 1

    def row(cells: list[str], tag: str) -> str:
        out = []
        for position, cell in enumerate(cells):
            style = alignment[position] if position < len(alignment) else None
            attribute = f' style="text-align:{style}"' if style else ""
            out.append(f"<{tag}{attribute}>{inline(cell)}</{tag}>")
        return "<tr>" + "".join(out) + "</tr>"

    parts = ["<table>", "<thead>", row(header, "th"), "</thead>", "<tbody>"]
    parts.extend(row(cells, "td") for cells in body)
    parts.extend(["</tbody>", "</table>"])
    return index, "\n".join(parts)


def _list(lines: list[str], index: int) -> tuple[int, str]:
    """按缩进宽度递归解析列表，缩进更深的项成为子列表。"""
    first = _BULLET.match(lines[index]) or _ORDERED.match(lines[index])
    assert first is not None
    base_indent = len(first.group(1))
    ordered = _BULLET.match(lines[index]) is None

    items: list[tuple[str, list[str]]] = []
    while index < len(lines):
        match = _BULLET.match(lines[index]) or _ORDERED.match(lines[index])
        if not match:
            break
        indent = len(match.group(1))
        if indent < base_indent:
            break
        if indent > base_indent:
            if not items:
                break
            # 更深缩进：交给子列表解析
            index, nested = _list(lines, index)
            items[-1][1].append(nested)
            continue
        items.append((match.group(3), []))
        index += 1

    tag = "ol" if ordered else "ul"
    parts = [f"<{tag}>"]
    for text, children in items:
        # 子列表紧贴父项文本，避免在 <li> 内留下无意义的换行
        parts.append(f"<li>{inline(text)}{''.join(children)}</li>")
    parts.append(f"</{tag}>")
    return index, "\n".join(parts)


def _paragraph(lines: list[str]) -> str:
    """把连续行合成段落，行尾两个空格渲染为 <br>。"""
    chunks: list[str] = []
    previous_hard = False
    for position, line in enumerate(lines):
        hard = line.endswith("  ")
        if position:
            chunks.append("<br>" if previous_hard else " ")
        chunks.append(inline(line.strip()))
        previous_hard = hard
    return "<p>" + "".join(chunks) + "</p>"


def _blocks(lines: list[str]) -> str:
    out: list[str] = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        fence = _FENCE.match(line)
        if fence:
            marker, language = fence.group(1), fence.group(2)
            index += 1
            buffer: list[str] = []
            while index < total and not lines[index].strip().startswith(marker[0] * len(marker)):
                buffer.append(lines[index])
                index += 1
            index += 1  # 跳过闭合围栏
            attribute = f' class="language-{language}"' if language else ""
            out.append(f"<pre><code{attribute}>{chr(10).join(buffer)}</code></pre>")
            continue

        if _HR.match(line):
            out.append("<hr>")
            index += 1
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            raw = heading.group(2)
            anchor = _ANCHOR.search(raw)
            if anchor:
                identifier = anchor.group(1)
                raw = _ANCHOR.sub("", raw)
            else:
                identifier = slugify(raw)
            out.append(f'<h{level} id="{identifier}">{inline(raw.strip())}</h{level}>')
            index += 1
            continue

        if _QUOTE.match(line):
            buffer = []
            while index < total and (quoted := _QUOTE.match(lines[index])):
                buffer.append(quoted.group(1))
                index += 1
            out.append(f"<blockquote>{_blocks(buffer)}</blockquote>")
            continue

        if "|" in line and index + 1 < total and _TABLE_DELIM.match(lines[index + 1]):
            index, html = _table(lines, index)
            out.append(html)
            continue

        if _BULLET.match(line) or _ORDERED.match(line):
            index, html = _list(lines, index)
            out.append(html)
            continue

        buffer = []
        while index < total and lines[index].strip() and not _starts_block(lines, index):
            buffer.append(lines[index])
            index += 1
        out.append(_paragraph(buffer))

    return "\n".join(out)


def render(text: str) -> str:
    """把 Markdown 子集渲染为 HTML 片段。"""
    normalized = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    return _blocks(_text(normalized).split("\n"))
