/**
 * 计算 50蓝色晶能 + 180绿色晶能 + 600红色晶能 的产线
 * 使用向上取整（Math.ceil），不配平
 */
const fs = require('fs');
const vm = require('vm');

const dataCode = fs.readFileSync('./js/data.js', 'utf8');
const ctx = {};
vm.createContext(ctx);
vm.runInContext(dataCode + `
this.ALL_ITEMS = ALL_ITEMS;
this.MACHINE_POWER = MACHINE_POWER;
`, ctx);

const { ALL_ITEMS, MACHINE_POWER } = ctx;
const TIME_PERIOD = 1800;
const BELT_RATE = 2;

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

function calculateNode(productId, quantity, aggregate, visited = new Set()) {
  const recipe = ALL_ITEMS[productId];
  if (!recipe || recipe.isRaw) {
    if (!aggregate.has(productId)) {
      aggregate.set(productId, { id: productId, name: recipe ? recipe.name : productId, isRaw: true, totalQty: 0 });
    }
    aggregate.get(productId).totalQty += quantity;
    return { id: productId, name: recipe ? recipe.name : productId, qty: quantity, isRaw: true, children: [] };
  }
  if (!aggregate.has(productId)) {
    const machine = getDefaultMachine(recipe);
    aggregate.set(productId, { id: productId, name: recipe.name, isRaw: false, recipe, machine, totalQty: 0 });
  }
  const existing = aggregate.get(productId);
  existing.totalQty += quantity;

  const craftsNeeded = existing.totalQty / recipe.output;
  const craftsPerMachine = TIME_PERIOD / recipe.time;
  existing.machineCountRaw = craftsNeeded / craftsPerMachine;

  const node = { id: productId, name: recipe.name, qty: quantity, isRaw: false, machine: existing.machine, machineCountRaw: existing.machineCountRaw, children: [] };
  if (visited.has(productId)) return node;
  const newVisited = new Set(visited);
  newVisited.add(productId);
  recipe.inputs.forEach(inp => {
    const childQty = craftsNeeded * inp.qty;
    const childNode = calculateNode(inp.item, childQty, aggregate, newVisited);
    node.children.push(childNode);
  });
  return node;
}

const plan = [
  { id: "蓝色晶能", qty: 50 },
  { id: "绿色晶能", qty: 180 },
  { id: "红色晶能", qty: 600 },
];

const aggregate = new Map();
const trees = [];
plan.forEach(p => {
  const tree = calculateNode(p.id, p.qty, aggregate);
  trees.push({ target: p, tree });
});

const machines = [];
const materials = [];
let totalPower = 0, totalMachines = 0, totalBelts = 0;

aggregate.forEach(item => {
  if (item.isRaw) {
    item.flowRate = item.totalQty / TIME_PERIOD;
    item.belts = Math.ceil(item.flowRate / BELT_RATE);
    totalBelts += item.belts;
    materials.push(item);
  } else {
    item.machineCount = Math.ceil(item.machineCountRaw);
    item.power = item.machineCount * (MACHINE_POWER[item.machine] || 0);
    const craftsPerMachine = TIME_PERIOD / item.recipe.time;
    item.actualOutput = item.machineCount * craftsPerMachine * item.recipe.output;
    item.overproduce = item.actualOutput - item.totalQty;
    item.efficiency = item.totalQty / item.actualOutput;
    item.flowRate = item.actualOutput / TIME_PERIOD;
    item.belts = Math.ceil(item.flowRate / BELT_RATE);
    totalBelts += item.belts;
    machines.push(item);
    totalPower += item.power;
    totalMachines += item.machineCount;
  }
});

machines.sort((a, b) => b.machineCount - a.machineCount);
materials.sort((a, b) => b.totalQty - a.totalQty);

const output = {
  timePeriod: TIME_PERIOD, beltRate: BELT_RATE, plan,
  machines: machines.map(m => ({
    id: m.id, name: m.name, machine: m.machine,
    machineCountRaw: parseFloat(m.machineCountRaw.toFixed(4)), machineCount: m.machineCount,
    power: m.power, demand: parseFloat(m.totalQty.toFixed(2)),
    actualOutput: parseFloat(m.actualOutput.toFixed(2)), overproduce: parseFloat(m.overproduce.toFixed(2)),
    efficiency: parseFloat((m.efficiency * 100).toFixed(1)), belts: m.belts,
    flowRate: parseFloat(m.flowRate.toFixed(2)),
    recipe: { output: m.recipe.output, time: m.recipe.time, inputs: m.recipe.inputs, equipment: m.recipe.equipment }
  })),
  materials: materials.map(m => ({ id: m.id, name: m.name, totalQty: parseFloat(m.totalQty.toFixed(2)), flowRate: parseFloat(m.flowRate.toFixed(2)), belts: m.belts })),
  totalPower, totalMachines, totalBelts, trees
};
console.log(JSON.stringify(output, null, 2));
