"""从 OOXML 容器（.docx / .xlsx）中抽取纯文本。

OOXML 文件本质是 ZIP 容器内含 XML 部件，因此仅用标准库即可取出可读文本，
既不需要第三方依赖，也不需要把任何内容写到磁盘。

安全边界：
- 只读容器内的命名部件，不落盘、不执行，宏与嵌入对象一律不解析。
- 容器体积、单部件解压后体积、输出字符数三层设限，抵御压缩炸弹。
- 含 DOCTYPE 声明的部件直接拒绝，避免实体扩展类攻击。
- 关系目标经归一化后必须存在于容器清单中，`..` 一律拒绝。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from .config import MAX_OOXML_ARCHIVE_BYTES, MAX_OOXML_MEMBER_BYTES, MAX_OOXML_TEXT_CHARS

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

DOCX = ".docx"
XLSX = ".xlsx"
SUPPORTED_EXTENSIONS = {DOCX, XLSX}

_DOCTYPE_SCAN_BYTES = 4096


class OoxmlError(Exception):
    """容器损坏、部件缺失或内容无法解析。"""


def extract_text(
    path: Path,
    extension: str,
    max_archive_bytes: int = MAX_OOXML_ARCHIVE_BYTES,
    max_member_bytes: int = MAX_OOXML_MEMBER_BYTES,
    max_chars: int = MAX_OOXML_TEXT_CHARS,
) -> str:
    """抽取 OOXML 文档的纯文本；无法解析时抛 OoxmlError。"""
    extension = extension.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise OoxmlError(f"不支持的 OOXML 类型：{extension}")

    try:
        archive_bytes = path.stat().st_size
    except OSError as error:
        raise OoxmlError("文件不可读") from error
    if archive_bytes > max_archive_bytes:
        raise OoxmlError(
            f"容器 {archive_bytes / 1048576:.1f} MB 超过上限 {max_archive_bytes // 1048576} MB"
        )

    try:
        with zipfile.ZipFile(path) as archive:
            text = (
                _docx_text(archive, max_member_bytes)
                if extension == DOCX
                else _xlsx_text(archive, max_member_bytes)
            )
    except zipfile.BadZipFile as error:
        raise OoxmlError("不是有效的 ZIP 容器") from error
    except ElementTree.ParseError as error:
        raise OoxmlError("XML 部件无法解析") from error
    except OSError as error:
        raise OoxmlError("文件读取失败") from error

    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n…（已截断，完整内容超过 {max_chars} 字符）"
    return text


def _read_member(archive: zipfile.ZipFile, name: str, max_member_bytes: int) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as error:
        raise OoxmlError(f"缺少部件：{name}") from error
    if info.file_size > max_member_bytes:
        raise OoxmlError(
            f"部件 {name} 解压后 {info.file_size / 1048576:.1f} MB，超过上限"
        )
    with archive.open(info) as stream:
        data = stream.read(max_member_bytes + 1)
    if len(data) > max_member_bytes:
        raise OoxmlError(f"部件 {name} 解压后超过上限")
    if b"<!DOCTYPE" in data[:_DOCTYPE_SCAN_BYTES]:
        raise OoxmlError(f"部件 {name} 含 DOCTYPE 声明，已拒绝解析")
    return data


def _docx_text(archive: zipfile.ZipFile, max_member_bytes: int) -> str:
    root = ElementTree.fromstring(_read_member(archive, "word/document.xml", max_member_bytes))
    paragraphs: list[str] = []
    for paragraph in root.iter(WORD + "p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == WORD + "t":
                parts.append(node.text or "")
            elif node.tag == WORD + "tab":
                parts.append("\t")
            elif node.tag in (WORD + "br", WORD + "cr"):
                parts.append("\n")
        paragraphs.append("".join(parts).strip())
    return "\n".join(paragraphs)


def _shared_strings(archive: zipfile.ZipFile, names: set[str], max_member_bytes: int) -> list[str]:
    if "xl/sharedStrings.xml" not in names:
        return []
    root = ElementTree.fromstring(_read_member(archive, "xl/sharedStrings.xml", max_member_bytes))
    return [
        "".join(node.text or "" for node in item.iter(SHEET + "t"))
        for item in root.iter(SHEET + "si")
    ]


def _normalize_target(target: str) -> str:
    target = target.replace("\\", "/").lstrip("/")
    if not target or ".." in target:
        return ""
    return target if target.startswith("xl/") else f"xl/{target}"


def _sheet_targets(
    archive: zipfile.ZipFile, names: set[str], max_member_bytes: int
) -> list[tuple[str, str]]:
    workbook = ElementTree.fromstring(_read_member(archive, "xl/workbook.xml", max_member_bytes))
    relationships: dict[str, str] = {}
    if "xl/_rels/workbook.xml.rels" in names:
        rel_root = ElementTree.fromstring(
            _read_member(archive, "xl/_rels/workbook.xml.rels", max_member_bytes)
        )
        for relation in rel_root:
            relationships[relation.get("Id", "")] = relation.get("Target", "")

    targets: list[tuple[str, str]] = []
    for index, sheet in enumerate(workbook.iter(SHEET + "sheet"), start=1):
        title = sheet.get("name") or f"Sheet{index}"
        candidate = _normalize_target(relationships.get(sheet.get(OFFICE_REL + "id", ""), ""))
        if candidate in names:
            targets.append((title, candidate))
    return targets


def _column_index(reference: str) -> int | None:
    letters = ""
    for char in reference:
        if "A" <= char.upper() <= "Z":
            letters += char.upper()
        else:
            break
    if not letters:
        return None
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return index - 1


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "s":
        raw = cell.find(SHEET + "v")
        if raw is None or raw.text is None:
            return ""
        try:
            return shared[int(raw.text)]
        except (ValueError, IndexError):
            return ""
    if kind == "inlineStr":
        node = cell.find(SHEET + "is")
        if node is None:
            return ""
        return "".join(text.text or "" for text in node.iter(SHEET + "t"))
    raw = cell.find(SHEET + "v")
    if raw is None or raw.text is None:
        return ""
    if kind == "b":
        return "TRUE" if raw.text == "1" else "FALSE"
    return raw.text


def _parse_range(reference: str) -> tuple[int, int, int, int] | None:
    """解析 `A2:C5` 形式的合并区域，返回 (起始列, 起始行, 结束列, 结束行)。"""
    match = re.match(r"^([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?$", reference.strip())
    if not match:
        return None
    first_column = _column_index(match.group(1))
    if first_column is None:
        return None
    first_row = int(match.group(2))
    if match.group(3):
        last_column = _column_index(match.group(3))
        last_row = int(match.group(4))
        if last_column is None:
            return None
    else:
        last_column, last_row = first_column, first_row
    return first_column, first_row, last_column, last_row


def _sheet_rows(
    archive: zipfile.ZipFile, target: str, shared: list[str], max_member_bytes: int
) -> list[list[str]]:
    """读取工作表为行列表（等宽、补空格）。

    合并单元格必须被填充：合成表里 `Lv` / `名称` 常跨多行合并，不填充的话
    表格会出现大片空白，读者无法判断哪一行属于哪个条目。
    """
    root = ElementTree.fromstring(_read_member(archive, target, max_member_bytes))
    grid: dict[int, dict[int, str]] = {}
    width = 0
    for position, row in enumerate(root.iter(SHEET + "row"), start=1):
        row_index = int(row.get("r") or position)
        cells: dict[int, str] = {}
        for cell_position, cell in enumerate(row.iter(SHEET + "c")):
            column = _column_index(cell.get("r") or "")
            cells[cell_position if column is None else column] = _cell_text(cell, shared)
        if not cells:
            continue
        grid[row_index] = cells
        width = max(width, max(cells) + 1)

    merged = root.find(SHEET + "mergeCells")
    if merged is not None:
        for item in merged.iter(SHEET + "mergeCell"):
            bounds = _parse_range(item.get("ref") or "")
            if bounds is None:
                continue
            first_column, first_row, last_column, last_row = bounds
            value = grid.get(first_row, {}).get(first_column, "")
            if not value:
                continue
            for row_index in range(first_row, last_row + 1):
                for column in range(first_column, last_column + 1):
                    grid.setdefault(row_index, {}).setdefault(column, value)

    return [
        [grid[row_index].get(column, "") for column in range(width)]
        for row_index in sorted(grid)
    ]


def _sheet_text(
    archive: zipfile.ZipFile, target: str, shared: list[str], max_member_bytes: int
) -> str:
    return "\n".join(
        "\t".join(row).rstrip() for row in _sheet_rows(archive, target, shared, max_member_bytes)
    )


def _xlsx_text(archive: zipfile.ZipFile, max_member_bytes: int) -> str:
    names = set(archive.namelist())
    shared = _shared_strings(archive, names, max_member_bytes)
    sections: list[str] = []
    for title, target in _sheet_targets(archive, names, max_member_bytes):
        body = _sheet_text(archive, target, shared, max_member_bytes)
        sections.append(f"# {title}\n{body}" if body else f"# {title}\n（空表）")
    if not sections:
        raise OoxmlError("容器中未找到可读工作表")
    return "\n\n".join(sections)


def extract_sheets(
    path: Path,
    extension: str = ".xlsx",
    max_archive_bytes: int = MAX_OOXML_ARCHIVE_BYTES,
    max_member_bytes: int = MAX_OOXML_MEMBER_BYTES,
) -> list[tuple[str, list[list[str]]]]:
    """把工作簿读成 `[(工作表名, 行列表)]`，供表格类 wiki 页面使用。

    与 `extract_text` 的区别：保留行列结构，因此调用方可以直接生成
    HTML/Markdown 表格，而不是拿到一堆制表符分隔的文本再猜列边界。
    """
    if extension.lower() != XLSX:
        raise OoxmlError(f"结构化表格读取仅支持 {XLSX}，收到 {extension}")

    try:
        archive_bytes = path.stat().st_size
    except OSError as error:
        raise OoxmlError("文件不可读") from error
    if archive_bytes > max_archive_bytes:
        raise OoxmlError(
            f"容器 {archive_bytes / 1048576:.1f} MB 超过上限 {max_archive_bytes // 1048576} MB"
        )

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            shared = _shared_strings(archive, names, max_member_bytes)
            sheets = [
                (title, _sheet_rows(archive, target, shared, max_member_bytes))
                for title, target in _sheet_targets(archive, names, max_member_bytes)
            ]
    except zipfile.BadZipFile as error:
        raise OoxmlError("不是有效的 ZIP 容器") from error
    except ElementTree.ParseError as error:
        raise OoxmlError("XML 部件无法解析") from error
    except OSError as error:
        raise OoxmlError("文件读取失败") from error

    if not sheets:
        raise OoxmlError("容器中未找到可读工作表")
    return sheets
