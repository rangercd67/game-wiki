"""把 `library/` 里的原始素材导入成 wiki 内容源（`content/`）。

素材是「攻略作者打包分享的文件」：txt / docx / xlsx / 截图混在一起，命名靠人肉约定，
编码不统一，表格里有大量留空表示「同上」。这个模块的职责就是把这些不规则的东西
变成可重复生成的规范内容源，并且**明确记录哪些内容没有导入、为什么**——
静默丢内容是这类工具最危险的失败方式。

三类页面：
- 图集页：一个目录下的截图，按自然序排列，文件名作为图注
- 表格页：xlsx 的某个工作表，转成结构化数据（`content/data/…json`）
- 文本页：txt/docx，转成 Markdown 段落

另有一类不走 xlsx 的「网格页」：明日方舟《集批宝典》是在线表格，素材是导出后的
JSON 网格（见 `SheetGrid`）。它用电子表格排图，需要按子表逐个声明呈现方式。

设计上刻意采用**声明式素材清单**而不是自动遍历：真实工作簿常有三四十个工作表，
自动一个表建一页会产出一堆重复且无人维护的页面。清单是编辑决策，代码只负责执行。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_SOURCE, PROJECT_ROOT
from .ooxml import OoxmlError, extract_sheets, extract_text

CONTENT_ROOT = PROJECT_ROOT / "content"
DATA_DIR = "data"

# 署名与出处标记：这些行不能混进正文或表格，但又必须保留——
# 素材是他人整理成果，公开发布必须保留出处。
ATTRIBUTION_MARKERS = ("作者：", "作者:", "出处：", "出处:", "转自", "来源：", "来源:", "B站up主")
_ATTRIBUTION = re.compile("|".join(re.escape(marker) for marker in ATTRIBUTION_MARKERS))
_DIGITS = re.compile(r"(\d+)")
_BLANK_LINES = re.compile(r"\n\s*\n")


# ---------- 基础工具 ----------


def read_text(path: Path) -> tuple[str, str]:
    """读取文本，返回 (内容, 实际编码)。

    素材编码并不统一：同一批攻略里出现过 GBK 的 txt（用 UTF-8 读会整篇乱码，
    而且乱码后仍然是「合法字符串」，不会报错直到读者发现）。因此 UTF-8 失败后
    必须回退到 GB18030 —— 它是 GBK 的超集，能覆盖简体与繁体旧编码。
    """
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "big5"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8(replace)"


def natural_key(value: str) -> list:
    """自然序：让 `2F` 排在 `10F` 前面，而不是按字典序把 10F 排在 2F 前。"""
    return [int(part) if part.isdigit() else part for part in _DIGITS.split(value)]


def split_attribution(lines: list[str]) -> tuple[list[str], list[str]]:
    """把署名行从正文中摘出来，返回 (正文行, 署名行)。"""
    body, credits = [], []
    for line in lines:
        (credits if _ATTRIBUTION.search(line) else body).append(line)
    return body, credits


def paragraphs_to_markdown(lines: list[str]) -> str:
    """空行分段，段内单行之间用硬换行，保留原始的行块结构。"""
    blocks: list[str] = []
    for block in _BLANK_LINES.split("\n".join(lines).strip()):
        rows = [row.strip() for row in block.splitlines() if row.strip()]
        if rows:
            blocks.append("  \n".join(rows))
    return "\n\n".join(blocks)


def credits_block(credits: list[str]) -> str:
    if not credits:
        return ""
    joined = "  \n".join(dict.fromkeys(row.strip() for row in credits if row.strip()))
    return f"\n\n> **内容出处**  \n> {joined}"


# ---------- 素材清单 ----------


@dataclass
class Gallery:
    slug: str
    title: str
    group: str
    order: float
    directory: str
    summary: str = ""
    intro: str = ""
    # 目录内需要优先展示/排除的文件名关键字
    spoiler: bool = False


@dataclass
class Table:
    slug: str
    title: str
    group: str
    order: float
    source: str
    sheet: str
    summary: str = ""
    skip_rows: int = 0
    drop_rows: tuple[int, ...] = ()
    fill_down: tuple[int, ...] = ()
    caption: str = ""


@dataclass
class Text:
    slug: str
    title: str
    group: str
    order: float
    source: str
    summary: str = ""
    # 非空则把文件每一行按 split 拆成表格列，适合「日期 + 内容」这类清单式文件
    columns: tuple[str, ...] = ()
    split: str = r"\s+"


@dataclass
class Palace:
    """殿堂/迷宫：走法图集 + 敌人弱点表 + 注意事项，合成一个页面。"""

    slug: str
    title: str
    order: float
    directory: str
    sheet: str
    summary: str
    notes: tuple[str, ...] = ()
    extra_media: tuple[str, ...] = ()


P5R_ROOT = "P5R攻略2.0/P5R"
PALACE_ROOT = f"{P5R_ROOT}/最后殿堂（剧透慎点）"

PALACES: list[Palace] = [
    Palace("palace-shido", "色欲的城堡（鸭志田）", 1, f"{P5R_ROOT}/1鸭志田殿堂", "鸭志田殿堂",
           "鸭志田殿堂全楼层地图、欲石走法与敌人弱点。建议 4.18 当天一次性拿完所有宝箱和欲石。",
           notes=(f"{P5R_ROOT}/1鸭志田殿堂/注意事项.txt",
                  f"{P5R_ROOT}/1鸭志田殿堂/关于地图攻略的注意事项.txt")),
    Palace("palace-madarame", "虚荣的美术馆（斑目）", 2, f"{P5R_ROOT}/2斑目殿堂", "斑目殿堂",
           "斑目殿堂全楼层地图与三块欲石位置，含扭曲的迷宫与小百合真迹路线。"),
    Palace("palace-kaneshiro", "暴食的银行（金城）", 3, f"{P5R_ROOT}/3金城殿堂", "金城殿堂",
           "金城殿堂全楼层地图，含地下大金库分层结构与洗钱办公室路线。"),
    Palace("palace-futaba", "愤怒的金字塔（双叶）", 4, f"{P5R_ROOT}/4双叶殿堂", "双叶殿堂",
           "双叶殿堂各情绪之间地图与地下洞穴路线。"),
    Palace("palace-okumura", "贪婪的宇宙基地（奥村）", 5, f"{P5R_ROOT}/5奥村殿堂", "奥村殿堂",
           "奥村殿堂流水线区域地图，含制造区与出货区路线。"),
    Palace("palace-sae", "嫉妒的赌场（新岛冴）", 6, f"{P5R_ROOT}/6新岛冴殿堂", "真岛冴殿堂",
           "新岛冴殿堂赌场各层地图，含黑暗之屋与老虎机房间。"),
    Palace("palace-masayoshi", "傲慢的游轮（狮童）", 7, f"{P5R_ROOT}/7狮童殿堂", "狮童殿堂",
           "狮童殿堂游轮各甲板与客舱通道地图，含欲石 3 与第二个宝箱的拿法。"),
    Palace("palace-mementos", "印象空间最深处", 8, f"{P5R_ROOT}/8印象空间最深处", "印象空间最深处",
           "印象空间最深处狱中通道全段走法。"),
    Palace("palace-qliphoth", "邪恶世界树", 9, f"{P5R_ROOT}/9邪恶树的世界", "邪恶树的世界",
           "通往圣杯的道路各段走法。"),
    Palace("palace-maruki", "？？？：研究所（丸喜）", 10, PALACE_ROOT, "最后的殿堂",
           "第三学期最后殿堂全区域地图。**含剧情剧透**，未通关请勿阅读。",
           notes=(f"{PALACE_ROOT}/黄昏回廊走法.txt",),
           extra_media=("宝魔.png", "P5R合成公式.jpg", "宝魔合成.jpg",
                        "面具性格1.png", "面具性格2.png")),
]

P5R_TABLES: list[Table] = [
    Table("persona-list", "人格面具总表", "data", 1, f"{P5R_ROOT}/P5R人格面具.xlsx", "面具总表",
          "全 200+ 人格面具的耐性、特性、电刑产物与合成公式。表内可直接筛选。",
          skip_rows=2, fill_down=(0, 1)),
    Table("persona-traits", "面具特性一览", "data", 2, f"{P5R_ROOT}/P5R人格面具.xlsx", "特性",
          "全部面具特性的中日文名称与实际效果，含「可以突破魔法伤害上限」这类关键机制说明。"),
]

P5R_TEXT: list[Text] = [
    Text("guide-start", "新手必读：该优先发展什么", "common", 1,
         f"{P5R_ROOT}/想自己玩的看这个.txt",
         "COOP 优先级、DLC 面具选择、战斗与日程的总体思路。"),
    Text("guide-schedule", "全事件白金攻略日程", "common", 2,
         f"{P5R_ROOT}/P5R日程攻略简体版文档.txt",
         "从 4.12 开始逐日安排，含课堂问答、COOP 发展与殿堂潜入时机。"),
    Text("guide-difficulty", "推荐面具选择与难度建议", "recommend", 1,
         f"{P5R_ROOT}/难度选择和初期面具选择.txt",
         "难度档位、DLC 面具与前期过渡面具推荐。"),
    Text("guide-max-stats", "把面具属性拉满到 99", "recommend", 2,
         f"{P5R_ROOT}/如何把面具属性全部拉到99.txt",
         "利用合体警报与黄字面具绞刑，稳定获得 10 点属性提升。"),
    Text("guide-treasure-demon", "宝魔出现位置与掉落", "common", 3,
         f"{P5R_ROOT}/印象空间之宝魔出现位置.txt",
         "各层宝魔的出现条件与对应掉落。"),
]

P5R_MISC: list[Text] = [
    Text("misc-links", "延伸阅读与外部资源", "misc", 1, f"{P5R_ROOT}/装饰物收集.txt",
         "装饰物收集、全对话攻略等外部参考资料。"),
]

P3P_ROOT = "P3P&P4G攻略合集包/P3P"
P4G_ROOT = "P3P&P4G攻略合集包/P4G"

P3P_GALLERIES: list[Gallery] = [
    Gallery("fusion-table", "全面具合成表", "data", 1, f"{P3P_ROOT}/全面具合成",
            "二身 / 三身合成公式与反查表，含特殊合成与各塔罗牌组合。"),
    Gallery("persona-list", "全面具属性及出现位置", "data", 2, f"{P3P_ROOT}/全面具属性及出现位置",
            "全部人格面具的属性与出现位置，共 13 张。"),
    Gallery("equipment", "全装备列表及获得方式", "data", 3, f"{P3P_ROOT}/全装备列表及获得方式",
            "各角色武器、防具、鞋子与饰品获取方式。"),
    Gallery("enemy-weakness", "全敌人属性弱点及掉落", "data", 4, f"{P3P_ROOT}/全敌人属性弱点及掉落",
            "全部敌人的弱点属性与掉落物。"),
    Gallery("social-links", "全社群解锁地点和条件", "data", 6, f"{P3P_ROOT}/全社群解锁地点和条件",
            "男女主全部社群的解锁地点与条件。", intro="男主与女主两条线分别对应一张图。"),
    Gallery("side-quests", "支线任务攻略", "data", 7, f"{P3P_ROOT}/支线任务攻略",
            "支线任务的接取条件与完成方式。"),
    Gallery("weapon-fusion", "武器合成攻略", "data", 8, f"{P3P_ROOT}/武器合成攻略",
            "武器合成公式、特殊武器合体与素材出处。"),
]

P3P_TABLES: list[Table] = [
    Table("skills", "技能一览", "data", 5, f"{P3P_ROOT}/技能篇.xlsx", "Sheet1",
          "全部技能的消耗、效果与习得条件。"),
]

P3P_TEXT: list[Text] = [
    Text("guide-notice", "游玩前注意事项", "common", 1, f"{P3P_ROOT}/游玩前注意事项（必看！！！）.txt",
         "开局前必须知道的机制与不可逆选择。"),
    Text("guide-male-schedule", "男主篇一周目全社群 MAX 日程", "common", 2,
         f"{P3P_ROOT}/男主篇一周目全社群MAX日程攻略.txt",
         "男主视角一周目社群全 MAX 的逐日安排。"),
    Text("guide-female-schedule", "女主篇一周目全社群 MAX 日程", "common", 3,
         f"{P3P_ROOT}/女主篇一周目全社群MAX日程攻略.txt",
         "女主视角一周目社群全 MAX 的逐日安排。"),
    Text("guide-gift", "送礼物攻略", "common", 4, f"{P3P_ROOT}/送礼物攻略.txt",
         "各角色礼物偏好。"),
]

P4G_GALLERIES: list[Gallery] = [
    Gallery("enemy-weakness", "全敌人弱点属性", "data", 1, f"{P4G_ROOT}/全敌人弱点属性",
            "全部敌人弱点属性表，共 9 张。"),
]

P4G_TABLES: list[Table] = [
    Table("persona-fusion", "全面具合成表", "data", 2, f"{P4G_ROOT}/全面具合成表/特殊合体表.xlsx", "Sheet1",
          "特殊合体表。其余塔罗牌合成表见下方分区。"),
    Table("skills", "技能与技能卡", "data", 3, f"{P4G_ROOT}/技能与技能卡攻略/物理技能.xlsx", "Sheet1",
          "物理技能的名称、可产出技能卡的面具与价格。"),
    Table("tasks", "全支线任务", "data", 4, f"{P4G_ROOT}/全支线任务.xlsx", "Sheet1",
          "全支线任务的委托内容、期限与报酬。"),
    Table("trophies", "成就奖杯列表", "data", 5, f"{P4G_ROOT}/成就奖杯列表（转自PSNINE）.xlsx", "Sheet1",
          "全成就奖杯的获取条件。"),
]

P4G_TEXT: list[Text] = [
    Text("guide-main", "P4G 完整攻略", "common", 1, f"{P4G_ROOT}/P4G攻略新版本.txt",
         "流程、社群、战斗与合成的综合攻略。"),
]

# 填字游戏的原始文件是「日期 + 答案」清单，且作者署名与链接直接接在最后一条数据末尾，
# 因此按行拆列，并在拆列后把署名从单元格里摘出来单独保留。
P5R_DAILY: list[Text] = [
    Text("crossword", "填字游戏答案", "daily", 1, f"{P5R_ROOT}/简体版填字游戏.txt",
         "全部填字游戏的日期与答案，可按日期检索。",
         columns=("日期", "答案")),
]

# P4G 的日程检索表按月分成 12 个 docx；z1~z3 是跨年后的 1~3 月。
P4G_MONTHS: list[Text] = [
    Text(
        f"schedule-{month:02d}",
        f"{month} 月日程",
        "daily",
        100 + month,
        f"{P4G_ROOT}/日程检索表（适合想自己玩的）/{'z' if month < 4 else ''}{month}月.docx",
        f"{month} 月逐日安排与可做事项。",
    )
    for month in (4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3)
]


# ---------- 明日方舟《集批宝典》（在线表格导出网格） ----------
#
# 这批素材不是 xlsx，而是腾讯文档《集批宝典》各子表经匿名接口导出后的 JSON：
# 每个子表一份 `NN-<名字>.json`，`grid` 是二维字符串数组，单元格内的换行原样保留。
#
# 作者是用电子表格**排图**而不是排表：大量合并单元格、多个子表并排塞进同一张 sheet、
# 单元格所在的行列位置本身携带语义（坐标图、按层分布图）。所以这里不写「自动转成规整表」
# 的通用逻辑——对这类表它必然猜错；而是逐个子表在清单里声明呈现方式（mode），把编辑
# 判断留在清单里，代码只负责执行。
#
# 合并单元格导出后只有左上角有值、其余为空，这是**原始形态**，一律不补全。

JIPIBAO_ROOT = "明日方舟-集批宝典/原始导出"
JIPIBAO_DOC = "https://docs.qq.com/sheet/DUFhxeHFCaXJwS0Vl"

# 表里散落的署名格（「制表人 哲三」之类）不能当数据塞进表格，但必须在页面上保留。
_CREDIT_CELL = re.compile(
    "|".join(re.escape(marker) for marker in ATTRIBUTION_MARKERS)
    + r"|制表人|制图人|数据来源|素材来源|统计："
)


@dataclass
class SheetGrid:
    """《集批宝典》子表的转写方式。

    `mode` 的取值与含义：

    - `grid`        原表网格。行号 = 原文档行号、列号 = 原文档列标，最忠实地保留排图语义。
    - `header`      某一行的内容就是表头（原表自带表头的坐标图用这个）。
    - `sections`    同一子表里上下叠放的若干块，每块有各自的表头，首列是块的类别。
    - `matrix`      二维分类表（行 = 星级，列 = 类别），把单元格内的换行折进同一格。
    - `melt`        宽表转长表：拆成 (分类, 名称) 两列；也支持 (表头行, 数值行) 配对。
    - `pairs`       (名称, 数值) 成对排布的分布表，常见形态是「层 → 节点 → 数值」。
    - `placeholder` 子表内容全是图片，接口取不到数据，只建页说明缺口。
    """

    slug: str
    title: str
    group: str
    order: float
    source: str
    summary: str
    mode: str = "grid"
    credits: str = "哲三"
    tab: str = ""
    sheet_name: str = ""
    header_row: int = 0
    label_col: int = 1
    value_from: int = 2
    key_col: int = 2
    group_row: int = -1
    fill_down: tuple[int, ...] = ()
    column_names: tuple[str, ...] = ()
    blocks: tuple[tuple[str, int, int], ...] = ()
    row_blocks: tuple[tuple[int, int], ...] = ()
    row_pairs: tuple[tuple[int, int], ...] = ()
    pair_from: int = 3
    pair_width: int = 2
    group_markers: tuple[tuple[int, str], ...] = ()
    orphan_numbers: str = "swap"
    # 原表把颜色图例（「蓝字：…」「黄底：…」）也写进了数据格，它不是数据，摘出来放正文。
    skip_values: tuple[str, ...] = ()
    note: str = ""

# 分组：黑流树海（已有）/ 界园 / 通用机制 / 仙术杯赛事。
# 归属按子表本身的范围定——跨期通用的数值表（经验、源石锭、BOSS、年代）放「通用机制」，
# 只在界园里成立的（构想、去伪存真、结局路线）放「界园」。
ARKNIGHTS_SHEETS: list[SheetGrid] = [
    # ---------- 黑流树海 ----------
    SheetGrid(
        "tree-sea-events", "不期而遇事件总表（树海 dlc0）", "blackflow", 5,
        f"{JIPIBAO_ROOT}/01-树海合订本dlc0.json",
        "「沉沦者的黑流树海」全部不期而遇事件：事件名、产出层位、简述与效果。",
        credits="哲三",
        note="### 表的读法\n\n"
             "原表是作者按层手排的分层图：事件名与「该事件会出现在哪一层」靠单元格的行列\n"
             "位置对应，而不是靠规整的列。合并单元格导出后只有左上角有值、其余为空，所以\n"
             "看起来空格很多——这是**原始形态，未做补全**。需要对照时可按行号 / 列标回原\n"
             "文档定位。",
    ),
    # ---------- 界园 ----------
    SheetGrid(
        "jy-events-dlc1", "不期而遇事件总表（界园 dlc1）", "jieyuan", 1,
        f"{JIPIBAO_ROOT}/04-界园合订本dlc1.json",
        "界园 dlc1 的不期而遇事件总表，按一至六层标注事件与效果。",
        credits="哲三",
        note="### 表的读法\n\n"
             "与「树海合订本」同一种排法：事件名与层位靠单元格位置对应，合并单元格导出后\n"
             "只剩左上角有值。这是**原始形态，未做补全**，可按行号 / 列标回原文档定位。",
    ),
    SheetGrid(
        "jy-events-dlc2", "不期而遇事件总表（界园 dlc2）", "jieyuan", 2,
        f"{JIPIBAO_ROOT}/02-界园合订本dlc2.json",
        "界园 dlc2 的不期而遇事件总表，含 dlc2 新增事件。",
        credits="哲三",
        note="### 表的读法\n\n"
             "与「树海合订本」同一种排法：事件名与层位靠单元格位置对应，合并单元格导出后\n"
             "只剩左上角有值。这是**原始形态，未做补全**，可按行号 / 列标回原文档定位。",
    ),
    SheetGrid(
        "jy-ideas", "构想分布表", "jieyuan", 3,
        f"{JIPIBAO_ROOT}/15-构想分布表.json",
        "每个节点对应的构想编号，按一至六层 / boss / 特殊分组。",
        mode="pairs", credits="哲三",
        label_col=2, pair_from=3, pair_width=2, orphan_numbers="swap",
        column_names=("层", "节点", "构想编号"),
        note="### 转写说明\n\n"
             "原表把「节点名 + 构想编号」成对排布。有两处原表本身就不规整，这里按原样保留：\n\n"
             "- 第 1 行的「坏邻居」在原表里没有配到构想编号，本表编号留空；\n"
             "- 第 12 行第三对位置错位（编号 28 落在节点列），本表按「纯数字即编号」还原为\n"
             "  节点留空、编号 28。",
    ),
    SheetGrid(
        "jy-hidden-enemies", "隐藏出怪表", "jieyuan", 4,
        f"{JIPIBAO_ROOT}/16-隐藏出怪表.json",
        "各节点在普通 / 紧急难度下的隐藏出怪数量，按层分组。",
        mode="pairs", credits="哲三",
        label_col=2, pair_from=3, pair_width=2,
        group_markers=((1, "普通"), (18, "紧急")), orphan_numbers="drop",
        column_names=("难度", "层", "节点", "出怪数"),
    ),
    SheetGrid(
        "jy-collectibles-deer", "去伪存真藏品表（鹿版）", "jieyuan", 5,
        f"{JIPIBAO_ROOT}/08-去伪存真藏品表_鹿版.json",
        "「去伪存真」藏品按星级 × 增益类别的完整列表。",
        mode="matrix", credits="哲三",
        header_row=1, key_col=2, value_from=3,
        row_blocks=((3, 12), (12, 19), (19, 29), (29, 35)),
        column_names=("星级",),
        note="### 转写说明\n\n"
             "原表是「行 = 星级、列 = 类别」的二维表，同一个类别下的藏品在多个单元格里竖着\n"
             "排。本页把每一列的藏品折进同一格、以「、」分隔，行列关系不变。\n\n"
             "原表第 L 列表头是空的（该列在原始文档里没有类别名），本页记为**未标注**，\n"
             "不做归并。",
    ),
    SheetGrid(
        "jy-collectibles-zhe", "去伪存真藏品表（哲版）", "jieyuan", 6,
        f"{JIPIBAO_ROOT}/10-去伪存真藏品表_哲版.json",
        "「去伪存真」藏品按星级 × 我方增益 / 敌方减益 / 其他收益的完整列表，另附美愿机制。",
        mode="matrix", credits="哲三",
        header_row=1, group_row=1, key_col=2, value_from=3,
        row_blocks=((3, 11), (11, 21), (21, 31), (31, 40)),
        column_names=("星级",),
        skip_values=("蓝字：", "红字：", "黄底：", "绿底："),
        note="### 美愿 · 机制\n\n"
             "原表第 42-47 行的「美愿 / 机制」区块：\n\n"
             "| 触发位 | 获取内容 |\n"
             "| --- | --- |\n"
             "| 1 手 | |\n"
             "| 2 书 | 1 |\n"
             "| 3 钱 | ≥150 源石锭则给金酒之杯，≥80 源石锭则给投币玩具（可以重复判定） |\n"
             "| 4 国王 | 血量为 1 则给国王藏品，且顺序为新枪 ＞ 冠冕 ＞ 铠甲 ＞ 延伸 |\n"
             "| 5 魔王 | 2 |\n"
             "| 6 | 随机给一个 |\n\n"
             "> 原表注：判定顺序 1 2 3 4 5 6。\n\n"
             "### 颜色图例\n\n"
             "原表用颜色标注藏品的属性，颜色本身在导出时丢失，图例文字保留如下：\n\n"
             "- **蓝字**：携带部署藏品\n"
             "- **红字**：生存藏品\n"
             "- **黄底**：DLC2 新增\n"
             "- **绿底**：可以美愿定向获取\n\n"
             "藏品列表里的 `△` 与 `※` 等标记沿用原表写法，未做解释（原表也没有解释）。",
    ),
    SheetGrid(
        "jy-ending12-route", "1、2 结局船路线图", "jieyuan", 7,
        f"{JIPIBAO_ROOT}/11-1、2结局船路线图.json",
        "「朝谒」与「魂灵朝谒」两张图上的入口、出口、船与不可部署位置坐标。",
        mode="header", credits="哲三",
        header_row=2, value_from=1,
        note="原表把两张图横向并排放在同一张 sheet 里（左「朝谒」、右「魂灵朝谒」），\n"
             "坐标轴都是 `A-I` 行 × `1-13` 列。列标与原文档一致，可直接对照。",
    ),
    SheetGrid(
        "jy-ending2-dr", "2 结局减伤区域图", "jieyuan", 8,
        f"{JIPIBAO_ROOT}/12-2结局减伤区域图.json",
        "2 结局两张图上「小特」所在格（减伤区域判定用）。",
        mode="header", credits="哲三",
        header_row=4, value_from=1,
        note="原表注（第 3 行）：减伤区域按大小特中心距判定，具体阈值见原文档表头文字——\n"
             "该说明与图表同格导出时被截断，本页只呈现点位。",
    ),
    SheetGrid(
        "jy-layer3-nodes", "三层节点统计（已完成使命）", "jieyuan", 9,
        f"{JIPIBAO_ROOT}/21-三层节点统计_已完成使命.json",
        "三层节点（商店 / 树洞 / 失与得）的样本统计与无效连线数。",
        credits="哲三",
        note="### 说明\n\n"
             "统计口径：素材来源为翻录播 + 群友截图 + 作者自己打，总样本数见原表。\n"
             "原表只有 10 行、四列数字，为保留行列对应关系按原样呈现。",
    ),
    SheetGrid(
        "jy-tongbao", "通宝交换学一图流", "jieyuan", 10,
        f"{JIPIBAO_ROOT}/03-通宝交换学一图流.json",
        "通宝交换规律的图解。**原表内容为图片，本次未取到数据。**",
        mode="placeholder", credits="哲三", tab="z2nfmv",
        sheet_name="通宝交换学一图流",
        note="### 资料缺口\n\n"
             "这张子表的内容是**直接贴在表格上的图片**（一图流本身），表格里没有任何\n"
             "单元格数据。匿名接口取到的 `grid` 是空的——不是抓取失败，是原表里就没有\n"
             "可抓的数据。\n\n"
             "要补齐只有两条路：由文档作者另出图，或人工截图后走本站的图片管道。\n"
             "在此之前本页只保留位置与说明，**不做任何推测性重绘**。",
    ),
    SheetGrid(
        "jy-finale-route", "终曲合声路线图", "jieyuan", 11,
        f"{JIPIBAO_ROOT}/09-终曲合声路线图.json",
        "「终曲合声」的路线图解。**原表内容为图片，本次未取到数据。**",
        mode="placeholder", credits="哲三", tab="2l32je",
        sheet_name="终曲合声路线图",
        note="### 资料缺口\n\n"
             "与「通宝交换学一图流」同样的情况：原表把图片贴在单元格上，没有任何数据。\n"
             "这张表连数据块都没导出成功（接口返回「block 里没有找到 f19 数据块」），\n"
             "更确认了内容不在单元格里。\n\n"
             "补齐方式同上：等作者出图或人工截图。**不做推测性重绘。**",
    ),
    # ---------- 通用机制（跨期） ----------
    SheetGrid(
        "gen-exp", "经验表", "gen", 1,
        f"{JIPIBAO_ROOT}/05-经验表.json",
        "各层作战经验、指挥等级升级需求与等级效果。",
        note="### 表内叠了三张表\n\n"
             "原表把三部分内容叠在同一张 sheet 里，本页按原样整片呈现，读的时候注意边界：\n\n"
             "- 第 4-14 行：按层数的作战经验（普通 / 紧急 / boss / 特殊），以及「狗鸭熊鼠」\n"
             "  与「其他」两组按关卡计的经验；\n"
             "- 第 17-29 行：指挥等级 → 升级需求经验值与等级效果（希望、携带、生命值上限、\n"
             "  思维上限）。\n\n"
             "行号列即原文档行号，可直接对照。",
    ),
    SheetGrid(
        "gen-ingot", "源石锭表", "gen", 2,
        f"{JIPIBAO_ROOT}/06-源石锭表.json",
        "普通 / 紧急 / boss 与「片瓣」两类节点在各层掉落的源石锭数量。",
        mode="sections", credits="哲三",
        label_col=1, value_from=2,
        blocks=(("正常", 2, 7), ("片瓣", 7, 11)),
        note="原表把「正常」与「片瓣」两块上下叠放，表头各自独立；本页合并成一张表，\n"
             "用「分类」列区分，空位即原表留空。",
    ),
    SheetGrid(
        "gen-random-events", "不期而遇事件表（多期并排）", "gen", 3,
        f"{JIPIBAO_ROOT}/07-不期而遇事件表.json",
        "横向并排的多期「不期而遇」对照表（一层至七层 × 效果 / 备注）。",
        credits="哲三",
        note="### 一张 sheet 里并排放着四期\n\n"
             "原表横向拼了四组「不期而遇」表，每组各有自己的层数列、效果列与备注列，分组\n"
             "标题写在组首单元格里。导出后合并单元格只剩左上角，所以组首之外的位置是空的。\n"
             "本页按原样整片呈现，列标与原文档一致，可直接对照。",
    ),
    SheetGrid(
        "gen-boss", "BOSS 数值表", "gen", 4,
        f"{JIPIBAO_ROOT}/13-BOSS数值表.json",
        "各期 BOSS 的攻击 / 血量 / 防御 / 法抗原始数据，以及年代与结局带来的乘区。",
        credits="哲三（原始数据来自 tomimi.dev）",
        note="### 说明\n\n"
             "原表左半是各 BOSS 的攻击方式与三维数值（含「移速」这类只对部分 BOSS 生效的\n"
             "行），右半是年代 / 结局乘区。原表注释：蓝色为法伤、橙色为物伤、粉色为真伤；\n"
             "「←」表示该项在乘算之前生效。\n\n"
             "行号列即原文档行号，数值一律取自原表，**未做任何换算**。",
    ),
    SheetGrid(
        "gen-eras", "年代表", "gen", 5,
        f"{JIPIBAO_ROOT}/14-年代表.json",
        "年代数值矩阵。**原表没有表头，列义见原文档表外说明，本页不做解释。**",
        credits="哲三",
        note="### 读法\n\n"
             "原表是一张 8 行的数字矩阵，没有表头——行与列的含义由原文档表格之外的说明\n"
             "给出，导出时并不带上这些说明。因此本页只按原样呈现数字，**不解释列义**，\n"
             "避免凭空推测。",
    ),
    SheetGrid(
        "gen-narrow-encounter", "狭路相逢表", "gen", 6,
        f"{JIPIBAO_ROOT}/17-狭路相逢表.json",
        "「狭路相逢」四种场景的经验、招募券与奖励档位。",
        credits="哲三",
        note="### 读法\n\n"
             "原表把「按遭遇」与「按等级」两张小表叠放。后者（第 6 行起）的列是 `1 级 /\n"
             "2 级 / 3 级 / 平局`，与前半张表的列含义不同，本页按原样呈现、不做合并，\n"
             "读的时候注意分界。",
    ),
    SheetGrid(
        "gen-shop-rare", "商店高级藏品表", "gen", 7,
        f"{JIPIBAO_ROOT}/18-商店高级藏品表.json",
        "商店里能直接买到的高级藏品，以及需要加固才能出现的部分。",
        mode="melt", credits="哲三",
        value_from=2, blocks=(("普通商店就有", 4, 8), ("贵重加固才有", 9, 11),
                              ("黑色职业书", 17, 19), ("手", 20, 21)),
        column_names=("分类", "藏品"),
        note="### 加固后的高级藏品数量\n\n"
             "| 加固后概率 | 数量 |\n"
             "| --- | --- |\n"
             "| 4% | 1 个高级 |\n"
             "| 46% | 2 个高级 |\n"
             "| 46% | 3 个高级 |\n"
             "| 4% | 4 个高级 |\n\n"
             "> 原表注：不包括黑色职业书和手。",
    ),
    SheetGrid(
        "gen-shop-stats", "商店统计", "gen", 8,
        f"{JIPIBAO_ROOT}/19-商店统计.json",
        "各高级藏品在统计中出现的次数。",
        mode="melt", credits="哲三",
        value_from=4, row_pairs=((1, 2), (4, 5), (10, 11), (13, 14)),
        column_names=("藏品", "出现次数"),
        note="### 一次商店出现的高级藏品数\n\n"
             "原表左侧区块（第 2-5 行）：\n\n"
             "| 高级藏品数 | 次数 |\n"
             "| --- | --- |\n"
             "| 1 个 | 5 |\n"
             "| 2 个 | 34 |\n"
             "| 3 个 | 29 |\n"
             "| 4 个 | 5 |",
    ),
    SheetGrid(
        "gen-lixue-manual", "里雪的计算手册", "gen", 9,
        f"{JIPIBAO_ROOT}/20-里雪的计算手册.json",
        "按藏品类别整理的攻击力 / 防御力加成速查（作者：里雪）。",
        credits="哲三 收录（原表作者：里雪）",
        note="### 说明\n\n"
             "原表是一份竖排速查表：分类标题单独占一行，下面几行罗列该类别下各藏品的加成\n"
             "（如「折戟-破釜沉舟（+30）」）。这种排法在单元格网格里就是「一行一个标题、\n"
             "下面若干行内容」，本页按原样呈现。",
    ),
    # ---------- 仙术杯 #6 赛事数据 ----------
    SheetGrid(
        "xs6-players", "仙术杯#6 选手统计", "xianshu", 1,
        f"{JIPIBAO_ROOT}/22-仙术杯#6_选手统计.json",
        "仙术杯#6 选手逐节点统计（573 行 × 28 列）。",
        credits="哲三 等（赛事数据）",
        note="### 说明\n\n"
             "原表用多行表头描述「开局 / 层数 / 各层节点」的层级关系；合并单元格导出后只\n"
             "保留左上角，因此表头的层级要对照原文档阅读。\n\n"
             "本页保留全部单元格。表格上方的筛选框可按选手或节点名检索。",
    ),
    SheetGrid(
        "xs6-finance", "仙术杯#6 财报", "xianshu", 2,
        f"{JIPIBAO_ROOT}/23-仙术杯#6_财报.json",
        "仙术杯#6 每日各选手的上贡金额与取钱金额。",
        mode="header", credits="哲三 等（赛事数据）",
        header_row=1, value_from=1, fill_down=(0,),
        column_names=("比赛日", "选手", "上贡金额", "取钱金额"),
        note="原表第 1 行是表头，第 1 列按比赛日分组（`day1`…）；空白处表示与上一行\n"
             "同属该比赛日，本页已按列向下填充，便于筛选。",
    ),
]


# ---------- 转换 ----------


class ImportReport:
    def __init__(self) -> None:
        self.skipped: list[str] = []
        self.media: dict[str, object] = {}
        self.credits: list[str] = []

    def skip(self, reason: str) -> None:
        self.skipped.append(reason)


def _front_matter(meta: dict[str, str]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if value not in ("", None):
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _media_entry(origin: str, max_edge: int = 1920) -> dict:
    return {"source": origin, "max_edge": max_edge}


def _write_gallery(
    source: Path, game: str, spec: Gallery, report: ImportReport,
) -> str | None:
    directory = source / spec.directory
    if not directory.is_dir():
        report.skip(f"{game}/{spec.slug}：目录不存在 {spec.directory}")
        return None
    images = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}),
        key=lambda p: natural_key(p.stem),
    )
    if not images:
        report.skip(f"{game}/{spec.slug}：目录内没有图片")
        return None

    lines: list[str] = []
    if spec.intro:
        lines.append(spec.intro)
    for index, image in enumerate(images, start=1):
        key = f"{game}/{spec.slug}/{index:02d}{image.suffix.lower()}"
        report.media[key] = _media_entry(f"{spec.directory}/{image.name}")
        lines.append(f"![{image.stem}](/media/{key})")
    meta = {
        "title": spec.title,
        "group": spec.group,
        "order": spec.order,
        "summary": spec.summary,
    }
    return _front_matter(meta) + "\n" + "\n\n".join(lines) + "\n"


def _write_table(
    source: Path, game: str, spec: Table, report: ImportReport,
) -> str | None:
    path = source / spec.source
    if not path.is_file():
        report.skip(f"{game}/{spec.slug}：源文件缺失 {spec.source}")
        return None
    try:
        sheets = extract_sheets(path, path.suffix.lower())
    except OoxmlError as error:
        report.skip(f"{game}/{spec.slug}：{spec.source} 解析失败（{error}）")
        return None

    match = next((rows for title, rows in sheets if title == spec.sheet), None)
    if match is None:
        available = ", ".join(title for title, _ in sheets)
        report.skip(f"{game}/{spec.slug}：{spec.source} 中不存在工作表 {spec.sheet}（现有：{available}）")
        return None

    rows = [row for row in match if any(cell.strip() for cell in row)]
    rows = rows[spec.skip_rows:]
    if not rows:
        report.skip(f"{game}/{spec.slug}：工作表 {spec.sheet} 没有有效数据")
        return None

    columns = [_clean(cell) for cell in rows[0]]
    body = [row for index, row in enumerate(rows[1:]) if index not in spec.drop_rows]
    # 留空表示「同上」的列按需向下填充：合成表的 Lv / 名称 就是这种写法。
    for column in spec.fill_down:
        carried = ""
        for row in body:
            if column < len(row):
                if row[column].strip():
                    carried = row[column]
                else:
                    row[column] = carried

    payload = {
        "caption": spec.caption or f"{spec.title}（取自 {Path(spec.source).name} · 工作表 {spec.sheet}）",
        "columns": columns,
        "rows": [[_clean(cell) for cell in row[: len(columns)]] for row in body],
        "credits": [],
    }
    data_path = CONTENT_ROOT / DATA_DIR / game / f"{spec.slug}.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    meta = {
        "title": spec.title,
        "group": spec.group,
        "order": spec.order,
        "summary": spec.summary,
        "data": f"{game}/{spec.slug}",
    }
    return _front_matter(meta) + "\n" + (spec.summary or "") + "\n"


def _column_letter(index: int) -> str:
    """0 → A、25 → Z、26 → AA。跟原文档的列标一致，方便读者回原表对照。"""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _load_grid(path: Path) -> tuple[str, str, list[list[str]]]:
    """读导出文件，返回 (tab id, 子表名, 网格)。补齐交给 `_trim_grid`。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    grid = payload.get("grid") or []
    rows = [["" if cell is None else str(cell) for cell in row] for row in grid]
    return str(payload.get("tab", "")), str(payload.get("name", "")), rows


