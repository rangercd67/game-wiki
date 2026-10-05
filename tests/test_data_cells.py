"""数据表的单元格是**纯文本**，不能写 Markdown。

`_render_data_table()` 对每个格子走 `html.escape()`，所以：

* `**粗体**` 会原样显示成星号；
* `[文字](/dohna/xxx/)` 会原样显示成方括号，而且 `checklinks` 扫不到它——
  既难看又漏检，是「看起来成功了」的静默错误。

内容源里数据表越写越多（多娜多娜的掉落表、徽章表都是几百行），
靠人眼复查不现实，因此把这条约定固化成用例：**所有 data/*.json 的
caption / 表头 / 单元格里都不许出现 Markdown 标记**。
需要问号或链接时，把解释写在页面的 Markdown 正文里。
"""

import json
import unittest
from pathlib import Path

from gamewiki.config import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "content" / "data"
FORBIDDEN = ("**", "](", "`", "|", "<a ", "<strong>")
PLAIN_TEXT_KEYS = ("caption", "columns", "rows")


def _walk(value, path, sink):
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk(item, f"{path}[{index}]", sink)
    elif isinstance(value, dict):
        for key, item in value.items():
            _walk(item, f"{path}.{key}", sink)
    elif isinstance(value, str):
        for mark in FORBIDDEN:
            if mark in value:
                sink.append((path, mark, value[:80]))


class DataCellTest(unittest.TestCase):
    def test_no_markdown_in_cells(self):
        files = sorted(DATA_DIR.rglob("*.json"))
        self.assertTrue(files, "content/data 下没有找到任何数据文件")

        problems: list[tuple[str, str, str]] = []
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for key in PLAIN_TEXT_KEYS:
                if key in payload:
                    _walk(payload[key], f"{path.name}:{key}", problems)

        detail = "\n".join(f"  {where} 含 {mark!r} → {text}" for where, mark, text in problems)
        self.assertEqual(problems, [], f"数据表单元格里出现了 Markdown 标记：\n{detail}")


if __name__ == "__main__":
    unittest.main()
