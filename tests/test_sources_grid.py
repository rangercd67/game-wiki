"""《集批宝典》网格转写的测试。

这批素材是用电子表格**排图**而不是排表：合并单元格、多表并排、单元格位置即语义。
所以转写逻辑全在 `_grid_payload()` 里按 mode 分支，一个分支猜错就是整张表错位——
而且错得很安静（值还在，只是落到了别的列），所以这里逐模式锁住行为。
"""

import unittest

from gamewiki.sources import SheetGrid, _column_letter, _grid_payload, _trim_grid


def spec(**kwargs) -> SheetGrid:
    base = dict(slug="t", title="T", group="g", order=1, source="s.json", summary="")
    base.update(kwargs)
    return SheetGrid(**base)


class ColumnLetterTests(unittest.TestCase):
    def test_bijective_base26(self):
        # 列标必须与原文档一致，否则「按列标回原表对照」这条线索会断。
        self.assertEqual(_column_letter(0), "A")
        self.assertEqual(_column_letter(25), "Z")
        self.assertEqual(_column_letter(26), "AA")
        self.assertEqual(_column_letter(27), "AB")
        self.assertEqual(_column_letter(51), "AZ")
        self.assertEqual(_column_letter(52), "BA")


class TrimGridTests(unittest.TestCase):
    def test_drops_trailing_empties_only(self):
        # 首行保留：`grid` 模式的行号就是位置语义，裁掉首行会让行号整体偏移。
        rows = [[""], ["a", ""], ["b", ""], [""]]
        kept, width = _trim_grid(rows)
        self.assertEqual(len(kept), 3)
        self.assertEqual(width, 1)

    def test_short_rows_are_padded(self):
        _, width = _trim_grid([["a", "b", "c"], []])
        self.assertEqual(width, 3)

    def test_blank_grid(self):
        self.assertEqual(_trim_grid([[], []]), ([], 0))


class GridModeTests(unittest.TestCase):
    def test_rows_keep_original_numbers(self):
        # 中间的全空行会被跳过，但行号列必须仍是原文档行号——否则读者回原表会对不上。
        rows = [["", "", ""], ["x", "", ""], ["", "", ""], ["", "y", ""]]
        columns, body, _ = _grid_payload(spec(mode="grid"), rows, 3)
        self.assertEqual(columns, ["行", "A", "B", "C"])
        self.assertEqual([r[0] for r in body], ["2", "4"])


class HeaderModeTests(unittest.TestCase):
    def test_value_from_skips_leading_empty_column(self):
        # 坐标图最左边有一整列空的外框列，跳过后表头才是「坐标 / 1 / 2 …」。
        rows = [[""], ["", "坐标", "1", "2"], ["", "I", "出口", ""]]
        columns, body, _ = _grid_payload(spec(mode="header", header_row=1, value_from=1), rows, 4)
        self.assertEqual(columns, ["坐标", "1", "2"])
        self.assertEqual(body, [["I", "出口", ""]])

    def test_fill_down_carries_group_label(self):
        rows = [["", "d", "p"], ["", "day1", "A"], ["", "", "B"]]
        columns, body, _ = _grid_payload(
            spec(mode="header", header_row=0, value_from=1,
                 column_names=("日", "人"), fill_down=(0,)),
            rows, 3,
        )
        self.assertEqual(columns, ["日", "人"])
        self.assertEqual(body, [["day1", "A"], ["day1", "B"]])


class SectionsModeTests(unittest.TestCase):
    def test_union_of_headers_and_label_column(self):
        # 两块各有各的层数表头，合并成一张表：列取并集，块名进「分类」列。
        rows = [
            [],
            ["", "正常", "一层", "二层", "断章"],
            ["", "普通", "1", "2", ""],
            ["", "片瓣", "一层", "二层"],
            ["", "普通", "3", "4"],
        ]
        columns, body, _ = _grid_payload(
            spec(mode="sections", label_col=1, value_from=2,
                 blocks=(("正常", 1, 3), ("片瓣", 3, 5))),
            rows, 5,
        )
        self.assertEqual(columns, ["分类", "项目", "一层", "二层", "断章"])
        self.assertEqual(body, [["正常", "普通", "1", "2", ""],
                                ["片瓣", "普通", "3", "4", ""]])