def _trim_grid(rows: list[list[str]]) -> tuple[list[list[str]], int]:
    """裁掉尾部全空的行与列，并把行补成等宽。

    注意**不能裁首行**：`grid` 模式要保留原文档行号，行号就是位置语义的一部分。
    补等宽是必须的——导出数据的行是参差的，后面每个 mode 都按下标取值。
    """
    kept = [list(row) for row in rows]
    while kept and not any(cell.strip() for cell in kept[-1]):
        kept.pop()
    width = max((len(row) for row in kept), default=0)
    for row in kept:
        row.extend([""] * (width - len(row)))
    while width and not any(row[width - 1].strip() for row in kept):
        width -= 1
    return kept, width


def _is_credit(cell: str) -> bool:
    return bool(_CREDIT_CELL.search(cell))


def _is_number(cell: str) -> bool:
    return cell.strip().isdigit()


def _grid_payload(spec: SheetGrid, rows: list[list[str]], width: int) -> tuple[list[str], list[list[str]], str]:
    """按 mode 把网格转成 (columns, rows, caption)。"""

    def cell(i: int, j: int) -> str:
        return rows[i][j] if i < len(rows) and j < len(rows[i]) else ""

    def junk(value: str) -> bool:
        """署名格与颜色图例格：不是数据，但各自在正文里另有着落。"""
        return _is_credit(value) or (bool(spec.skip_values) and value.startswith(spec.skip_values))

    if spec.mode == "grid":
        columns = ["行"] + [_column_letter(j) for j in range(width)]
        body = [[str(index + 1)] + row[:width]
                for index, row in enumerate(rows) if any(c.strip() for c in row)]
        return columns, body, "原表网格：行号与原文档一致，列号为原文档列标，空格即原表留空。"

    if spec.mode == "header":
        # 原表最左边常有一整列空的（图表的外框/刻度区），用 value_from 跳过它。
        start = spec.value_from
        columns = list(spec.column_names) or [cell(spec.header_row, j) for j in range(start, width)]
        body = [row[start:start + len(columns)]
                for row in rows[spec.header_row + 1:] if any(c.strip() for c in row)]
        for column in spec.fill_down:
            carried = ""
            for row in body:
                if column >= len(row):
                    continue
                if row[column].strip():
                    carried = row[column]
                else:
                    row[column] = carried
        return columns, body, "表头取自原表第 %d 行。" % (spec.header_row + 1)

    if spec.mode == "sections":
        labels: list[str] = []
        for _, start, _end in spec.blocks:
            for name in rows[start][spec.value_from:width]:
                if name.strip() and name not in labels:
                    labels.append(name)
        columns = ["分类", "项目"] + labels
        body = []
        for label, start, end in spec.blocks:
            head = rows[start][spec.value_from:width]
            slot = {name: labels.index(name) for name in head if name.strip()}
            for offset, row in enumerate(rows[start + 1:end]):
                if not any(c.strip() for c in row):
                    continue
                values = [""] * len(labels)
                for position, name in enumerate(head):
                    if name.strip():
                        values[slot[name]] = cell(start + 1 + offset, spec.value_from + position)
                body.append([label, row[spec.label_col]] + values)
        return columns, body, "原表分「%s」若干块，此处合并成一张表，用「分类」列区分。" % "」「".join(
            label for label, _s, _e in spec.blocks)

    if spec.mode == "matrix":
        raw = [cell(spec.header_row, j).strip() for j in range(spec.value_from, width)]
        if spec.group_row >= 0:
            carried = ""
            grouped = []
            for name in raw:
                carried = name or carried
                grouped.append(carried)
            raw = grouped
        counts: dict[str, int] = {}
        for name in raw:
            counts[name] = counts.get(name, 0) + 1
        seen: dict[str, int] = {}
        labels = []
        for name in raw:
            if counts.get(name, 1) > 1:
                seen[name] = seen.get(name, 0) + 1
                labels.append(f"{name}·{seen[name]}")
            else:
                labels.append(name)
        title = spec.column_names[0] if spec.column_names else "分类"
        columns = [title] + [name or "未标注" for name in labels]
        body = []
        for start, end in spec.row_blocks:
            values = []
            for j in range(spec.value_from, width):
                items = [cell(i, j).strip() for i in range(start, end)]
                values.append("、".join(item for item in items if item and not junk(item)))
            body.append([cell(start, spec.key_col)] + values)
        return columns, body, "原表为「行 = %s、列 = 类别」的二维表，同一格的多个条目以「、」分隔。" % title

    if spec.mode == "melt":
        columns = list(spec.column_names) or ["分类", "名称"]
        body = []
        if spec.row_pairs:
            for head_row, value_row in spec.row_pairs:
                for j in range(spec.value_from, width):
                    name = cell(head_row, j).strip()
                    if name and not junk(name):
                        body.append([name, cell(value_row, j).strip()])
        else:
            for label, start, end in spec.blocks:
                for row in rows[start:end]:
                    for item in row[spec.value_from:width]:
                        item = item.strip()
                        if item and not junk(item):
                            body.append([label, item])
        return columns, body, "原表是横向铺开的清单，此处转成「分类 + 名称」两列，便于检索。"

    if spec.mode == "pairs":
        columns = list(spec.column_names)
        markers = dict(spec.group_markers)
        body = []
        group = ""
        carried = ""
        for index, row in enumerate(rows):
            if index in markers:
                group = markers[index]
                carried = ""
                continue
            if not any(c.strip() for c in row):
                continue
            current = cell(index, spec.label_col).strip()
            if current:
                carried = current
            for j in range(spec.pair_from, width, spec.pair_width):
                name = cell(index, j).strip()
                value = cell(index, j + 1).strip()
                if not name or junk(name):
                    continue
                if _is_number(name) and not value:
                    # 原表偶尔把编号写进了名称格（或在名称格留下一个行号）。编号一定是
                    # 纯数字、节点名一定不是，据此还原。
                    if spec.orphan_numbers == "drop":
                        continue
                    name, value = "", name
                body.append([group, carried, name, value] if markers else [carried, name, value])
        return columns, body, "原表按「%s + 数值」成对铺开，此处转成逐行一条。" % columns[-2]

    raise ValueError(f"未知的转写方式：{spec.mode}")


