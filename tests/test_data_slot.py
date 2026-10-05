"""数据表在正文里的落点。

`front-matter` 的 `data:` 表格默认被追加到正文末尾，于是它排在「内容出处」之后——
内容页读起来是倒的。正文里单独写一行 `:::data` 可以指定落点。

这里的用例锁住三件事：
1. 有占位符 → 就地替换，且占位符不再出现在产物里；
2. 没占位符 → 仍旧追加到末尾（老页面行为不变，别把现有页面改坏）；
3. 没有数据表（未声明 `data:` / `columns` 为空）→ 正文一个字都不动，
   并且正文里偶然出现的 `:::data` 文本也不会被吃掉。
"""

import unittest

from gamewiki.wiki import _place_data_table

TABLE = '<figure class="data-table"><table data-rows="1"></table></figure>'


class DataSlotTest(unittest.TestCase):
    def test_slot_is_replaced_in_place(self):
        body = "<p>前</p>\n<p>:::data</p>\n<p>后</p>"
        out = _place_data_table(body, TABLE)
        self.assertNotIn(":::data", out)
        self.assertLess(out.index(TABLE), out.index("<p>后</p>"))
        self.assertLess(out.index("<p>前</p>"), out.index(TABLE))

    def test_without_slot_appends_at_end(self):
        body = "<p>前</p>\n<p>后</p>"
        out = _place_data_table(body, TABLE)
        self.assertTrue(out.endswith(TABLE))
        self.assertTrue(out.startswith(body))

    def test_empty_table_leaves_body_untouched(self):
        body = "<p>前</p>\n<p>:::data</p>\n<p>后</p>"
        self.assertEqual(_place_data_table(body, ""), body)

    def test_inline_marker_text_is_not_consumed(self):
        """只有独立成段的占位符才算数，行内的 `:::data` 只是普通文本。"""
        body = "<p>见 :::data 的说明</p>"
        out = _place_data_table(body, TABLE)
        self.assertTrue(out.startswith(body))
        self.assertTrue(out.endswith(TABLE))


if __name__ == "__main__":
    unittest.main()
