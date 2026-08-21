/**
 * 江城创业记 - 产物配方数据库
 * 数据来源: https://wiki.biligame.com/jiangcity/产物配方
 * 适用版本: V0.7.8.0809.1
 */

// ========== 传送带数据 ==========
// 传送带等级：每秒传输物品数
const CONVEYOR_BELTS = [
  { level: 1, rate: 1, name: "1级传送带" },
  { level: 2, rate: 2, name: "2级传送带" },
  { level: 3, rate: 3, name: "3级传送带" },
  { level: 4, rate: 4, name: "4级传送带" },
];

// ========== 机器功耗数据 (kw/s) ==========
const MACHINE_POWER = {
  "制作台": 0,
  "制造机": 4,
  "组装机": 18,
  "合成机": 64,
  "冶炼器": 5,
  "熔炉": 5,
  "熔铸机": 16,
  "核心充能器": 20,
  "晶体置换机": 18,
  "粮食处理器": 8,
  "生产间": 0,
};

// 机器等级（用于功耗优化推荐）
const MACHINE_TIER = {
  "制作台": 0,
  "制造机": 1,
  "组装机": 2,
  "合成机": 3,
  "冶炼器": 1,
  "熔炉": 1,
  "熔铸机": 2,
  "核心充能器": 2,
  "晶体置换机": 2,
  "粮食处理器": 1,
  "生产间": 1,
};

// ========== 基础原料（采集获取，无配方） ==========
const RAW_RESOURCES = [
  { id: "原木", name: "原木", category: "raw", isRaw: true },
  { id: "石头", name: "石头", category: "raw", isRaw: true },
  { id: "铁矿石", name: "铁矿石", category: "raw", isRaw: true },
  { id: "铜矿石", name: "铜矿石", category: "raw", isRaw: true },
  { id: "沙子", name: "沙子", category: "raw", isRaw: true },
  { id: "煤矿石", name: "煤矿石", category: "raw", isRaw: true },
  { id: "粮食", name: "粮食", category: "raw", isRaw: true },
  { id: "兽皮", name: "兽皮", category: "raw", isRaw: true },
  { id: "蛛丝", name: "蛛丝", category: "raw", isRaw: true },
  { id: "桶装石油", name: "桶装石油", category: "raw", isRaw: true },
  { id: "有机能量块", name: "有机能量块", category: "raw", isRaw: true },
];

