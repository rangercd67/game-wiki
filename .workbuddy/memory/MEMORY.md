# game-wiki 项目长期笔记

## 项目定位

**内容型攻略 wiki**（挂载到用户自己的网站 + GitHub Pages），参考形态：
`wiki.biligame.com/persona`——左侧分组导航树 + 页面正文 + 数据表格 + 图集 + 站内搜索。

> 历史包袱：`gamewiki/indexer.py` + `server.py` + `web/` + `build.py` 是早期的
> 「本地文件索引/预览器」，与 wiki 目标无关。已停在可用状态，不再投入，也不要
> 因为它的存在而把 wiki 需求往「文件管理」方向带。

## 架构：三段式管道

```
library/            原始素材（只读，不动）
   ↓ gamewiki/sources.py      声明式清单驱动
content/            内容源（Markdown + data/*.json + media.json + site.json）
   ↓ gamewiki/wiki.py         渲染 + 导航 + 搜索 + 图片管道
dist-wiki/          静态站点（部署产物）
```

## 目录约定

| 路径 | 说明 |
| --- | --- |
| `content/site.json` | 站点标题 + `games[]`，每个 game 带自己的 `groups[]`（分组按游戏不同） |
| `content/<game>/index.md` | 游戏首页 → `dist-wiki/<game>/index.html` |
| `content/<game>/<slug>.md` | 普通页面 → `dist-wiki/<game>/<slug>/index.html` |
| `content/data/<game>/<name>.json` | 结构化表格数据，被 front-matter `data: <game>/<name>` 引用 |
| `content/media.json` | 图片映射 `输出名 → library 相对路径`，**图片不进 git** |
| `content/_*/`、`data/` | 保留目录，扫描时静默跳过（`RESERVED_DIRS`） |

## 页面 front-matter

```
---
title: 页面标题
group: <site.json 里该游戏的分组 id>
order: 1            # 组内排序，缺省按标题
summary: 摘要       # 用于导航搜索与 SEO
data: <game>/<name> # 可选，引用结构化表格
---
```

## 硬性技术约定

1. **零第三方依赖**（Pillow 可选，仅用于图片缩放；缺失时降级为原样复制）。
2. **输出一律相对路径**。内容里写 `/media/x.png`，生成器按页面深度改写。
   禁止产出 `href="/..."`（已验证脚本检查违规数必须为 0）。
3. **转义只做一次**，在 `mdrender.render()` 入口，且用自定义 `_text()`
   （`&`→`&amp;`、`<`→`&lt;`），**不能用 `html.escape`**——它会把 `>` 变成 `&gt;`，
   毁掉引用块语法。`inline()` 的契约是「入参已转义」。
4. **大表格走 `content/data/`**，不要内联进 Markdown（上千行会毁掉内容源可读性）。
5. **素材编码必须探测**：UTF-8 → GB18030 → Big5 回退。GBK 文件用 UTF-8 读会静默乱码。
6. **表格留空列按需向下填充**（`fill_down`），但必须按列声明：
   合成表的 `Lv`/`名称` 空白是「同上」，掉落列的空白是「无掉落」。
7. **署名与出处必须保留**。素材多为他人在 B 站/贴吧/日站整理的成果，
   公开站点若不保留出处即侵权。导入器会自动摘出署名行并渲染为页面底部出处块。
8. **不编数据**。公开来源只有标题没有数值时，页面写「资料缺口」而不是估算填充。
9. 素材目录名/工作表名找不到时**报错跳过并记录**，不要猜。

## 内容边界（多娜多娜等成人向游戏）

- 只收录系统与数值类资料：角色定位、武器类型与机制、章节分支、地图掉落、设施。
- 不撰写露骨性内容，不做性化角色的页面。
- 属性名与阈值可作数值描述，但不写「如何优化性剥削」类的养成攻略。

## 命令

```bash
# 素材 → 内容源（幂等，可重复执行）
python -m gamewiki.sources
# 内容源 → 静态站点
python -m gamewiki.wiki                     # 输出 dist-wiki/
python -m gamewiki.wiki --domain xiaomenghua.top   # 附带写 CNAME
# 测试
python -m unittest discover -s tests -t .
# 本地预览
cd dist-wiki && python -m http.server 8099 --bind 127.0.0.1
```

## 用户偏好

- UI：极简医学风格，≤2 主色（科技蓝 `#0EA5E9` / 活力绿 `#22C55E`），背景 `#F0F7F7`，
  圆角 12px，无衬线。深浅双主题只切表面与文字色，主色不变。
- 沟通：先确认目标产物形态再动手；用户对方向性错误容忍度极低。
- 部署目标：GitHub Pages + 自有域名 `xiaomenghua.top`。
