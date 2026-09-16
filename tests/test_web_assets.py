import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


class _MarkupCollector(HTMLParser):
    """收集 index.html 中的 id、class 与外部资源引用。"""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.classes: set[str] = set()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        for name in (attributes.get("class") or "").split():
            self.classes.add(name)
        if tag == "script" and attributes.get("src"):
            self.assets.append(attributes["src"])
        if tag == "link" and attributes.get("href"):
            self.assets.append(attributes["href"])


def _markup() -> _MarkupCollector:
    collector = _MarkupCollector()
    collector.feed((WEB / "index.html").read_text(encoding="utf-8"))
    return collector


def _selectors() -> list[tuple[str, str]]:
    """提取 app.js 中 $(...) 用到的 id 与 class 选择器。"""
    script = (WEB / "app.js").read_text(encoding="utf-8")
    found = re.findall(r'\$\(\s*"([#.])([A-Za-z0-9_-]+)"\s*\)', script)
    return found


class WebAssetTests(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = _markup().ids
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        self.assertEqual(duplicates, [], f"index.html 存在重复 id：{duplicates}")

    def test_app_js_id_selectors_resolve(self):
        known = set(_markup().ids)
        missing = sorted({name for kind, name in _selectors() if kind == "#"} - known)
        self.assertEqual(missing, [], f"app.js 引用了 index.html 中不存在的 id：{missing}")

    def test_app_js_class_selectors_resolve(self):
        known = _markup().classes
        missing = sorted({name for kind, name in _selectors() if kind == "."} - known)
        self.assertEqual(missing, [], f"app.js 引用了 index.html 中不存在的 class：{missing}")

    def test_referenced_assets_exist(self):
        for asset in _markup().assets:
            self.assertTrue((WEB / asset.lstrip("/")).is_file(), f"缺失前端资源：{asset}")


if __name__ == "__main__":
    unittest.main()
