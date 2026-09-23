"""Markdown 渲染器的行为测试。

渲染器是内容管道的地基：它要是静默出错，40 多个攻略页面会一起错，
而且错在「看起来还行」的地方，所以这里逐条锁住语法行为。
"""

import unittest

from gamewiki.mdrender import inline, render, slugify


class InlineTests(unittest.TestCase):
    """inline() 契约：入参已转义，只负责行内排版与属性边界。"""

    def test_code_span_protects_emphasis_markers(self):
        # 行内代码里的 * 不能被当成强调，否则技能名「*特攻」会被吃掉。
        html = inline("`*特攻` 与 **粗体**")
        self.assertIn("<code>*特攻</code>", html)
        self.assertIn("<strong>粗体</strong>", html)

    def test_image_before_link(self):
        html = inline("![地图](/media/a.png)")
        self.assertEqual(
            html, '<img src="/media/a.png" alt="地图" loading="lazy" decoding="async">'
        )

    def test_external_link_gets_target_blank(self):
        html = inline("[出处](https://www.psnine.com/topic/31361)")
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_internal_link_stays_same_window(self):
        self.assertNotIn("target=", inline("[殿堂](/p5r/palace-shido/)"))

    def test_attribute_quotes_are_escaped(self):
        html = inline('[链接](https://example.com/a"b)')
        self.assertIn('href="https://example.com/a&quot;b"', html)

    def test_already_escaped_ampersand_is_not_double_escaped(self):
        # render() 已把 & 转成 &amp;，inline 不能再动它，否则会变成 &amp;amp;
        html = inline("[x](https://example.com/?a=1&amp;b=2)")
        self.assertIn("&amp;b=2", html)
        self.assertNotIn("&amp;amp;", html)


class EscapingTests(unittest.TestCase):
    """转义发生在 render() 入口，必须恰好一次。"""

    def test_angle_brackets_are_escaped(self):
        # 内容是游戏攻略，出现 < > 很正常，不能变成标签。
        html = render("HP < 50% 且 SP > 30\n")
        self.assertIn("HP &lt; 50%", html)
        self.assertIn("SP > 30", html)

    def test_raw_html_is_neutralised(self):
        html = render("<script>alert(1)</script>\n")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script>", html)

    def test_link_ampersand_escaped_once_in_full_pipeline(self):
        html = render('[x](https://example.com/?a=1&b=2 "标题")\n')
        self.assertIn("&amp;b=2", html)
        self.assertNotIn("&amp;amp;", html)


class SlugifyTests(unittest.TestCase):
    def test_chinese_is_preserved(self):
        self.assertEqual(slugify("数据图鉴"), "数据图鉴")

    def test_punctuation_is_dropped(self):
        # 与 GitHub 的锚点行为一致：标点丢弃，空格折叠为连字符。
        self.assertEqual(slugify("色欲的城堡（鸭志田）"), "色欲的城堡鸭志田")

    def test_spaces_become_separator(self):
        self.assertEqual(slugify("P5R Skills"), "p5r-skills")

    def test_empty_falls_back(self):
        self.assertEqual(slugify("!!! ???"), "section")


class BlockTests(unittest.TestCase):
    def test_headings_get_anchor_ids(self):
        html = render("## 推荐面具选择\n")
        self.assertEqual(html, '<h2 id="推荐面具选择">推荐面具选择</h2>')

    def test_explicit_anchor_overrides_slug(self):
        html = render("## 推荐面具选择 {#recommended}\n")
        self.assertIn('id="recommended"', html)
        self.assertNotIn("{#recommended}", html)

    def test_table_alignment_and_body(self):
        html = render("| 日期 | 答案 |\n| :--- | ---: |\n| 4.18 | 全日制教育 |\n")
        self.assertIn('<th style="text-align:left">日期</th>', html)
        self.assertIn('<th style="text-align:right">答案</th>', html)
        self.assertIn('<td style="text-align:left">4.18</td>', html)
        self.assertIn('<td style="text-align:right">全日制教育</td>', html)

    def test_table_without_alignment_has_no_style(self):
        html = render("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        self.assertIn("<td>1</td>", html)

    def test_delimiter_row_is_not_rendered_as_content(self):
        html = render("| 日期 | 答案 |\n| --- | --- |\n| 4.18 | 全日制教育 |\n")
        self.assertNotIn("---", html)

    def test_escaped_pipe_inside_cell(self):
        html = render("| a | b |\n| --- | --- |\n| x \\| y | z |\n")
        self.assertIn("<td>x | y</td>", html)

    def test_horizontal_rule_is_not_a_table(self):
        self.assertEqual(render("---\n"), "<hr>")

    def test_blockquote_wraps_paragraph(self):
        html = render("> 难度建议 safety 或 easy\n")
        self.assertIn("<blockquote><p>难度建议 safety 或 easy</p></blockquote>", html)

    def test_nested_list(self):
        html = render("- 前期\n  - 战车\n  - 命运\n- 后期\n")
        self.assertEqual(
            html,
            "<ul>\n<li>前期<ul>\n<li>战车</li>\n<li>命运</li>\n</ul></li>\n<li>后期</li>\n</ul>",
        )

    def test_list_item_has_no_trailing_newline(self):
        html = render("1. 找千早使用禁忌 天运占卜\n2. 去印象空间瞬杀\n")
        self.assertIn("<li>找千早使用禁忌 天运占卜</li>", html)
        self.assertIn("<ol>", html)

    def test_fenced_code_keeps_markdown_literal(self):
        html = render("```\n**不渲染**\n```\n")
        self.assertEqual(html, "<pre><code>**不渲染**</code></pre>")

    def test_fenced_code_with_language(self):
        self.assertIn('<code class="language-python">', render("```python\nx=1\n```\n"))

    def test_hard_break_from_trailing_spaces(self):
        self.assertIn("<br>", render("第一行  \n第二行\n"))

    def test_paragraph_stops_at_list(self):
        html = render("说明文字\n- 项目\n")
        self.assertIn("<p>说明文字</p>", html)
        self.assertIn("<ul>", html)

    def test_blank_document(self):
        self.assertEqual(render(""), "")

    def test_table_after_paragraph_is_detected(self):
        # 段落里出现竖线不应吞掉后面的表格
        html = render("提示：见下表\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        self.assertIn("<table>", html)
        self.assertIn("<p>提示：见下表</p>", html)


if __name__ == "__main__":
    unittest.main()
