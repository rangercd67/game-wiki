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

## 已收录板块

| game id | 标题 | 分组 | 现状 |
| --- | --- | --- | --- |
| `dohna` | 多娜多娜 | common / data / story | 系统与数值资料，多处「资料缺口」待补 |
| `p5r` | P5R 皇家版 | common / palace / recommend / data / daily / misc | 殿堂走法、图鉴、日程 |
| `p3p` | P3P 携带版 | common / data | 技能、装备、敌人弱点 |
| `p4g` | P4G 黄金版 | common / data / daily | 合成表（20 个分表待合并）、技能、任务、奖杯 |
| `arknights` | 明日方舟 | `blackflow` / `jieyuan` / `gen` / `xianshu` | 误入奇境点位表（4 页 40 基底）+《集批宝典》全表导入（23 页），2026-09-25 新增 |

### 《集批宝典》：素材形态与导入方式（务必按这个走）

腾讯文档《集批宝典》`DUFhxeHFCaXJwS0Vl` 的作者是用**电子表格排图**，不是排表：合并
单元格、多子表并排塞进同一张 sheet、单元格行列位置本身携带语义（坐标图、按层分布图）。
因此**不要写「自动识别表头」的通用转换**，必然猜错。做法是：素材导出成 JSON 网格存
`library/明日方舟-集批宝典/原始导出/`，再在 `gamewiki/sources.py` 的 `ARKNIGHTS_SHEETS`
清单里**逐表声明** `mode`：

| mode | 用途 | 关键字段 |
| --- | --- | --- |
| `grid` | 原表网格，行号/列标 = 原文档坐标（最忠实） | — |
| `header` | 原表自带表头行 | `header_row` `value_from` `column_names` `fill_down` |
| `sections` | 同表内叠放的若干块，各自有表头 | `blocks=(label, start, end)` |
| `matrix` | 行 × 列 二维分类表，格内折行 | `header_row` `group_row` `key_col` `row_blocks` |
| `melt` | 宽转长 (分类, 名称) 或 (表头行,数值行) 配对 | `blocks` / `row_pairs` |
| `pairs` | (名称, 数值) 横向成对 → 逐行一条 | `label_col` `pair_from` `group_markers` `orphan_numbers` |
| `placeholder` | 子表内容是图片，接口取不到数据 | `tab` `sheet_name` |

踩过的坑（别再犯）：

1. **`value_from` 不能省**：原表最左边常有一整列空的（图表外框/刻度区），不跳过去
   表头会整体错一位（11/12 坐标图、23 财报都栽在这上面）。
2. **署名格要单独摘**：`制表人 哲三`、`数据来源 tomimi.dev` 落在数据格里，用
   `_CREDIT_CELL` 过滤掉、改在页面「出处」块呈现。但 `grid` 模式保留原样——整片网格
   就是要忠实还原。颜色图例（「蓝字：…」）同理，用 `skip_values` 摘出。
3. **`_trim_grid` 必须补等宽**：导出数据的行是参差的，不补的话每个 mode 按下标取值
   都会 IndexError。裁列可以，**裁首行不行**（行号即位置语义）。
4. **`mdrender` 不支持 `<url>` 自动链接**，外链必须写 `[文本](url)`，否则渲染成转义文本。
5. **构建前要停掉预览服务**：`python -m gamewiki.wiki` 会 `rmtree(dist-wiki)`，
   若有 http.server 正在占用该目录，沙箱的 trash shim 会报
   `[safe-delete] ... Some operations were aborted` 直接失败。

### 黑流树海：坐标口径（务必沿用，别改）

截图/资料上的坐标是 `(x, y)`：**x 自左起（0 起）**，**y 自下而上（0 起，地图固定 5 行）**。
列数按层：III 7 列、IV 8 列、V 10 列。III/V 层 1 个红终点（险路恶敌），IV 层 3 个（险路尽头）。

**规则版本分两套，不能混用**（这是单独成篇的原因）：

| 层 | 本站收录（2026-09-09 版） | `legacy/jcwiki/黑柳树海/` 那份（黑蓑 2026-08 口径） |
| --- | --- | --- |
| III 血色空脉 | 5-6 步 | 5-8 步 |
| IV 受害者腐殖 | 5-8 步（追忆 5-10+ 步） | 5-9 步 |
| V 卡德霍之颅 | 3-8 步 | 3-8 步 |

层名以截图为准：**受害者腐殖**（legacy 的 HTML 里写作「受害者腐蚀」，不用这个）。
数据来源：B站 UP主 哲三Philosophy_3 的拼图，**BV 号待补**。

### 从深色截图批量提取点位的方法（复用于同类资料）

