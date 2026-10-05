# game-wiki 项目长期笔记

> 日常流水见 `.workbuddy/memory/YYYY-MM-DD.md`；这里只留跨会话必须遵守的约定与结论。

## 项目定位

**内容型攻略 wiki**（GitHub Pages 子路径部署），形态参考 `wiki.biligame.com/persona`：
左侧分组导航树 + 页面正文 + 数据表格 + 图集 + 站内搜索。

> 历史包袱：`gamewiki/indexer.py` / `server.py` / `web/` / `build.py` 是早期的
> 「本地文件索引器」，与 wiki 无关，已停在可用状态。**别因为它把需求往文件管理方向带。**

## 架构：三段式管道

```
library/  原始素材（只读）  --gamewiki/sources.py（声明式清单）-->  content/  内容源
content/  Markdown + data/*.json + media.json + site.json  --gamewiki/wiki.py-->  dist-wiki/  产物
```

| 路径 | 说明 |
| --- | --- |
| `content/site.json` | 站点标题 + `games[]`，每个 game 自带 `groups[]` |
| `content/<game>/index.md` | 游戏首页 |
| `content/<game>/<slug>.md` | 普通页面 → `dist-wiki/<game>/<slug>/index.html` |
| `content/data/<game>/<name>.json` | 结构化表格，被 front-matter `data: <game>/<name>` 引用 |
| `content/media.json` | `输出名 → library 相对路径`，**图片不进 git** |
| `content/_*/`、`data/` | 保留目录，扫描时静默跳过 |

front-matter：`title` / `group`（site.json 里的分组 id）/ `order`（组内排序）/ `summary`，
可选 `data: <game>/<name>`。

## 硬性技术约定

1. **零第三方依赖**（Pillow 可选，缺了降级为原样复制）。
2. **输出一律相对路径**。内容写 `/media/x.png`，生成器按页面深度改写；
   禁止产出 `href="/..."`（`checklinks` 硬闸门，违规数必须为 0）——子路径部署靠它。
3. **转义只做一次**，在 `mdrender.render()` 入口，用自定义 `_text()`
   （`&`→`&amp;`、`<`→`&lt;`）。**不能用 `html.escape`**，它会把 `>` 变成 `&gt;`
   毁掉引用块。`inline()` 的契约是「入参已转义」。