// ========== 产物配方数据 ==========
const RECIPES = [
  // --- 木材系列 ---
  { id: "木材", name: "木材", category: "wood", equipment: ["制作台","制造机","组装机","合成机"], unlock: "完成任务[结识林山石]", inputs: [{item:"原木",qty:1}], output: 1, time: 3, clicks: 3 },
  { id: "木板", name: "木板", category: "wood", equipment: ["制作台","制造机","组装机","合成机"], unlock: "完成任务[购买资源场]", inputs: [{item:"木材",qty:1}], output: 1, time: 3, clicks: 3 },
  { id: "木棒", name: "木棒", category: "wood", equipment: ["制作台","制造机","组装机","合成机"], unlock: "完成任务[购买资源场]", inputs: [{item:"木材",qty:2}], output: 3, time: 6, clicks: 6 },
  { id: "木纤维", name: "木纤维", category: "wood", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-木材纤维化", inputs: [{item:"原木",qty:2}], output: 3, time: 6, clicks: 6 },
  { id: "加强木板", name: "加强木板", category: "wood", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-基础木制造", inputs: [{item:"木板",qty:2},{item:"石材",qty:3}], output: 1, time: 6, clicks: 6 },
  { id: "木质框架", name: "木质框架", category: "wood", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-基础木制造", inputs: [{item:"木棒",qty:4},{item:"螺丝",qty:6}], output: 1, time: 6, clicks: 6 },
  { id: "纸", name: "纸", category: "wood", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-纸生产", inputs: [{item:"木材",qty:1}], output: 2, time: 3, clicks: 3 },
  { id: "油纸", name: "油纸", category: "wood", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-纸生产", inputs: [{item:"纸",qty:3},{item:"油",qty:1}], output: 1, time: 9, clicks: 9 },

  // --- 石材建材 ---
  { id: "石材", name: "石材", category: "stone", equipment: ["制作台","制造机","组装机","合成机"], unlock: "完成任务[结识林山石]", inputs: [{item:"石头",qty:1}], output: 1, time: 3, clicks: 3 },
  { id: "石砖", name: "石砖", category: "stone", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-石料处理", inputs: [{item:"石材",qty:2}], output: 1, time: 6, clicks: 6 },
  { id: "钢筋混凝土", name: "钢筋混凝土", category: "stone", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-强度材料", inputs: [{item:"钢板",qty:2},{item:"石材",qty:5}], output: 1, time: 15, clicks: 15 },
  { id: "强力石砖", name: "强力石砖", category: "stone", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-强度材料", inputs: [{item:"钢筋混凝土",qty:1}], output: 2, time: 15, clicks: 15 },
  { id: "高性能地板", name: "高性能地板", category: "stone", equipment: ["制作台","合成机"], unlock: "科技研习-高性能地面", inputs: [{item:"橡胶",qty:3},{item:"塑料",qty:3},{item:"强力石砖",qty:4}], output: 1, time: 10, clicks: 10 },

  // --- 金属冶炼 ---
  { id: "铁锭", name: "铁锭", category: "metal", equipment: ["冶炼器","熔炉"], unlock: "完成任务[结识林山石]", inputs: [{item:"铁矿石",qty:2}], output: 1, time: 3, clicks: 3 },
  { id: "铜锭", name: "铜锭", category: "metal", equipment: ["冶炼器","熔炉"], unlock: "完成任务[购买资源场]", inputs: [{item:"铜矿石",qty:2}], output: 1, time: 3, clicks: 3 },
  { id: "钢锭", name: "钢锭", category: "metal", equipment: ["熔铸机"], unlock: "修复T3第二节点", inputs: [{item:"铁矿石",qty:2},{item:"煤矿石",qty:2}], output: 1, time: 4, clicks: 4 },
  { id: "超级合金", name: "超级合金", category: "metal", equipment: ["熔铸机"], unlock: "科技研习-超级合金", inputs: [{item:"钢锭",qty:3},{item:"提纯硅",qty:3}], output: 1, time: 5, clicks: 5 },

  // --- 金属加工 ---
  { id: "铁板", name: "铁板", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-入门铁制造", inputs: [{item:"铁锭",qty:1}], output: 1, time: 3, clicks: 3 },
  { id: "铁棒", name: "铁棒", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-入门铁制造", inputs: [{item:"铁锭",qty:2}], output: 3, time: 6, clicks: 6 },
  { id: "螺丝", name: "螺丝", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-基础铁锻造", inputs: [{item:"铁棒",qty:1}], output: 3, time: 2, clicks: 2 },
  { id: "加固铁板", name: "加固铁板", category: "metalwork", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-基础铁锻造", inputs: [{item:"铁板",qty:2},{item:"螺丝",qty:4}], output: 1, time: 6, clicks: 6 },
  { id: "铁质框架", name: "铁质框架", category: "metalwork", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-基础铁锻造", inputs: [{item:"铁棒",qty:4},{item:"螺丝",qty:6}], output: 1, time: 6, clicks: 6 },
  { id: "铜板", name: "铜板", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-入门铜制造", inputs: [{item:"铜锭",qty:1}], output: 1, time: 3, clicks: 3 },
  { id: "铜线", name: "铜线", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-入门铜制造", inputs: [{item:"铜锭",qty:2}], output: 3, time: 6, clicks: 6 },
  { id: "钢管", name: "钢管", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-基础钢锻造", inputs: [{item:"钢锭",qty:2}], output: 1, time: 6, clicks: 6 },
  { id: "钢板", name: "钢板", category: "metalwork", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-基础钢锻造", inputs: [{item:"钢锭",qty:3}], output: 2, time: 12, clicks: 12 },
  { id: "散热器", name: "散热器", category: "metalwork", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-散热器", inputs: [{item:"钢板",qty:4},{item:"铜板",qty:4}], output: 1, time: 10, clicks: 10 },

  // --- 纺织材料 ---
  { id: "线", name: "线", category: "textile", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-木材纤维化", inputs: [{item:"木纤维",qty:2}], output: 1, time: 6, clicks: 6 },
  { id: "布", name: "布", category: "textile", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-布料生产", inputs: [{item:"线",qty:2}], output: 1, time: 6, clicks: 6 },
  { id: "精致皮革", name: "精致皮革", category: "textile", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-精致丝布工艺", inputs: [{item:"兽皮",qty:1},{item:"布",qty:2}], output: 1, time: 10, clicks: 10 },
  { id: "精致丝线", name: "精致丝线", category: "textile", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-精致丝布工艺", inputs: [{item:"蛛丝",qty:1},{item:"线",qty:4}], output: 2, time: 10, clicks: 10 },

  // --- 化工材料 ---
  { id: "提纯硅", name: "提纯硅", category: "chemical", equipment: ["制作台","制造机","组装机","合成机"], unlock: "科技研习-砂石处理", inputs: [{item:"沙子",qty:3}], output: 1, time: 6, clicks: 6 },
  { id: "玻璃", name: "玻璃", category: "chemical", equipment: ["熔铸机"], unlock: "科技研习-砂石处理", inputs: [{item:"沙子",qty:3},{item:"石头",qty:3}], output: 1, time: 6, clicks: 6 },
  { id: "塑料", name: "塑料", category: "chemical", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-石油制品", inputs: [{item:"桶装石油",qty:3},{item:"煤矿石",qty:2}], output: 1, time: 5, clicks: 5 },
  { id: "橡胶", name: "橡胶", category: "chemical", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-石油制品", inputs: [{item:"桶装石油",qty:3},{item:"粮食",qty:2}], output: 1, time: 5, clicks: 5 },

  // --- 食品医药 ---
  { id: "酒", name: "酒", category: "food", equipment: ["粮食处理器"], unlock: "科技研习-粮食处理", inputs: [{item:"粮食",qty:4}], output: 1, time: 15, clicks: 15 },
  { id: "油", name: "油", category: "food", equipment: ["粮食处理器"], unlock: "科技研习-粮食处理", inputs: [{item:"粮食",qty:4}], output: 1, time: 15, clicks: 15 },
  { id: "酒精", name: "酒精", category: "food", equipment: ["冶炼器"], unlock: "科技研习-近代医疗商品", inputs: [{item:"酒",qty:3}], output: 1, time: 12, clicks: 12 },
  { id: "香皂", name: "香皂", category: "food", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-近代日用品", inputs: [{item:"油",qty:2},{item:"酒精",qty:2}], output: 1, time: 6, clicks: 6 },
  { id: "抗生素", name: "抗生素", category: "food", equipment: ["生产间"], unlock: "修复T2第一节点", inputs: [{item:"酒",qty:5},{item:"油",qty:5}], output: 1, time: 10, clicks: 0 },
  { id: "医药箱", name: "医药箱", category: "food", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-近代医疗商品", inputs: [{item:"布",qty:2},{item:"酒精",qty:2},{item:"铁质框架",qty:1}], output: 1, time: 12, clicks: 12 },

  // --- 能源系统 ---
  { id: "燃料碳棒", name: "燃料碳棒", category: "energy", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-耐久性燃料", inputs: [{item:"煤矿石",qty:1},{item:"木纤维",qty:1}], output: 1, time: 3, clicks: 3 },
  { id: "C级能量块", name: "C级能量块", category: "energy", equipment: ["核心充能器"], unlock: "修复T2第三节点", inputs: [{item:"铜板",qty:3},{item:"木质框架",qty:1}], output: 1, time: 20, clicks: 20 },
  { id: "B级能量块", name: "B级能量块", category: "energy", equipment: ["核心充能器"], unlock: "修复T4第三节点", inputs: [{item:"钢管",qty:4},{item:"提纯硅",qty:10}], output: 1, time: 30, clicks: 30 },
  { id: "A级能量块", name: "A级能量块", category: "energy", equipment: ["核心充能器"], unlock: "修复T7第四节点", inputs: [{item:"有机能量块",qty:2},{item:"橡胶",qty:4}], output: 1, time: 30, clicks: 30 },
  { id: "燃油能量块", name: "燃油能量块", category: "energy", equipment: ["制作台","组装机","合成机"], unlock: "修复T6第二节点", inputs: [{item:"燃料碳棒",qty:2},{item:"桶装石油",qty:2}], output: 1, time: 10, clicks: 10 },
  { id: "航天燃料", name: "航天燃料", category: "energy", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-航天燃料", inputs: [{item:"有机能量块",qty:10},{item:"燃油能量块",qty:5}], output: 1, time: 30, clicks: 30 },

  // --- 晶能系统 ---
  { id: "红色晶能", name: "红色晶能", category: "crystal", equipment: ["晶体置换机"], unlock: "修复T2第二节点", inputs: [{item:"铁锭",qty:3},{item:"铜锭",qty:3}], output: 1, time: 6, clicks: 20 },
  { id: "绿色晶能", name: "绿色晶能", category: "crystal", equipment: ["晶体置换机"], unlock: "修复T2第二节点", inputs: [{item:"布",qty:3},{item:"初级工具",qty:2}], output: 1, time: 10, clicks: 20 },
  { id: "蓝色晶能", name: "蓝色晶能", category: "crystal", equipment: ["晶体置换机"], unlock: "修复T3第二节点", inputs: [{item:"铁质核心",qty:1},{item:"钢管",qty:3}], output: 1, time: 12, clicks: 20 },
  { id: "紫色晶能", name: "紫色晶能", category: "crystal", equipment: ["晶体置换机"], unlock: "修复T5第四节点", inputs: [{item:"控制器",qty:1},{item:"电动机",qty:1}], output: 1, time: 15, clicks: 20 },
  { id: "黄色晶能", name: "黄色晶能", category: "crystal", equipment: ["晶体置换机"], unlock: "修复T7第3节点", inputs: [{item:"电动机",qty:2},{item:"石材",qty:4}], output: 1, time: 20, clicks: 20 },

  // --- 工具核心 ---
  { id: "初级工具", name: "初级工具", category: "tool", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-初级工具化", inputs: [{item:"木棒",qty:2},{item:"石材",qty:1}], output: 1, time: 10, clicks: 10 },
  { id: "铁质工具", name: "铁质工具", category: "tool", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-中级工具化", inputs: [{item:"铁棒",qty:2},{item:"加固铁板",qty:1}], output: 1, time: 10, clicks: 10 },
  { id: "高级工具", name: "高级工具", category: "tool", equipment: ["制作台","合成机"], unlock: "科技研习-高级工具", inputs: [{item:"工业结构体",qty:1},{item:"控制器",qty:1},{item:"电动机",qty:1}], output: 2, time: 20, clicks: 20 },
  { id: "铁质核心", name: "铁质核心", category: "tool", equipment: ["制作台","组装机","合成机"], unlock: "修复T2第3节点", inputs: [{item:"加固铁板",qty:1},{item:"C级能量块",qty:1}], output: 1, time: 10, clicks: 10 },
  { id: "钢质核心", name: "钢质核心", category: "tool", equipment: ["制作台","组装机","合成机"], unlock: "修复T4第三节点", inputs: [{item:"铁质工具",qty:1},{item:"B级能量块",qty:1}], output: 1, time: 12, clicks: 12 },
  { id: "机械核心", name: "机械核心", category: "tool", equipment: ["制作台","组装机","合成机"], unlock: "修复T7第四节点", inputs: [{item:"A级能量块",qty:1},{item:"超级合金",qty:2}], output: 1, time: 12, clicks: 12 },

  // --- 电子机械 ---
  { id: "电枢", name: "电枢", category: "electronic", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-入门电动设备", inputs: [{item:"铁棒",qty:4},{item:"铜线",qty:20}], output: 1, time: 15, clicks: 15 },
  { id: "集电环", name: "集电环", category: "electronic", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-基础电动设备", inputs: [{item:"铜板",qty:4},{item:"螺丝",qty:25}], output: 1, time: 15, clicks: 15 },
  { id: "电动机", name: "电动机", category: "electronic", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-电器工业化", inputs: [{item:"电枢",qty:5},{item:"集电环",qty:5}], output: 2, time: 30, clicks: 30 },
  { id: "芯片", name: "芯片", category: "electronic", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-电子工业", inputs: [{item:"提纯硅",qty:10},{item:"铜板",qty:15}], output: 1, time: 30, clicks: 30 },
  { id: "控制器", name: "控制器", category: "electronic", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-电器工业化", inputs: [{item:"芯片",qty:1},{item:"钢质核心",qty:1}], output: 1, time: 30, clicks: 30 },
  { id: "电路板", name: "电路板", category: "electronic", equipment: ["制作台","合成机"], unlock: "科技研习-集成电子化", inputs: [{item:"橡胶",qty:5},{item:"铜板",qty:20},{item:"工业结构体",qty:1}], output: 1, time: 30, clicks: 30 },
  { id: "大型计算机", name: "大型计算机", category: "electronic", equipment: ["制作台","合成机"], unlock: "修复T6第三节点", inputs: [{item:"电路板",qty:1},{item:"芯片",qty:5},{item:"控制器",qty:5}], output: 1, time: 30, clicks: 30 },
  { id: "超级计算机", name: "超级计算机", category: "electronic", equipment: ["制作台","合成机"], unlock: "科技研习-超级计算机", inputs: [{item:"大型计算机",qty:2},{item:"机械核心",qty:5},{item:"高级工具",qty:3}], output: 1, time: 60, clicks: 60 },
  { id: "工业结构体", name: "工业结构体", category: "electronic", equipment: ["制作台","合成机"], unlock: "科技研习-工业级制品", inputs: [{item:"铁质框架",qty:3},{item:"钢管",qty:5},{item:"强力石砖",qty:5}], output: 2, time: 30, clicks: 30 },

  // --- 日用商品 ---
  { id: "铜镜", name: "铜镜", category: "goods", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-古制商品制造", inputs: [{item:"木质框架",qty:1},{item:"铜板",qty:3}], output: 1, time: 6, clicks: 6 },
  { id: "油纸伞", name: "油纸伞", category: "goods", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-古制商品制造", inputs: [{item:"木棒",qty:2},{item:"油纸",qty:3}], output: 1, time: 6, clicks: 6 },
  { id: "手表", name: "手表", category: "goods", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-现代商品", inputs: [{item:"玻璃",qty:5},{item:"芯片",qty:2},{item:"电路板",qty:1}], output: 1, time: 15, clicks: 15 },
  { id: "烤箱", name: "烤箱", category: "goods", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-现代商品", inputs: [{item:"工业结构体",qty:1},{item:"高级工具",qty:1},{item:"大型计算机",qty:1}], output: 1, time: 20, clicks: 20 },
  { id: "帐篷", name: "帐篷", category: "goods", equipment: ["生产间"], unlock: "科技研习-帐篷", inputs: [{item:"布",qty:10},{item:"木棒",qty:8},{item:"加固铁板",qty:1}], output: 1, time: 20, clicks: 0 },
  { id: "建造胶囊", name: "建造胶囊", category: "goods", equipment: ["制作台","组装机","合成机"], unlock: "修复T3第五节点", inputs: [{item:"木质框架",qty:1},{item:"钢筋混凝土",qty:1}], output: 3, time: 15, clicks: 15 },

  // --- 航天科技 ---
  { id: "天机石", name: "天机石", category: "aerospace", equipment: ["制作台","合成机","生产间"], unlock: "修复T4第二节点", inputs: [{item:"提纯硅",qty:5},{item:"铁质工具",qty:2},{item:"铁质核心",qty:10}], output: 1, time: 12, clicks: 12 },
  { id: "防御磁盾", name: "防御磁盾", category: "aerospace", equipment: ["生产间"], unlock: "科技研习-防御磁盾", inputs: [{item:"工业结构体",qty:1},{item:"提纯硅",qty:6}], output: 1, time: 6, clicks: 0 },
  { id: "航天结构体", name: "航天结构体", category: "aerospace", equipment: ["制作台","组装机","合成机"], unlock: "科技研习-航天结构体", inputs: [{item:"超级合金",qty:8},{item:"橡胶",qty:4}], output: 2, time: 30, clicks: 30 },
  { id: "航天引擎", name: "航天引擎", category: "aerospace", equipment: ["制作台","合成机"], unlock: "科技研习-航天引擎", inputs: [{item:"机械核心",qty:2},{item:"大型计算机",qty:1},{item:"散热器",qty:4}], output: 1, time: 40, clicks: 40 },
];

// ========== 分类定义 ==========
const CATEGORIES = [
  { id: "raw", name: "基础原料", icon: "⛏", color: "#8b7355", desc: "采集获取的原始资源" },
  { id: "wood", name: "木材系列", icon: "🪵", color: "#8b6c42", desc: "木材加工及木制品" },
  { id: "stone", name: "石材建材", icon: "🧱", color: "#7d7d7d", desc: "石材与建筑材料" },
  { id: "metal", name: "金属冶炼", icon: "🔥", color: "#b87333", desc: "矿石冶炼成锭" },
  { id: "metalwork", name: "金属加工", icon: "⚙", color: "#9e9e9e", desc: "金属板/棒/线/管等" },
  { id: "textile", name: "纺织材料", icon: "🧵", color: "#c4956a", desc: "纤维、线、布、皮革" },
  { id: "chemical", name: "化工材料", icon: "⚗", color: "#4fc3f7", desc: "硅、玻璃、塑料、橡胶" },
  { id: "food", name: "食品医药", icon: "🍷", color: "#81c784", desc: "酒、油、医药用品" },
  { id: "energy", name: "能源系统", icon: "🔋", color: "#ffb74d", desc: "能量块与燃料" },
  { id: "crystal", name: "晶能系统", icon: "💎", color: "#ba68c8", desc: "五色晶能" },
  { id: "tool", name: "工具核心", icon: "🔨", color: "#ff8a65", desc: "工具与核心组件" },
  { id: "electronic", name: "电子机械", icon: "🔌", color: "#64b5f6", desc: "芯片、电路、计算机" },
  { id: "goods", name: "日用商品", icon: "📦", color: "#a5d6a7", desc: "终端商品" },
  { id: "aerospace", name: "航天科技", icon: "🚀", color: "#ce93d8", desc: "航天与高级产物" },
];

// ========== 构建索引 ==========
const ALL_ITEMS = {};
RAW_RESOURCES.forEach(r => { ALL_ITEMS[r.id] = r; });
RECIPES.forEach(r => { ALL_ITEMS[r.id] = r; });

// 构建"被依赖"关系（谁用到了这个材料）
const USED_BY = {};
Object.keys(ALL_ITEMS).forEach(id => { USED_BY[id] = []; });
RECIPES.forEach(recipe => {
  recipe.inputs.forEach(inp => {
    if (!USED_BY[inp.item]) USED_BY[inp.item] = [];
    USED_BY[inp.item].push(recipe.id);
  });
});