def _sheet_page(spec: SheetGrid, tab: str, sheet_name: str,
                row_count: int, caption: str) -> str:
    meta = {
        "title": spec.title,
        "group": spec.group,
        "order": spec.order,
        "summary": spec.summary,
        "data": f"arknights/{spec.slug}" if row_count else "",
    }
    lines = [spec.summary]
    if row_count:
        lines.append(f"共 {row_count} 行。{caption}")
    if spec.note:
        lines.append(spec.note)
    origin = f"子表「{sheet_name}」" if sheet_name else "对应子表"
    if tab:
        origin += f"（tab `{tab}`）"
    lines.append(
        "## 出处\n\n"
        f"本页数据取自腾讯文档《集批宝典》{origin}，由 **{spec.credits}** 整理。"
        "转写过程**未修改、未补全任何数值**；合并单元格导出后只有左上角有值，"
        "因此表里的空格是原始形态。\n\n"
        # `mdrender` 不支持 `<url>` 自动链接语法，必须写完整的 Markdown 链接。
        f"原文档：[腾讯文档《集批宝典》]({JIPIBAO_DOC})"
    )
    return _front_matter(meta) + "\n" + "\n\n".join(lines) + "\n"


def _write_sheet(
    source: Path, game: str, spec: SheetGrid, report: ImportReport,
) -> str | None:
    path = source / spec.source

    if spec.mode == "placeholder":
        # 图片型子表没有可用的 grid；文件在就顺手取它的真实名称，不在也不影响出页。
        tab, sheet_name = spec.tab, spec.sheet_name
        if path.is_file():
            try:
                loaded_tab, loaded_name, _grid = _load_grid(path)
                tab, sheet_name = loaded_tab or tab, loaded_name or sheet_name
            except (json.JSONDecodeError, ValueError) as error:
                report.skip(f"{game}/{spec.slug}：{spec.source} 解析失败（{error}）")
        else:
            report.skip(f"{game}/{spec.slug}：导出文件缺失 {spec.source}（占位页仍会生成）")
        return _sheet_page(spec, tab, sheet_name, 0, "")

    if not path.is_file():
        report.skip(f"{game}/{spec.slug}：源文件缺失 {spec.source}")
        return None
    try:
        tab, sheet_name, grid = _load_grid(path)
    except (json.JSONDecodeError, ValueError) as error:
        report.skip(f"{game}/{spec.slug}：{spec.source} 解析失败（{error}）")
        return None

    rows, width = _trim_grid(grid)
    if not rows or not width:
        report.skip(f"{game}/{spec.slug}：子表没有任何单元格数据（内容可能全是图片）")
        return None

    try:
        columns, body, caption = _grid_payload(spec, rows, width)
    except (IndexError, KeyError, ValueError) as error:
        report.skip(f"{game}/{spec.slug}：按 {spec.mode} 转写失败（{error}）")
        return None
    if not body:
        report.skip(f"{game}/{spec.slug}：按 {spec.mode} 转写后没有任何数据行")
        return None

    payload = {
        "caption": caption,
        "columns": columns,
        "rows": [[_clean(str(item)) for item in row] for row in body],
        "credits": [],
    }
    data_path = CONTENT_ROOT / DATA_DIR / game / f"{spec.slug}.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return _sheet_page(spec, tab or spec.tab, sheet_name, len(payload["rows"]), caption)


