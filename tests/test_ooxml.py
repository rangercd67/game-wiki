import tempfile
import unittest
import zipfile
from pathlib import Path

from gamewiki.ooxml import OoxmlError, extract_text

WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

XML_HEAD = '<?xml version="1.0" encoding="UTF-8"?>'


def _docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    return (
        f'{XML_HEAD}<w:document xmlns:w="{WORD_NS}"><w:body>{body}</w:body></w:document>'
    ).encode("utf-8")


def _workbook(sheet_names: list[str], targets: list[str]) -> bytes:
    sheets = "".join(
        f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        f'{XML_HEAD}<workbook xmlns="{SHEET_NS}" xmlns:r="{REL_NS}">'
        f"<sheets>{sheets}</sheets></workbook>"
    ).encode("utf-8")


def _rels(targets: list[str]) -> bytes:
    items = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/worksheet" Target="{target}"/>'
        for index, target in enumerate(targets, start=1)
    )
    return f'{XML_HEAD}<Relationships xmlns="{PKG_REL_NS}">{items}</Relationships>'.encode("utf-8")


def _sheet(rows: str) -> bytes:
    return f'{XML_HEAD}<worksheet xmlns="{SHEET_NS}"><sheetData>{rows}</sheetData></worksheet>'.encode("utf-8")


def _shared(items: list[str]) -> bytes:
    entries = "".join(f"<si><t>{text}</t></si>" for text in items)
    return f'{XML_HEAD}<sst xmlns="{SHEET_NS}">{entries}</sst>'.encode("utf-8")


class _Fixture(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        self.addCleanup(self._temp.cleanup)

    def write(self, name: str, members: dict[str, bytes]) -> Path:
        path = self.root / name
        with zipfile.ZipFile(path, "w") as archive:
            for member, data in members.items():
                archive.writestr(member, data)
        return path


class DocxTests(_Fixture):
    def test_extracts_paragraphs(self):
        path = self.write("a.docx", {"word/document.xml": _docx("第一段", "第二段")})
        self.assertEqual(extract_text(path, ".docx"), "第一段\n第二段")

    def test_keeps_tabs_and_breaks(self):
        document = (
            f'{XML_HEAD}<w:document xmlns:w="{WORD_NS}"><w:body><w:p>'
            "<w:r><w:t>甲</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>乙</w:t></w:r>"
            "<w:r><w:br/></w:r><w:r><w:t>丙</w:t></w:r>"
            "</w:p></w:body></w:document>"
        ).encode("utf-8")
        path = self.write("b.docx", {"word/document.xml": document})
        self.assertEqual(extract_text(path, ".docx"), "甲\t乙\n丙")

    def test_missing_document_part(self):
        path = self.write("c.docx", {"word/styles.xml": b"<x/>"})
        with self.assertRaises(OoxmlError):
            extract_text(path, ".docx")


class XlsxTests(_Fixture):
    def members(self, rows: str, sheet_names=("Sheet1",), targets=("worksheets/sheet1.xml",),
                shared=()):
        payload = {
            "xl/workbook.xml": _workbook(list(sheet_names), list(targets)),
            "xl/_rels/workbook.xml.rels": _rels(list(targets)),
            f"xl/{targets[0]}": _sheet(rows),
        }
        if shared:
            payload["xl/sharedStrings.xml"] = _shared(list(shared))
        return payload

    def test_shared_strings_with_sparse_cells(self):
        rows = '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1"><v>42</v></c></row>'
        path = self.write("a.xlsx", self.members(rows, shared=["名称"]))
        self.assertEqual(extract_text(path, ".xlsx"), "# Sheet1\n名称\t\t42")

    def test_inline_string_and_boolean(self):
        rows = (
            '<row r="1"><c r="A1" t="inlineStr"><is><t>行内</t></is></c>'
            '<c r="B1" t="b"><v>1</v></c><c r="C1" t="b"><v>0</v></c></row>'
        )
        path = self.write("b.xlsx", self.members(rows))
        self.assertEqual(extract_text(path, ".xlsx"), "# Sheet1\n行内\tTRUE\tFALSE")

    def test_multiple_sheets_keep_names_and_order(self):
        payload = {
            "xl/workbook.xml": _workbook(["甲表", "乙表"],
                                         ["worksheets/sheet1.xml", "worksheets/sheet2.xml"]),
            "xl/_rels/workbook.xml.rels": _rels(["worksheets/sheet1.xml", "worksheets/sheet2.xml"]),
            "xl/worksheets/sheet1.xml": _sheet('<row r="1"><c r="A1"><v>1</v></c></row>'),
            "xl/worksheets/sheet2.xml": _sheet('<row r="1"><c r="A1"><v>2</v></c></row>'),
        }
        path = self.write("c.xlsx", payload)
        self.assertEqual(extract_text(path, ".xlsx"), "# 甲表\n1\n\n# 乙表\n2")

    def test_empty_sheet_is_labelled(self):
        path = self.write("d.xlsx", self.members(""))
        self.assertEqual(extract_text(path, ".xlsx"), "# Sheet1\n（空表）")

    def test_relationship_with_parent_traversal_is_rejected(self):
        payload = self.members('<row r="1"><c r="A1"><v>1</v></c></row>',
                               targets=("../evil.xml",))
        payload["evil.xml"] = _sheet('<row r="1"><c r="A1"><v>9</v></c></row>')
        path = self.write("e.xlsx", payload)
        with self.assertRaises(OoxmlError):
            extract_text(path, ".xlsx")


class GuardTests(_Fixture):
    def test_rejects_doctype_declaration(self):
        document = (
            f'{XML_HEAD}<!DOCTYPE x [<!ENTITY a "b">]>'
            f'<w:document xmlns:w="{WORD_NS}"><w:body><w:p><w:r><w:t>t</w:t></w:r></w:p>'
            "</w:body></w:document>"
        ).encode("utf-8")
        path = self.write("a.docx", {"word/document.xml": document})
        with self.assertRaises(OoxmlError):
            extract_text(path, ".docx")

    def test_rejects_oversized_archive(self):
        path = self.write("a.docx", {"word/document.xml": _docx("x")})
        with self.assertRaises(OoxmlError):
            extract_text(path, ".docx", max_archive_bytes=10)

    def test_rejects_oversized_member(self):
        path = self.write("a.docx", {"word/document.xml": _docx("x" * 5000)})
        with self.assertRaises(OoxmlError):
            extract_text(path, ".docx", max_member_bytes=100)

    def test_rejects_corrupt_container(self):
        path = self.root / "bad.docx"
        path.write_bytes(b"not a zip archive")
        with self.assertRaises(OoxmlError):
            extract_text(path, ".docx")

    def test_rejects_unsupported_extension(self):
        path = self.write("a.pptx", {"ppt/presentation.xml": b"<x/>"})
        with self.assertRaises(OoxmlError):
            extract_text(path, ".pptx")

    def test_truncates_long_output(self):
        path = self.write("a.docx", {"word/document.xml": _docx("字" * 999)})
        text = extract_text(path, ".docx", max_chars=100)
        self.assertTrue(text.startswith("字" * 100))
        self.assertIn("已截断", text)


if __name__ == "__main__":
    unittest.main()