4. **行内标记先拼行、再 inline**。`_join_inline()` 把连续行拼成一句后才走行内解析；
   **反过来（逐行 inline 再拼）会让跨行写的 `**粗体**`、`` `行内代码` `` 落单**，
   页面上直接印出字面标记。段落与列表项共用它。
   同理：**列表项支持缩进续行**（缩进更深、非列表标记、非块起始的后续行并入本项），
   否则一句写不完的要点会把列表切成好几个 `<ul>`。闸门：
   `tests/test_mdrender.py::ListContinuationTests`、`tests/test_content_markup.py`
   （整棵 `content/` 渲染后不得出现 `**` `` ` `` `~~` `![` `](` `| --- |`）。
5. **大表格走 `content/data/`**，不要内联进 Markdown。
6. **素材编码必须探测**：UTF-8 → GB18030 → Big5。
7. **表格留空列按需向下填充**（`fill_down`），但必须按列声明（合成表的 `Lv`/名称 空白是
   「同上」，掉落列的空白是「无掉落」）。
8. **署名与出处必须保留**。素材多为他人在 B 站/贴吧/日站整理的成果，不标出处即侵权；
   导入器会自动摘署名行渲染成页面底部的出处块。
9. **不编数据**。只有标题没数值就写「资料缺口」；拿到的是截图而没逐格核对就先收原图、
   缺口写「待表格化」。**截图自称的数量与图内条数不符时，先去核原文**。
10. **数据表单元格是纯文本**。`_render_data_table()` 每格走 `html.escape()`，
    写 `**` 会印出字面星号，写 `[文字](/link/)` 既不渲染 `checklinks` 也扫不到。
    闸门 `tests/test_data_cells.py`。
11. **页面顺序的唯一真相 = front-matter 的 `order`**（导入页来自 `sources.py` 的 `spec.order`）。
    `collect_pages()` 全局重排为「游戏按 site.json 序 → 组按 groups[] 序 → 组内 order」，
    导航 / 首页卡片 / 搜索索引共用这一份。**别在别处按文件名序排 pages**。
12. **数据表落点用 `:::data` 占位**（正文单独一行）。不写占位符时表格仍追加在正文末尾，
    会排到「内容出处」之后。`_place_data_table()`，用例 `tests/test_data_slot.py`。
13. **Pages 发布有编译延迟**：deploy 成功后立刻 curl 新页会 404，约 1 分钟才 200。
    判定成功看 `tmp/deploy-cache` 的提交 + 远端 `gh-pages`，别只看首次 curl。
14. **`deploy --build` 不能放后台**：后台无宿主确认弹窗，重建时 `rmtree(dist-wiki)`
    会撞沙箱批量删除守卫（`[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]`）白跑一次。
    **前台重跑**才有弹窗。另：构建前要停掉占用 `dist-wiki` 的 http.server。
15. 素材目录名/工作表名找不到时**报错跳过并记录**，不要猜。

## 内容边界（多娜多娜等成人向游戏）

- 只收系统与数值类资料：角色定位、武器类型与机制、章节分支、地图掉落、设施。
- **不撰写露骨性内容，不做性化角色的页面**；道具/店铺等字面系统界面词按原文保留。
- **素材混着成人向标签时做「中性化 + 公开对照」**：
  `【XX 爆衣CG】`→`【XX 专属 CG】`、`【XX H剧情】`→`【XX 专属事件】`、
  `【XX NTR剧情/回忆】`／`牛头人事件`→`【XX 坏结局事件】`、`处○`→`处女人材`、
  `porno`→`珀尔诺`。**游戏内任务文本原样保留**，只改标签；对照表写在页面「内容出处」；
  **原图本身带这些标签就不发布**，只归档到 `library/`。

## 已收录板块

| game id | 标题 | 分组 | 现状 |
| --- | --- | --- | --- |
| `dohna` | 多娜多娜 | common / data / story | **16 页**（2026-10-06 +1）：角色 / 徽章搭配 / 人材属性与经营环节 / 武器 / 数据表 / 词条 63 / 特殊人才（一览·任务条件·评价）/ 掉落（路线图·明细）/ 徽章位置 / 章节 / 话数 / **逐日流程** |
| `p5r` | P5R 皇家版 | common / palace / recommend / data / daily / misc | 殿堂走法、图鉴、日程 |
| `p3p` | P3P 携带版 | common / data | 技能、装备、敌人弱点 |
| `p4g` | P4G 黄金版 | common / data / daily | 合成表（20 个分表待合并）、技能、任务、奖杯 |
| `arknights` | 明日方舟 | `blackflow`/`jieyuan`/`gen`/`xianshu` | 误入奇境点位表（4 页 40 基底）+《集批宝典》全表导入（23 页） |

**多娜多娜剩余「资料缺口」**：逐点掉落明细表格化、武器强化素材金额、词条官方原文数值、
据点设施数值、敌人弱点。**话数（1～59）与章数（8～24）不是同一套编号**，别互相套用。

### 多娜多娜三批素材的关键结论

**1）掉落点**（贴吧「轰击晨星i」《中文地图资料大全》，同文见 doyo / OMOBI）

- 放大方式分两种：**像素地图**用 waifu2x `-s 4 -n 1 -m …anime_style_art_rgb`；
  **文字表格用 LANCZOS**（动画模型会给文字加晕色）。不做矢量化。
- **低清截图不要相信自己的眼睛**——已读错三处（徽章房间「服务器室」实为**娱乐室**、
  效果「-20%」实为 **+20%**、区域 1 的「武器 2 级」属于**服务器室**而非大厅）。
  凡是**符号 / 房间名 / 人名**，一律拿同源**文字版**（doyo/omobi/cyberly）定稿。
- 原帖自身 3 处矛盾（产峰工业两个点位概率写反、化学研究所生物安全柜 12.50% vs 40%）：
  **以逐图表为准**，速查表照录 + 备注列标注。

**2）人材词条**（小黑盒 轰击晨星 自制长图，593×1920，两张同构表 63 行 + 18 行）

- **`LKS/TEC/MEN` 与 `LKS修正/TEC修正/MEN修正` 是两套数，原帖没解释区别**
  （量级 ±1000 vs ±100～±400；社区的三幻神/四天王/八大金刚用的是**修正**那套）。
  **两套照录，页面明写「原帖未说明」，不推断。**
- 「强横」数值已补齐 `0 / -100 / +100`；原帖把「安产型」与「穿显瘦」重复粘贴，照录并点出。
- **低清截图有可读性下限**：图 A 原生 387 px 宽、正文约 12 px/字，6 倍 NEAREST 放大后
  笔画仍是糊的——**信息已经丢了，不是放大方式的问题**。判读靠**暗像素行高**定位文字行
  （8 px 是正文，30+ px 是药丸色块）；读不出的四处**全部标「字迹不清，未转写」**，不猜。

**3）逐日流程**（贴吧 辉弥沙耶《【无剧透】全主线简易流程攻略》，2020-12）

- 与 `special-talents-quests` 重合的后半段（第 34～47 楼特殊妹子条件）**不重复收录**；
  粉色 ToDo 标签细条截图也不收（正文已转写，完整清单在 `episode-flow`）。
- 原帖**跳过** DAY 27/32/41/42/57，**抽楼**丢了 DAY 18～22；
  DAY 9～11、15～17、29～30、47～48、59～68 来自**补楼截图**，必须读图转写。
- 站内独有的信息：结局三层（普通 / 个人 = 未发生坏结局事件且好感 ≥ 7 /
  老板娘 = 2000w 事件且全员好感 ≤ 7），**判定节点 = 第二个【ToDo：なし】完成时**。
- 选图规则：去重后取「高度 ≥ 100 px」，再手工剔装饰件（立绘、商标、属性标尺细条）。

### 《集批宝典》导入（务必按这个走）

作者是用**电子表格排图**（合并单元格、多子表并排、单元格行列位置携带语义），
**不要写「自动识别表头」的通用转换**，必然猜错。素材导出 JSON 网格存
`library/明日方舟-集批宝典/原始导出/`，再在 `sources.py` 的 `ARKNIGHTS_SHEETS` 里逐表声明 `mode`：

| mode | 用途 | 关键字段 |
| --- | --- | --- |
| `grid` | 原表网格，行号/列标 = 原文档坐标（最忠实） | — |
| `header` | 原表自带表头行 | `header_row` `value_from` `column_names` `fill_down` |
| `sections` | 同表内叠放的若干块，各带表头 | `blocks=(label, start, end)` |
| `matrix` | 行 × 列 二维分类表 | `header_row` `group_row` `key_col` `row_blocks` |
| `melt` | 宽转长 (分类, 名称) 或 (表头行, 数值行) 配对 | `blocks` / `row_pairs` |
| `pairs` | (名称, 数值) 横向成对 → 逐行一条 | `label_col` `pair_from` `group_markers` `orphan_numbers` |
| `placeholder` | 子表内容是图片，接口取不到 | `tab` `sheet_name` |

坑：① **`value_from` 不能省**——原表最左边常有一整列空的（图表外框/刻度区），
不跳过去表头整体错一位。② **署名格要单独摘**（`_CREDIT_CELL`），但 `grid` 模式保留原样；
颜色图例用 `skip_values`。③ **`_trim_grid` 必须补等宽**，行参差不补就 IndexError；
裁列可以，**裁首行不行**。④ **`mdrender` 不支持 `<url>` 自动链接**，外链必须 `[文本](url)`。

### 黑流树海：坐标口径（别改）

坐标 `(x, y)`：**x 自左起（0 起）**，**y 自下而上（0 起，地图固定 5 行）**。
列数按层：III 7 列、IV 8 列、V 10 列。III/V 层 1 个红终点，IV 层 3 个。
层名以截图为准：**受害者腐殖**（legacy HTML 里的「受害者腐蚀」不用）。
**规则版本分两套不能混用**：本站收录（2026-09-09 版）III 5-6 步 / IV 5-8 步（追忆 5-10+）/ V 3-8 步；
`legacy/jcwiki/黑柳树海/` 那份（黑蓑 2026-08 口径）III 5-8 / IV 5-9 / V 3-8。
数据来自 B 站 哲三Philosophy_3 的拼图，**BV 号待补**。

### 从深色截图批量提点位（`tmp/xrwj/`，未入库）

按**固定色值**取连通域质心（卡片底 `#101A24`、页面底 `#0A1016`、黄点 `#FFD92E`、
起点 `#3EE6C4`），用**起点锚定列**、「红点集合 == 标签终点集合」反推 y 轴方向、
「黄点数 == 标签写的可能位置数」自校验。**三层校验全过才算可用**（曾 40/40 全过），
再画回检图人眼过一遍。

### 读图定图注的省力办法

用 PIL 拼 **contact sheet**（2～4 列、每格标 `#序号 楼层/图号 尺寸`）一次看 7～30 张，
比一张张 Read 省一个数量级。地图右下角**标签框要单独裁剪 + 3 倍放大**才读得清。
（同源：**贴吧「只看楼主」全量抓取**的通道与坑，见 `2026-10-05.md`。）

## 命令

```bash
python -m gamewiki.sources                  # 素材 → 内容源（幂等）
python -m gamewiki.wiki                     # 内容源 → dist-wiki/（会先删产物目录）
python -m gamewiki.checklinks               # 站内引用硬闸门（deploy 会自动跑）
python -m unittest discover -s tests -t .   # 85 例
python -m gamewiki.deploy --remote https://github.com/rangercd67/game-wiki.git --build
cd dist-wiki && python -m http.server 8099 --bind 127.0.0.1   # 本地预览（日常不必开）
```

## 部署（已上线）

**<https://rangercd67.github.io/game-wiki/>**

| 项 | 值 |
| --- | --- |
| 仓库 | `rangercd67/game-wiki`，**public**（Pages 免费账号只能发公开仓库） |
| 站点分支 | `gh-pages`（孤立分支；`main` 只放源码） |
| 模式 | `build_type=legacy`，分支直发，**不依赖 Actions** |
| 自定义域名 | **没绑**，挂在 `/game-wiki/` 子路径下 |

**为什么没绑 `xiaomenghua.top`**：那是用户的 Hexo 博客（Cloudflare 后面），绑上去会把博客顶掉；
`rangercd67.github.io` 本身也已被占用。子路径部署靠的就是第 2 条「输出一律相对路径」。

三个分支：`main`（源码 + `legacy/`，`library/`、`dist-wiki/`、`tmp/` 忽略）、
`gh-pages`（产物）、`legacy-static`（远端旧站 `7604eeb`）。
远端原 `main` 与本地**无共同祖先**，换 main 用 `--force-with-lease`。

### 发布注入（顺序不能反）

令牌在 `~/.hermes/github_token_ruankao`（含 `repo`/`delete_repo`，**不含 `workflow`** → 只能分支直发）。
代理必须 `http://127.0.0.1:7890`（7891/1080/10809 都不通）。
`~/.gitconfig` 里那条**空** `[credential] helper =` 已根治弹窗，**空值必须先于真 helper 出现**：

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
  圆角 12px，无衬线；深浅双主题只切表面与文字色，主色不变。
- 沟通：**先确认目标产物形态再动手**（「抽成 wiki 页面」≠ 交付独立 HTML）；对方向性错误容忍度极低。
- 部署：GitHub Pages 子路径，不在本地长期挂预览服务。