def _clean(cell: str) -> str:
    """清掉单元格里的换行与多余空白，避免撑破表格布局。"""
    return re.sub(r"\s+", " ", cell.replace("\x00", "")).strip()


def extract_cell_credit(cell: str) -> tuple[str, str]:
    """从单元格里摘出署名/链接，返回 (剩余内容, 署名)。

    素材作者的署名常常直接接在最后一条数据后面（填字游戏的末行就是
    「1.27 千年九尾狐狸精 作者：猎猫人老贾 https://…」），不摘出来会让整行数据被署名污染。
    """
    match = _ATTRIBUTION.search(cell)
    if not match:
        return cell, ""
    return cell[: match.start()].strip(), cell[match.start():].strip()


def _lined_table(lines: list[str], spec: "Text") -> tuple[str, list[str]]:
    """把清单式文本按行拆成 Markdown 表格。"""
    credits: list[str] = []
    rows: list[list[str]] = []
    separator = re.compile(spec.split)
    width = len(spec.columns)
    for line in lines:
        if not line.strip():
            continue
        cells = [part.strip() for part in separator.split(line.strip(), maxsplit=width - 1)]
        cells += [""] * (width - len(cells))
        for index, cell in enumerate(cells):
            trimmed, credit = extract_cell_credit(cell)
            if credit:
                cells[index] = trimmed
                credits.append(credit)
        rows.append(cells)

    header = "| " + " | ".join(spec.columns) + " |"
    divider = "| " + " | ".join("---" for _ in spec.columns) + " |"
    body = [
        "| " + " | ".join(cell.replace("|", r"\|") or " " for cell in row) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body]), credits


