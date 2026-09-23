"""导航链接必须按「当前页」的深度计算，而不是按链接目标的深度。

回归用例。早先 `_render_nav` 里游戏标题用的是 `index_page.prefix`——
链接目标自己的深度——于是侧边栏在每个页面都发出 `../<game>/`。
游戏首页恰好就是深度 1，所以在那 4 个页面上这条链接碰巧成立，
其余 53 个内容页的侧边导航整片 404。

这类 bug 的可怕之处在于：构建成功、页面能开、单元测试全绿、体积统计正常，
只有把每个 href 落到磁盘上才能发现。`gamewiki.checklinks` 是兜底，
这里的用例是让它不再复发。
"""

import re
import unittest
from pathlib import Path

from gamewiki.wiki import Page, _render_game_tabs, _render_nav, _url_for

SITE = {
    "games": [
        {"id": "dohna", "title": "多娜多娜", "groups": [{"id": "common", "title": "通用"}]},
        {"id": "p5r", "title": "P5R", "groups": [{"id": "palace", "title": "殿堂"}]},
    ]
}

_HREF = re.compile(r'href="([^"]+)"')


def _page(game, slug, title, output, prefix, group="common"):
    page = Page(
        game=game,
        slug=slug,
        title=title,
        group=group,
        order=1.0,
        summary="",
        body="",
        source=Path("content") / game / f"{slug}.md",
        output=output,
        prefix=prefix,
    )
    page.url = _url_for(page)
    return page


class NavPrefixTest(unittest.TestCase):
    def setUp(self):
        self.dohna_index = _page("dohna", "index", "多娜多娜", "dohna/index.html", "../", group="")
        self.deep = _page(
            "dohna", "characters", "角色", "dohna/characters/index.html", "../../"
        )
        self.p5r_index = _page("p5r", "index", "P5R", "p5r/index.html", "../", group="")
        self.pages = [self.dohna_index, self.deep, self.p5r_index]

    def test_nav_from_deep_page_uses_current_depth(self):
        hrefs = _HREF.findall(_render_nav(SITE, self.pages, self.deep))
        self.assertIn("../../p5r/", hrefs)
        self.assertIn("../../dohna/characters/", hrefs)
        for href in hrefs:
            self.assertTrue(
                href.startswith("../../"),
                f"深度 2 的页面不该发出 {href}（会落到站点目录之外）",
            )

    def test_nav_from_root_has_no_parent_escape(self):
        hrefs = _HREF.findall(_render_nav(SITE, self.pages, None))
        for href in hrefs:
            self.assertFalse(href.startswith("../"), f"站点首页不该回退到上层目录：{href}")
            self.assertTrue(href.startswith("./"), f"站点首页链接应以 ./ 开头：{href}")

    def test_game_tabs_follow_current_depth(self):
        deep_hrefs = _HREF.findall(_render_game_tabs(SITE, self.deep, self.pages))
        self.assertEqual(sorted(deep_hrefs), ["../../dohna/", "../../p5r/"])
        root_hrefs = _HREF.findall(_render_game_tabs(SITE, None, self.pages))
        self.assertEqual(sorted(root_hrefs), ["./dohna/", "./p5r/"])

    def test_every_game_link_survives_deeper_pages(self):
        """深度 3（未来可能出现的更细层级）也要跟着走。"""
        deeper = _page("dohna", "deep", "更深", "dohna/a/b/index.html", "../../../")
        hrefs = _HREF.findall(_render_nav(SITE, self.pages + [deeper], deeper))
        for href in hrefs:
            self.assertTrue(href.startswith("../../../"), f"{href} 没有按深度 3 回退")


if __name__ == "__main__":
    unittest.main()