`tmp/xrwj/` 有四个脚本（未入库，用到时再取）：按**固定色值**取连通域质心拿点位
（卡片底 `#101A24`、页面底 `#0A1016`、黄点 `#FFD92E`、起点 `#3EE6C4`），
用**起点锚定列**、用「红点集合是否等于标签终点集合」反推 y 轴方向，
再用「黄点数 == 标签写的可能位置数」做自校验。三层校验全过才算数据可用
（本次 40/40 全过）。做回检图把坐标画回原图，人眼过一遍再入库。

## 命令

```bash
# 素材 → 内容源（幂等，可重复执行）
python -m gamewiki.sources
# 内容源 → 静态站点
python -m gamewiki.wiki                     # 输出 dist-wiki/
python -m gamewiki.wiki --domain wiki.example.com  # 才需要写 CNAME
# 站内引用检查（发布前的硬闸门，deploy 会自动跑）
python -m gamewiki.checklinks
# 测试
python -m unittest discover -s tests -t .
# 发布到 GitHub Pages（--build 会先重建）
python -m gamewiki.deploy --remote https://github.com/rangercd67/game-wiki.git --build
# 本地预览（线上已可用，日常不必再开）
cd dist-wiki && python -m http.server 8099 --bind 127.0.0.1
```

## 部署（已上线）

**线上地址：<https://rangercd67.github.io/game-wiki/>**

| 项 | 值 |
| --- | --- |
| 仓库 | `rangercd67/game-wiki`，**public**（Pages 免费账号只能发公开仓库） |
| 站点分支 | `gh-pages`（孤立分支，`main` 只放源码） |
| Pages 模式 | `build_type=legacy`，分支直发，**不依赖 Actions** |
| 自定义域名 | **没绑**。`game-wiki` 挂在 `/game-wiki/` 子路径下 |

**为什么没绑 `xiaomenghua.top`**：那个域名是用户的 Hexo 博客（Cloudflare 后面，
jquery / fancybox / katex / atom.xml，带 `ctf-wp` 导航）。绑上去会把博客整个顶掉。
`rangercd67.github.io` 本身也已被占用（404 Site not found，无用户站）。

**子路径部署靠的是「输出一律相对路径」那条约定**——`checklinks` 里
「禁止 `href="/..."`」这条规则就是为它兜底的。

### 三个分支的分工

| 分支 | 内容 | 说明 |
| --- | --- | --- |
| `main` | 项目源码 + `legacy/` | 公开；`library/`、`dist-wiki/`、`tmp/` 被忽略 |
| `gh-pages` | 站点产物 | 发布目标，每次 deploy 覆盖 |
| `legacy-static` | 远端旧站（`7604eeb`） | 早期「江城创业记/多娜多娜/黑柳树海」静态站，换 main 前存下来的 |

远端原 `main` 与本地**无共同祖先**（旧站是被 `git filter-repo` 从 jcwiki 拆出来的），
所以 2026-09-25 那次换 main 用的是 `--force-with-lease`，不是强推裸 `--force`。
旧内容没丢：既在 `legacy-static` 分支上，也在本地 `legacy/` 与 `tmp/legacy-backup/` 里。

### 发布凭据

- 代理必须走 `http://127.0.0.1:7890`（`7891`/`1080`/`10809` 都不通）。
- 令牌在 `~/.hermes/github_token_ruankao`（40 字符），作用域含 `repo`、`delete_repo`，
  **不含 `workflow`** —— 所以 Pages 只能走「分支直发」，不能用 Actions 方式建站。
- 无人值守下必须显式清空 `credential.helper` 再注入，否则会挂在本机
  `git-credential-manager` 上空转 ~70 秒：

```bash
export TOKEN=$(cat ~/.hermes/github_token_ruankao | tr -d '\r\n')
export GIT_CONFIG_COUNT=3
export GIT_CONFIG_KEY_0=http.proxy
export GIT_CONFIG_VALUE_0=http://127.0.0.1:7890
export GIT_CONFIG_KEY_1=credential.helper
export GIT_CONFIG_VALUE_1=
export GIT_CONFIG_KEY_2=credential.helper
export GIT_CONFIG_VALUE_2='!f() { echo username=x-access-token; echo password=$TOKEN; }; f'
```

## 用户偏好

- UI：极简医学风格，≤2 主色（科技蓝 `#0EA5E9` / 活力绿 `#22C55E`），背景 `#F0F7F7`，
  圆角 12px，无衬线。深浅双主题只切表面与文字色，主色不变。
- 沟通：先确认目标产物形态再动手；用户对方向性错误容忍度极低。
- 部署：**GitHub Pages 子路径**，不再在本地长期挂预览服务。