def _write_text(
    source: Path, game: str, spec: Text, report: ImportReport,
) -> str | None:
    path = source / spec.source
    if not path.is_file():
        report.skip(f"{game}/{spec.slug}：源文件缺失 {spec.source}")
        return None

    suffix = path.suffix.lower()
    if suffix == ".docx":
        try:
            raw = extract_text(path, ".docx")
        except OoxmlError as error:
            report.skip(f"{game}/{spec.slug}：{spec.source} 解析失败（{error}）")
            return None
        encoding = "utf-8"
    else:
        raw, encoding = read_text(path)

    lines, credits = split_attribution(raw.splitlines())
    if spec.columns:
        body, cell_credits = _lined_table(lines, spec)
        credits.extend(cell_credits)
    else:
        body = paragraphs_to_markdown(lines)
    report.credits.extend(credits)

    if not body.strip():
        report.skip(f"{game}/{spec.slug}：{spec.source} 没有可用正文（编码 {encoding}）")
        return None

    meta = {
        "title": spec.title,
        "group": spec.group,
        "order": spec.order,
        "summary": spec.summary,
    }
    note = f"\n\n> 原始文件：`{spec.source}`（编码 {encoding}）"
    return _front_matter(meta) + "\n" + body + credits_block(credits) + note + "\n"


