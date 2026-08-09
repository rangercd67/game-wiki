# 江城创业记 · 产线计算器（量化计算器网页版）

把用户自写的 Excel 计算器（`江城创业记量化计算器v4.1`，适用游戏版本 V0.7.8.0809.1）改造成的**纯前端产线计算器网站**。

配方数据来源：<https://wiki.biligame.com/jiangcity/产物配方>

## 它能做什么

- 按 **14 个分类**浏览 77 种产物配方 + 11 种基础原料
- 搜索产物、查看配方、计算产线、汇总材料
- 支持 **4 级传送带效率**（1/2/3/4 个/秒，当前进度为 2/s）
- 两种机器配平模式：
  - **LCM 自动扩展配平**（推荐）：需求量按最小公倍数倍率放大，机器台数全整数
  - **向上取整版**（已弃用但保留）：`Math.ceil` 直接取整，含溢出率统计
- 多版可视化：三链树图、共享 DAG、交互版、区块布局蓝图（含区内传送带连线）

## 目录结构

| 文件 | 用途 |
|------|------|
| `index.html` / `css/style.css` / `js/data.js` / `js/app.js` | 主网站（配方库 + 计算器） |
| `js/data.js` | 数据：`RECIPES` / `RAW_RESOURCES` / `ALL_ITEMS` / `MACHINE_POWER` / `CONVEYOR_BELTS` |
| `compute-bgr.js` + `bgr-result.json` | 50蓝/180绿/600红 配平计算（倍率 ×540，总机器 13770 台） |
| `compute-ceil.js` + `ceil-result.json` | 向上取整版（38 台 / 148kW / 29 带 + 额外产出表） |
| `validate.py` | 数据完整性校验（77 配方 + 11 原料，引用无遗漏） |
| `gen-lines.js` → `production-lines.html` | 红/绿/蓝 三条独立树状图 |
| `gen-merged.js` → `merged-line.html` | 共享 DAG（铁锭/铜锭只画一次） |
| `gen-merged-interactive.js` → `merged-line.html` | 交互版（缩放/平移/悬停/隔离模式/点击高亮） |
| `gen-layout.js` → `layout.html` | 4 区块蓝图（**失败：区内未连线**） |
| `gen-layout2.js` → `layout2.html` | **最终交付**：区内机器↔机器传送带 + 原料直入喂料带 + 点机器高亮整条产线 |
| `generate-bus.js` → `bus.svg` | 总线图（**已废弃**：2/s 带速下 main bus 不成立） |

## 如何运行

```bash
cd jiangcity-calculator
python -m http.server 9527
# 浏览器打开 http://localhost:9527
```

> 端口 9527 是因为 8080 被占用；如冲突可换任意空闲端口。

## 核心设计判断

- **不做 main bus（主干总线）**：当前 2/s 带速上限仅 4/s，长途总线拉不动，采用「冶炼中枢集中 + 区块本地化短带」。
- **配平优先于取整**：小数机器是假精度，LCM 扩展配平给出可落地的整数台数。
- 见 `CONVERSATION.md` 了解完整协作过程与每一版的取舍。

## 当前本地预览

<http://localhost:9527>（需先启动上面的 http.server）
