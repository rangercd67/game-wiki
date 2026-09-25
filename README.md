# Game Wiki · 藏经阁

**内容型攻略 Wiki**——左侧分组导航树 + 页面正文 + 数据表格 + 图集 + 站内搜索，
形态参考 [wiki.biligame.com/persona](https://wiki.biligame.com/persona)。
构建产物是纯静态站点，可直接挂到 GitHub Pages 或自有域名。

## 目录边界

- 工作目录：`D:\Development\Projects\game-wiki`
- 素材库：`library/`——原始攻略、图集、表格，**不纳入 Git**（多为他人作品且体积上百 MB）
- 内容源：`content/`——由素材导入而来的 Markdown、结构化表格与图片映射，**纳入 Git**
- 历史外部源：`E:\Games\GameTools` 已不再参与索引，仅作个人归档保留

## 架构：三段式管道

```
library/          原始素材（只读，不动）
   ↓  python -m gamewiki.sources     声明式清单驱动导入
content/          Markdown + data/*.json + media.json + site.json
   ↓  python -m gamewiki.wiki        渲染 + 导航 + 搜索 + 图片管道
dist-wiki/        静态站点（部署产物，不进 Git）
```

## 目录约定

| 路径 | 说明 |
| --- | --- |
| `content/site.json` | 站点标题 + `games[]`，每个 game 带自己的 `groups[]`（分组按游戏不同） |
| `content/<game>/index.md` | 游戏首页 → `dist-wiki/<game>/index.html` |
| `content/<game>/<slug>.md` | 普通页面 → `dist-wiki/<game>/<slug>/index.html` |
| `content/data/<game>/<name>.json` | 结构化表格数据，被 front-matter `data: <game>/<name>` 引用 |
| `content/media.json` | 图片映射 `输出名 → library 相对路径`，**图片不进 Git** |
| `wiki/page.html`、`wiki/assets/` | 页面模板与前端资源 |

页面 front-matter：

```yaml
---
title: 页面标题
group: <site.json 里该游戏的分组 id>
order: 1            # 组内排序，缺省按标题
summary: 摘要       # 用于导航搜索与 SEO
data: <game>/<name> # 可选，引用结构化表格
---
```

## 快速开始

环境要求：Python 3.11 或更高版本。**运行时零第三方依赖**；Pillow 为可选项，
只用于图片缩放，缺失时降级为原样复制。

```powershell
# 素材 → 内容源（幂等，可重复执行）
py -m gamewiki.sources

# 内容源 → 静态站点（输出 dist-wiki/）
py -m gamewiki.wiki

# 附带写 CNAME，用于自定义域名（本例绑在域名根目录）
py -m gamewiki.wiki --domain wiki.example.com

# 沿用素材原始格式（默认会把 PNG 转 WebP，体积约为原来的 1/4）
py -m gamewiki.wiki --image-format keep

# 检查产物里的站内引用（死链、根路径引用、Jekyll 隐患）
py -m gamewiki.checklinks

# 本地预览
cd dist-wiki; py -m http.server 8099 --bind 127.0.0.1
```

## 数据导入

素材形态不同，导入链也不同，都收敛在 `gamewiki/sources.py` 的声明式清单里，
**改数据不改代码**：

| 素材形态 | 声明方式 | 用途 |
| --- | --- | --- |
| 多工作表 xlsx | `Workbook` | 每个工作表抽成一张表 |
| 长文 / 图片目录 | `Document` / `Gallery` | 正文与图集 |
| 在线表格导出网格 | `SheetGrid` | 明日方舟《集批宝典》23 个子表 |

`SheetGrid` 支持 7 种取数模式，对应在线表格里常见的排版：

| mode | 场景 |
| --- | --- |
| `grid` | 原样网格，保留原表行号列标，空白即原表留空 |
| `header` | 首行是表头，跳过前置空列 |
| `sections` | 多段「小节 → 键值」结构 |
| `matrix` | 二维交叉表，单元格内的竖排列表合并为顿号 |
| `melt` | 宽表转长表（列名当属性） |
| `pairs` | 两列一组，按编号配对 |
| `placeholder` | 原文档只给了图，建页标注资料缺口 |

几条自己踩出来的规矩，写在 README 里是为了别再踩一次：

- **素材编码必须探测**：UTF-8 → GB18030 → Big5 回退。GBK 文件用 UTF-8 读会**静默**乱码。
- **留空列按需向下填充**，但必须按列声明——合成表的 `Lv`/`名称` 空白是「同上」，
  掉落列的空白是「无掉落」，两者不能一概而论。
- **不编数据**。公开来源只有标题没有数值时，页面写「资料缺口」而不是估算填充。
- 素材目录名 / 工作表名匹配不上时**报错跳过并记录**，不要猜。

## 测试

```powershell
py -m unittest discover -s tests -t .
```

无需网络与第三方依赖。覆盖自研 Markdown 渲染器的转义、表格对齐、列表嵌套等边界
（`test_mdrender.py`），导航链接的深度计算（`test_nav_prefix.py`），`SheetGrid` 的
7 种取数模式与引号/空行/参差行的边界（`test_sources_grid.py`），以及早期预览器
`web/index.html` 与 `web/app.js` 的选择器自洽性（`test_web_assets.py`）。

## 已收录游戏

| 游戏 | 页面数 | 内容 |
| --- | --- | --- |
| 多娜多娜 一起做坏事吧 | 4 | 系统概览、角色定位、武器类型与机制、章节分支 |
| 女神异闻录 5 皇家版 | 20 | 殿堂走法地图、印象空间、面具合成、日程、社群 |
| 女神异闻录 3 携带版 | 13 | 男女主双线日程、全面具合成、装备获取 |
| 女神异闻录 4 黄金版 | 19 | 流程、技能卡、支线任务、成就 |
| 明日方舟 · 集成战略 | 27 | 黑流树海误入奇境、界园合订本与藏品、通用机制数值、仙术杯#6 赛事数据 |

> 明日方舟部分的数据源是腾讯文档《集批宝典》的 23 个子表，由
> `gamewiki/sources.py` 里的声明式 `SheetGrid` 清单导入（见「数据导入」一节）。
> 其中 2 个子表原文档只给了图，页面为占位并标注资料缺口，不做推测性重绘。

## 部署

线上站点：**<https://rangercd67.github.io/game-wiki/>**

站点为纯静态产物，只用相对路径，因此放在域名根目录或子路径下都能正确工作——
上面这个地址就挂在 `/game-wiki/` 子路径下，没有绑自定义域名。
发布走独立的 `gh-pages` 分支，`main` 只保留源码。

```powershell
py -m gamewiki.deploy --remote https://github.com/<user>/<repo>.git
```

发布前会自动跑一遍站内引用检查，**有死链就拒绝推送**——死链在本地很难被发现，
上线却是对外可见的破损。`--dry-run` 只提交不推送。

第一次推送约 20 MB（其中图片约 17 MB）。之后是普通快进推送，git 按内容去重，
未改动的图片不会重复上传，日常只改 HTML 时推送量在 1 MB 以内。

站点由 `gh-pages` 分支直接发布（Pages 的 `build_type=legacy`），不依赖 Actions，
因此发布令牌无需 `workflow` 作用域。

## 协作流程

1. Trae 进行小步开发。
2. 每个稳定节点进行一次可回滚的 Git 提交。
3. Codex 处理复杂任务或进行独立审查。
4. 敏感代码、凭据和私有数据在共享前脱敏。
5. WorkBuddy 整理文档、周报和知识库。

## 内容边界

成人向游戏只收录系统与数值类资料（角色定位、武器类型与机制、章节分支、地图掉落、
设施），不撰写露骨性内容，不做性化角色的页面。

## 署名与出处

素材多为他人在 B 站 / 贴吧 / 日站整理的成果，导入器会自动摘出署名行并渲染为页面
底部的出处块。公开站点不保留出处即侵权，**不要移除**。

## 遗留模块

`gamewiki/indexer.py` + `server.py` + `web/` 是早期的「本地文件索引/预览器」，
与 Wiki 目标无关，已停在可用状态不再投入。既有 GitHub 项目成果保存在
`legacy/jcwiki/`，不参与主程序执行。安全设计与自定义参数见
[docs/architecture.md](docs/architecture.md)。