def _write_palace(
    source: Path, game: str, spec: Palace, rows_by_sheet: dict[str, list[list[str]]],
    report: ImportReport,
) -> str | None:
    directory = source / spec.directory
    if not directory.is_dir():
        report.skip(f"{game}/{spec.slug}：目录不存在 {spec.directory}")
        return None

    images = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}),
        key=lambda p: natural_key(p.stem),
    )
    lines: list[str] = []
    if spec.summary:
        lines.append(spec.summary)

    # 注意事项取自目录内的说明文件，放在地图之前更符合阅读顺序
    notes = []
    for name in spec.notes:
        note_path = source / name
        if not note_path.is_file():
            report.skip(f"{game}/{spec.slug}：注意事项缺失 {name}")
            continue
        raw, _ = read_text(note_path)
        note_lines, credits = split_attribution(raw.splitlines())
        report.credits.extend(credits)
        text = paragraphs_to_markdown(note_lines)
        if text:
            notes.append(text)
    if notes:
        lines.append("## 注意事项")
        lines.extend(_blockquote(text) for text in notes)

    rows = rows_by_sheet.get(spec.sheet)
    if rows:
        table = _rows_to_markdown(rows)
        lines.append(f"## 敌人弱点")
        lines.append(table)
    else:
        report.skip(f"{game}/{spec.slug}：未找到工作表「{spec.sheet}」的敌人表")

    if images:
        lines.append("## 走法地图")
        for index, image in enumerate(images, start=1):
            key = f"{game}/{spec.slug}/{index:02d}{image.suffix.lower()}"
            report.media[key] = _media_entry(f"{spec.directory}/{image.name}", max_edge=2200)
            lines.append(f"![{image.stem}](/media/{key})")
    else:
        report.skip(f"{game}/{spec.slug}：目录内没有地图图片")

    # 与新岛殿堂目录平级的图表（合成公式、面具性格等），归入同一页的补充区
    if spec.extra_media:
        charts: list[str] = []
        for index, name in enumerate(spec.extra_media, start=1):
            origin = f"{P5R_ROOT}/{name}"
            path = source / origin
            if not path.is_file():
                report.skip(f"{game}/{spec.slug}：补充图表缺失 {origin}")
                continue
            key = f"{game}/{spec.slug}/chart-{index:02d}{path.suffix.lower()}"
            report.media[key] = _media_entry(origin, max_edge=2200)
            charts.append(f"![{path.stem}](/media/{key})")
        if charts:
            lines.append("## 合成公式与面具性格")
            lines.extend(charts)

    meta = {
        "title": spec.title,
        "group": "palace",
        "order": spec.order,
        "summary": spec.summary,
    }
    return _front_matter(meta) + "\n" + "\n\n".join(lines) + "\n"


