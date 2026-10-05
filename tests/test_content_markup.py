"""内容源渲染后不得漏出字面标记。

渲染器刻意对不认识的写法「原样输出」——作者能立刻看出哪里没生效，
但这意味着一个没闭合的 `**`、或者跨行书写的行内标记，
会**直接印在页面上**。这类问题在构建日志里完全看不出来，只能靠产物扫描。

这里把整棵 `content/` 树的正文渲染一遍，断言产物里不出现字面标记。
保留目录（`_*` 与 `data/`）跳过，它们不是页面。

配套的渲染器行为锁在 `tests/test_mdrender.py`：
跨行标记与列表项缩进续行的正确性由那组用例保证，这里只兜「产物脏了」。
"""

import pathlib
import unittest

from gamewiki.mdrender import render
from gamewiki.wiki import parse_front_matter

CONTENT = pathlib.Path(__file__).resolve().parent.parent / "content"
RESERVED = {"data", "media", "assets"}

# 渲染后仍出现即为「没生效」的字面标记
LEAKS = {
    "**": "粗体没闭合",
    "`": "行内代码没闭合",
    "~~": "删除线没闭合",
    "![": "图片语法没生效",
    "](": "链接 / 图片语法没生效",
    "| --- |": "表格分隔行没被吃掉",
}


def page_sources() -> list[pathlib.Path]:
    out = []
    for path in sorted(CONTENT.rglob("*.md")):
        parts = path.relative_to(CONTENT).parts
        if any(part in RESERVED or part.startswith("_") for part in parts):
            continue
        out.append(path)
    return out


class ContentMarkupTest(unittest.TestCase):
    def test_content_tree_is_not_empty(self):
        self.assertGreater(len(page_sources()), 50, "内容源没扫到页面，路径判断可能失效")

    def test_no_literal_markup_leaks_into_output(self):
        failures: list[str] = []
        for path in page_sources():
            _, body = parse_front_matter(path.read_text(encoding="utf-8"))
            html = render(body)
            for marker, why in LEAKS.items():
                if marker not in html:
                    continue
                line = next(
                    (i + 1 for i, text in enumerate(body.split("\n")) if marker in render(text)),
                    0,
                )
                failures.append(
                    "%s:%s 漏出 %r（%s）"
                    % (path.relative_to(CONTENT).as_posix(), line, marker, why)
                )
        self.assertEqual(failures, [], "渲染产物里有没生效的标记：\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
