"""把 `library/` 里的原始素材导入成 wiki 内容源（`content/`）。

素材是「攻略作者打包分享的文件」：txt / docx / xlsx / 截图混在一起，命名靠人肉约定，
编码不统一，表格里有大量留空表示「同上」。这个模块的职责就是把这些不规则的东西
变成可重复生成的规范内容源，并且**明确记录哪些内容没有导入、为什么**——
静默丢内容是这类工具最危险的失败方式。

三类页面：
- 图集页：一个目录下的截图，按自然序排列，文件名作为图注
- 表格页：xlsx 的某个工作表，转成结构化数据（`content/data/…json`）
- 文本页：txt/docx，转成 Markdown 段落

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