class MatrixModeTests(unittest.TestCase):
    def test_group_row_disambiguates_repeated_categories(self):
        # 表头行写的是大类（我方增益占三列），同一大类占多列时加序号，否则列名会重复。
        rows = [
            [],
            ["", "", "制表", "我方增益", "", "", "敌方减益"],
            ["", "", "二星", "A", "B", "C", "D"],
        ]
        columns, body, _ = _grid_payload(
            spec(mode="matrix", header_row=1, group_row=1, key_col=2, value_from=3,
                 row_blocks=((2, 3),), column_names=("星级",)),
            rows, 7,
        )
        self.assertEqual(
            columns, ["星级", "我方增益·1", "我方增益·2", "我方增益·3", "敌方减益"]
        )
        self.assertEqual(body, [["二星", "A", "B", "C", "D"]])

    def test_blank_header_becomes_unmarked(self):
        rows = [[], ["", "", "h", "A", ""], ["", "", "一星", "x", "y"]]
        columns, _, _ = _grid_payload(
            spec(mode="matrix", header_row=1, key_col=2, value_from=3,
                 row_blocks=((2, 3),), column_names=("星级",)),
            rows, 5,
        )
        self.assertEqual(columns, ["星级", "A", "未标注"])

    def test_skip_values_drops_colour_legend(self):
        rows = [[], ["", "", "h", "A"], ["", "", "一星", "x"], ["", "", "", "蓝字：图例"]]
        _, body, _ = _grid_payload(
            spec(mode="matrix", header_row=1, key_col=2, value_from=3,
                 row_blocks=((2, 4),), column_names=("星级",), skip_values=("蓝字：",)),
            rows, 4,
        )
        self.assertEqual(body, [["一星", "x"]])


class MeltModeTests(unittest.TestCase):
    def test_blocks_become_label_name_pairs(self):
        rows = [[], ["", "甲", "a", "b"], ["", "", "c"]]
        columns, body, _ = _grid_payload(
            spec(mode="melt", value_from=2, blocks=(("甲", 1, 3),),
                 column_names=("分类", "藏品")),
            rows, 4,
        )
        self.assertEqual(columns, ["分类", "藏品"])
        self.assertEqual(body, [["甲", "a"], ["甲", "b"], ["甲", "c"]])

    def test_credit_cell_never_becomes_data(self):
        rows = [[], ["", "甲", "a", "制表人 哲三"]]
        _, body, _ = _grid_payload(
            spec(mode="melt", value_from=2, blocks=(("甲", 1, 2),)),
            rows, 4,
        )
        self.assertEqual(body, [["甲", "a"]])

    def test_row_pairs_take_header_row_as_names(self):
        rows = [[], ["", "", "", "藏品甲", "藏品乙"], ["", "", "", "6", "7"]]
        _, body, _ = _grid_payload(
            spec(mode="melt", value_from=3, row_pairs=((1, 2),),
                 column_names=("藏品", "次数")),
            rows, 5,
        )
        self.assertEqual(body, [["藏品甲", "6"], ["藏品乙", "7"]])


class PairsModeTests(unittest.TestCase):
    def test_group_marker_restarts_layer_fill_down(self):
        # 「普通 / 紧急」是分节标记，不该被当成层名向下填充。
        rows = [
            [],
            ["", "", "普通"],
            ["", "", "一层", "甲", "22"],
            ["", "", "二层", "乙", "38"],
            ["", "", "紧急"],
            ["", "", "一层", "甲", "21"],
        ]
        columns, body, _ = _grid_payload(
            spec(mode="pairs", label_col=2, pair_from=3, pair_width=2,
                 group_markers=((1, "普通"), (4, "紧急")),
                 column_names=("难度", "层", "节点", "出怪数")),
            rows, 5,
        )
        self.assertEqual(columns, ["难度", "层", "节点", "出怪数"])
        self.assertEqual(body, [["普通", "一层", "甲", "22"],
                                ["普通", "二层", "乙", "38"],
                                ["紧急", "一层", "甲", "21"]])

    def test_orphan_number_swap_vs_drop(self):
        rows = [[], ["", "", "一层", "甲", "26", "神出鬼没", "27", "28"]]
        common = dict(mode="pairs", label_col=2, pair_from=3, pair_width=2,
                      column_names=("层", "节点", "编号"))
        _, swapped, _ = _grid_payload(spec(**common, orphan_numbers="swap"), rows, 8)
        self.assertEqual(swapped, [["一层", "甲", "26"], ["一层", "神出鬼没", "27"],
                                   ["一层", "", "28"]])
        _, dropped, _ = _grid_payload(spec(**common, orphan_numbers="drop"), rows, 8)
        self.assertEqual(dropped, [["一层", "甲", "26"], ["一层", "神出鬼没", "27"]])

    def test_credit_cell_in_name_slot_is_dropped(self):
        rows = [[], ["", "", "一层", "甲", "22", "制表人 哲三", ""]]
        _, body, _ = _grid_payload(
            spec(mode="pairs", label_col=2, pair_from=3, pair_width=2,
                 column_names=("层", "节点", "出数")),
            rows, 7,
        )
        self.assertEqual(body, [["一层", "甲", "22"]])


if __name__ == "__main__":
    unittest.main()
