/**
 * 计算 50蓝色晶能 + 180绿色晶能 + 600红色晶能 的产线
 * 输出完整依赖树和汇总数据（JSON）
 */

const fs = require('fs');
const vm = require('vm');

// 读取 data.js
const dataCode = fs.readFileSync('./js/data.js', 'utf8');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(dataCode + `
this.RECIPES = RECIPES;
this.RAW_RESOURCES = RAW_RESOURCES;
this.ALL_ITEMS = ALL_ITEMS;
this.MACHINE_POWER = MACHINE_POWER;
this.CONVEYOR_BELTS = CONVEYOR_BELTS;
`, ctx);

const { RECIPES, RAW_RESOURCES, ALL_ITEMS, MACHINE_POWER } = ctx;

const TIME_PERIOD = 1800; // 默认 30 分钟
const BELT_RATE = 2;      // 2级传送带

function getDefaultMachine(recipe) {
  if (!recipe.equipment || recipe.equipment.length === 0) return "";
  let best = recipe.equipment[0];
  let bestPower = MACHINE_POWER[best] ?? 999;
  for (const m of recipe.equipment) {
    const p = MACHINE_POWER[m] ?? 999;
    if (p < bestPower) { best = m; bestPower = p; }
  }
  return best;
}

function gcd(a, b) {
  a = Math.abs(Math.round(a)); b = Math.abs(Math.round(b));
  while (b) { [a, b] = [b, a % b]; }
  return a || 1;
}
function lcm(a, b) { return Math.abs(a * b) / gcd(a, b); }
function findDenominator(x, maxDen = 10000) {
  if (Math.abs(x - Math.round(x)) < 1e-9) return 1;
  for (let d = 2; d <= maxDen; d++) {
    if (Math.abs(d * x - Math.round(d * x)) < 1e-6) return d;
  }
  return 0;
}

function calculateNode(productId, quantity, timePeriod, aggregate, visited = new Set()) {
  const recipe = ALL_ITEMS[productId];

  if (!recipe || recipe.isRaw) {
    if (!aggregate.has(productId)) {
      aggregate.set(productId, {
        id: productId,
        name: recipe ? recipe.name : productId,
        isRaw: true,
        totalQty: 0,
      });
    }
    aggregate.get(productId).totalQty += quantity;
    return { id: productId, name: recipe ? recipe.name : productId, qty: quantity, isRaw: true, children: [] };
  }

  if (!aggregate.has(productId)) {
    const machine = getDefaultMachine(recipe);
    const craftsNeeded = quantity / recipe.output;
    const craftsPerMachine = timePeriod / recipe.time;
    const machineCount = craftsNeeded / craftsPerMachine;
    const power = machineCount * (MACHINE_POWER[machine] || 0);
    aggregate.set(productId, {
      id: productId,
      name: recipe.name,
      isRaw: false,
      recipe: recipe,
      machine: machine,
      machineCount: machineCount,
      power: power,
      totalQty: quantity,
      children: [],
    });
  } else {
    const existing = aggregate.get(productId);
    existing.totalQty += quantity;
    const craftsNeeded = existing.totalQty / recipe.output;
    const craftsPerMachine = timePeriod / recipe.time;
    existing.machineCount = craftsNeeded / craftsPerMachine;
    existing.power = existing.machineCount * (MACHINE_POWER[existing.machine] || 0);
  }

  const node = {
    id: productId,
    name: recipe.name,
    qty: quantity,
    isRaw: false,
    machine: aggregate.get(productId).machine,
    machineCount: aggregate.get(productId).machineCount,
    children: [],
  };

  if (visited.has(productId)) return node;
  const newVisited = new Set(visited);
  newVisited.add(productId);

  const craftsNeeded = quantity / recipe.output;
  recipe.inputs.forEach(inp => {
    const childQty = craftsNeeded * inp.qty;
    const childNode = calculateNode(inp.item, childQty, timePeriod, aggregate, newVisited);
    node.children.push(childNode);
  });

  return node;
}

function runBalancedCalculation(plan) {
  // Pass 1: 原始需求
  const agg1 = new Map();
  plan.forEach(p => calculateNode(p.id, p.qty, TIME_PERIOD, agg1));

  let scaleM = 1;
  agg1.forEach(item => {
    if (!item.isRaw && item.machineCount > 0) {
      const den = findDenominator(item.machineCount);
      if (den > 0) scaleM = lcm(scaleM, den);
    }
  });
  if (scaleM > 10000) scaleM = 1;

  // Pass 2: 配平需求
  const aggregate = new Map();
  const trees = [];
  const scaledPlan = plan.map(p => ({ id: p.id, qty: p.qty * scaleM }));

  scaledPlan.forEach(p => {
    const tree = calculateNode(p.id, p.qty, TIME_PERIOD, aggregate);
    trees.push({ target: p, tree: tree });
  });

  const machines = [];
  const materials = [];
  let totalPower = 0;
  let totalMachines = 0;
  let totalBelts = 0;

  aggregate.forEach(item => {
    item.flowRate = item.totalQty / TIME_PERIOD;
    item.belts = Math.ceil(item.flowRate / BELT_RATE);
    item.beltRate = BELT_RATE;
    totalBelts += item.belts;

    if (item.isRaw) {
      materials.push(item);
    } else {
      item.machineCount = Math.round(item.machineCount);
      item.power = item.machineCount * (MACHINE_POWER[item.machine] || 0);
      machines.push(item);
      totalPower += item.power;
      totalMachines += item.machineCount;
    }
  });

  machines.sort((a, b) => b.machineCount - a.machineCount);
  materials.sort((a, b) => b.totalQty - a.totalQty);

  return { scaleM, machines, materials, totalPower, totalMachines, totalBelts, trees, plan };
}

const plan = [
  { id: "蓝色晶能", qty: 50 },
  { id: "绿色晶能", qty: 180 },
  { id: "红色晶能", qty: 600 },
];

const result = runBalancedCalculation(plan);

console.log(JSON.stringify(result, null, 2));