def _blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines())


def _rows_to_markdown(rows: list[list[str]]) -> str:
    """把工作表行转成 Markdown 管道表格。"""
    width = max(len(row) for row in rows)
    padded = [[_clean(cell) for cell in row] + [""] * (width - len(row)) for row in rows]
    header, body = padded[0], padded[1:]
    lines = [
        "| " + " | ".join(cell or " " for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(cell.replace("|", r"\|") or " " for cell in row) + " |")
    return "\n".join(lines)


def _collect_sheet_rows(source: Path, workbook: str) -> dict[str, list[list[str]]]:
    """读取一个工作簿的所有工作表，供殿堂页取用敌人表。"""
    path = source / workbook
    if not path.is_file():
        return {}
    try:
        sheets = extract_sheets(path, ".xlsx")
    except OoxmlError:
        return {}
    collected = {}
    for title, rows in sheets:
        cleaned = [row for row in rows if any(cell.strip() for cell in row)]
        if cleaned:
            collected[title] = cleaned
    return collected


def import_all(source: Path = DEFAULT_SOURCE, content: Path = CONTENT_ROOT) -> ImportReport:
    """执行导入，写出 content/<game>/*.md 与 content/media.json。"""
    source = Path(source)
    report = ImportReport()
    if not source.is_dir():
        raise FileNotFoundError(f"素材目录不存在：{source}")

    palace_enemies = _collect_sheet_rows(source, f"{P5R_ROOT}/P5R日程攻略简体版.xlsx")

    for spec in PALACES:
        page = _write_palace(source, "p5r", spec, palace_enemies, report)
        if page:
            _write_page(content, "p5r", spec.slug, page)

    for spec in (*P5R_TABLES, *P5R_TEXT, *P5R_MISC, *P5R_DAILY):
        page = (
            _write_table(source, "p5r", spec, report)
            if isinstance(spec, Table)
            else _write_text(source, "p5r", spec, report)
        )
        if page:
            _write_page(content, "p5r", spec.slug, page)

    for spec in (*P3P_GALLERIES, *P3P_TABLES, *P3P_TEXT):
        page = (
            _write_gallery(source, "p3p", spec, report)
            if isinstance(spec, Gallery)
            else _write_table(source, "p3p", spec, report)
            if isinstance(spec, Table)
            else _write_text(source, "p3p", spec, report)
        )
        if page:
            _write_page(content, "p3p", spec.slug, page)

    for spec in (*P4G_GALLERIES, *P4G_TABLES, *P4G_TEXT, *P4G_MONTHS):
        page = (
            _write_gallery(source, "p4g", spec, report)
            if isinstance(spec, Gallery)
            else _write_table(source, "p4g", spec, report)
            if isinstance(spec, Table)
            else _write_text(source, "p4g", spec, report)
        )
        if page:
            _write_page(content, "p4g", spec.slug, page)

    # 明日方舟的素材是《集批宝典》导出网格，转换逻辑与 xlsx 那条链不同。
    # 首页 `arknights/index.md` 是人工写的总览（含误入奇境的读图规则与坐标口径），
    # 刻意不在这里重生成——构建脚本把人工导读冲掉是最容易发生的静默事故。
    for spec in ARKNIGHTS_SHEETS:
        page = _write_sheet(source, "arknights", spec, report)
        if page:
            _write_page(content, "arknights", spec.slug, page)

    # 游戏首页
    _write_page(content, "p5r", "index", _index_page(
        "p5r", "P5R 皇家版", "女神异闻录 5 皇家版攻略总览：殿堂走法、人格面具图鉴、合成表与逐日日程。"))
    _write_page(content, "p3p", "index", _index_page(
        "p3p", "P3P 携带版", "女神异闻录 3 携带版攻略：男女主双线日程、全面具合成与装备获取。"))
    _write_page(content, "p4g", "index", _index_page(
        "p4g", "P4G 黄金版", "女神异闻录 4 黄金版攻略：流程、技能卡、支线任务与成就。"))

    media_path = content / "media.json"
    if media_path.is_file():
        existing = json.loads(media_path.read_text(encoding="utf-8"))
        report.media = {**existing, **report.media}
    media_path.write_text(
        json.dumps(report.media, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _write_page(content: Path, game: str, slug: str, body: str) -> None:
    target = Path(content) / game / f"{slug}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _index_page(game: str, title: str, summary: str) -> str:
    meta = {"title": title, "order": 0, "summary": summary}
    return _front_matter(meta) + f"\n{summary}\n\n左侧按分组浏览本站全部内容。\n"


def main() -> None:
    report = import_all()
    print(f"导入完成：媒体条目 {len(report.media)} 个，署名行 {len(report.credits)} 条，跳过 {len(report.skipped)} 项")
    for item in report.skipped:
        print(f"  跳过：{item}")


if __name__ == "__main__":
    main()
