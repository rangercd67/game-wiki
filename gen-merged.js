/**
 * 合并三条晶能产线 -> 单一共享 DAG
 * 共享中间产物只画一次；内部边标注吞吐/带数/填充率
 * 原始矿作为「直接进入」侧输入挂在冶炼/木材节点旁，不计入厂内带
 */
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('./ceil-result.json', 'utf8'));
const TIME = data.timePeriod, BELT = data.beltRate;
const machineMap = {};
data.machines.forEach(m => machineMap[m.id] = m);

// ---- 合并三棵树 ----
const edgeQty = {};      // "parent>child" -> 聚合需求量
const nodeInfo = {};      // id -> {name,isRaw,machine}
const roots = [];
const childrenAdj = {};   // id -> [childId]
const parentsAdj = {};    // id -> [parentId]
function visit(node, parentId) {
  if (!nodeInfo[node.id]) nodeInfo[node.id] = { id: node.id, name: node.name, isRaw: node.isRaw, machine: node.machine };
  if (parentId) {
    const k = parentId + '>' + node.id;
    edgeQty[k] = (edgeQty[k] || 0) + node.qty;
    (childrenAdj[parentId] = childrenAdj[parentId] || []).push(node.id);
    (parentsAdj[node.id] = parentsAdj[node.id] || []).push(parentId);
  } else roots.push(node.id);
  (node.children || []).forEach(c => visit(c, node.id));
}
data.trees.forEach(t => visit(t.tree, null));

const allIds = Object.keys(nodeInfo);
// 拓扑排序 (Kahn)
const indeg = {}; allIds.forEach(id => indeg[id] = (parentsAdj[id] || []).length);
const queue = roots.slice(); const topo = [];
const adj = JSON.parse(JSON.stringify(childrenAdj));
while (queue.length) {
  const n = queue.shift(); topo.push(n);
  (adj[n] || []).forEach(c => { indeg[c]--; if (indeg[c] === 0) queue.push(c); });
}
// 最长路径分层 (tier)
const tier = {};
topo.forEach(id => {
  if (roots.includes(id)) { tier[id] = 0; return; }
  let mx = 0;
  (parentsAdj[id] || []).forEach(p => mx = Math.max(mx, tier[p] + 1));
  tier[id] = mx;
});

// ---- 布局：逐层分配 x ----
const NODE_W = 150, GAP = 48, TIER_H = 134, TOP = 70, SIDE = 40;
const tiers = {};
allIds.forEach(id => { if (!nodeInfo[id].isRaw) (tiers[tier[id]] = tiers[tier[id]] || []).push(id); });
const maxTier = Math.max(...Object.keys(tiers).map(Number));
const pos = {}; // id -> {x,y}
// tier0 顺序：红绿蓝
const rootOrder = ['红色晶能', '绿色晶能', '蓝色晶能'];
tiers[0].sort((a, b) => rootOrder.indexOf(a) - rootOrder.indexOf(b));
let cursor = SIDE, maxRight = 0;
tiers[0].forEach(id => { pos[id] = { x: cursor, y: TOP }; cursor += NODE_W + GAP; });
maxRight = Math.max(maxRight, cursor);
for (let tk = 1; tk <= maxTier; tk++) {
  const nodes = tiers[tk];
  // 按父节点平均 x 排序，保持簇聚
  nodes.sort((a, b) => {
    const ax = avgParentX(a), bx = avgParentX(b);
    return ax - bx;
  });
  cursor = SIDE;
  nodes.forEach(id => { pos[id] = { x: cursor, y: TOP + tk * TIER_H }; cursor += NODE_W + GAP; });
  maxRight = Math.max(maxRight, cursor);
}
function avgParentX(id) {
  const ps = parentsAdj[id] || [];
  if (!ps.length) return 0;
  return ps.reduce((s, p) => s + (pos[p] ? pos[p].x + NODE_W / 2 : 0), 0) / ps.length;
}

const W = maxRight + SIDE - GAP;
const H = TOP + maxTier * TIER_H + NODE_H() + 60;
function NODE_H() { return 60; }

// ---- 画 SVG ----
let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${Math.min(W, 1180)}px;display:block;margin:0 auto;" font-family="-apple-system,'Segoe UI',sans-serif">`;
svg += `<rect width="${W}" height="${H}" fill="#161922"/>`;

// 内部边
const rawUsers = {}; // smelter -> [rawIds]
Object.keys(edgeQty).forEach(k => {
  const [p, c] = k.split('>');
  if (nodeInfo[c].isRaw) { (rawUsers[p] = rawUsers[p] || []).push(c); return; }
  const x1 = pos[p].x + NODE_W / 2, y1 = pos[p].y + NODE_H();
  const x2 = pos[c].x + NODE_W / 2, y2 = pos[c].y;
  const flow = edgeQty[k] / TIME;
  const belts = Math.max(1, Math.ceil(flow / BELT));
  const fill = flow / (belts * BELT);
  const col = belts <= 1 ? '#3a4252' : '#e0913a';
  const d = (tier[c] - tier[p] === 1)
    ? `M${x1},${y1} L${x2},${y2}`
    : `M${x1},${y1} C${x1},${y1 + 60} ${x2},${y2 - 60} ${x2},${y2}`; // 跨层曲线
  svg += `<path d="${d}" stroke="${col}" stroke-width="2" fill="none" opacity="0.9"/>`;
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  const lbl = `${flow.toFixed(2)}/s · ${belts}带`;
  const tw = lbl.length * 7 + 12;
  svg += `<rect x="${mx - tw / 2}" y="${my - 11}" width="${tw}" height="20" rx="5" fill="#0e1117" stroke="${col}" stroke-width="1"/>`;
  svg += `<text x="${mx}" y="${my + 4}" fill="${fill > 0.95 ? '#9fb0c8' : '#f0b46a'}" font-size="12" text-anchor="middle">${lbl}</text>`;
});

// 原始矿侧输入
Object.keys(rawUsers).forEach(sm => {
  const sx = pos[sm].x, sy = pos[sm].y;
  rawUsers[sm].forEach((r, i) => {
    const rx = sx - NODE_W - 30, ry = sy + i * 34 - 6;
    svg += `<rect x="${rx}" y="${ry}" width="118" height="28" rx="6" fill="#241f17" stroke="#caa14a" stroke-width="2"/>`;
    svg += `<text x="${rx + 59}" y="${ry + 18}" fill="#e8d49a" font-size="12" text-anchor="middle">${nodeInfo[r].name} 直入</text>`;
    svg += `<path d="M${rx + 118},${ry + 14} L${sx},${sy + 14 + i * 0}" stroke="#caa14a" stroke-width="1.5" stroke-dasharray="4 3" fill="none"/>`;
  });
});

// 节点
allIds.filter(id => !nodeInfo[id].isRaw).forEach(id => {
  const x = pos[id].x, y = pos[id].y, cx = x + NODE_W / 2, cy = y + NODE_H() / 2;
  const isRoot = roots.includes(id);
  const mc = machineMap[id];
  const fill = isRoot ? '#1d2330' : '#1b212c';
  const stroke = isRoot ? ({ '红色晶能': '#ff5c5c', '绿色晶能': '#3ddc84', '蓝色晶能': '#4aa8ff' }[id]) : '#5b6b86';
  const sub = mc ? `${mc.machine} ×${mc.machineCount}` : '';
  svg += `<rect x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H()}" rx="9" fill="${fill}" stroke="${stroke}" stroke-width="2.5"/>`;
  svg += `<text x="${cx}" y="${cy - 6}" fill="#eef2f8" font-size="15" font-weight="700" text-anchor="middle">${nodeInfo[id].name}</text>`;
  svg += `<text x="${cx}" y="${cy + 14}" fill="#9fb0c8" font-size="12" text-anchor="middle">${sub}</text>`;
});
svg += `</svg>`;

// 统计内部带
let beltLines = [], totalBelt = 0, underfull = 0;
Object.keys(edgeQty).forEach(k => {
  const [, c] = k.split('>');
  if (nodeInfo[c].isRaw) return;
  const flow = edgeQty[k] / TIME;
  const belts = Math.max(1, Math.ceil(flow / BELT));
  const fill = flow / (belts * BELT);
  beltLines.push({ k, flow: +flow.toFixed(2), belts, fill: +(fill * 100).toFixed(0) });
  totalBelt += belts;
  if (fill < 95) underfull++;
});

const html = `<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>江城创业记 · 合并产线图</title>
<style>
body{margin:0;background:#0d0f14;color:#dfe6f0;font-family:-apple-system,'Segoe UI',sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:26px 16px 70px}
h1{font-size:21px;margin:0 0 6px}
.sub{color:#8a97ad;font-size:13px;margin:0 0 18px;line-height:1.6}
.panel{background:#11141b;border:1px solid #222a38;border-radius:14px;padding:16px 12px 8px;margin-bottom:24px;overflow-x:auto}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:#aab6c8;margin:8px 0 22px;padding:12px 16px;background:#11141b;border:1px solid #222a38;border-radius:12px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.box{width:14px;height:14px;border-radius:4px;border:2px solid #5b6b86;background:#1b212c}
.box.cry{border-color:#4aa8ff;background:#1d2330}.box.raw{border-color:#caa14a;background:#241f17}
.sw{width:22px;height:0;border-top:3px solid #3a4252}.sw.hot{border-color:#e0913a}
.tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
.tbl th,.tbl td{padding:7px 10px;border-bottom:1px solid #222a38;text-align:left}
.tbl th{color:#8a97ad;font-weight:600}
.tbl td.num{text-align:right;font-variant-numeric:tabular-nums}
.note{font-size:12.5px;color:#9fb0c8;line-height:1.7;background:#15201a;border:1px solid #2c4a36;border-radius:10px;padding:12px 16px;margin:14px 0}
.note b{color:#7df0ad}
</style></head><body><div class="wrap">
<h1>江城创业记 · 合并产线图（共享中间产物）</h1>
<p class="sub">需求 50蓝 / 180绿 / 600红 · 周期 1800s · 带速 2/s · 机器按向上取整（已全局共享，共 38 台）<br>
<b>原始矿「直接进入」</b>：矿石/原木/石头不作为厂内带，直接喂入对应冶炼/加工节点（图中金色虚线侧框）。厂内带只算中间产物运输。</p>

<div class="legend">
<span><i class="box cry"></i>晶能(目标)</span>
<span><i class="box"></i>中间产物(设备×台数)</span>
<span><i class="box raw"></i>原始矿(直入)</span>
<span><i class="sw"></i>≤2/s 单带</span>
<span><i class="sw hot"></i>&gt;2/s 需双带</span>
<span>边标签：吞吐/s · 带数（填充率&lt;95% 标橙）</span>
</div>

<div class="panel">${svg}</div>

<div class="note">
<b>合并后的带况：</b>厂内带共 <b>${totalBelt}</b> 条，其中 <b>${underfull}</b> 条未跑满（&lt;95%）。最粗的四条带是
<b>铁锭 1.33/s、铜锭 1.33/s、木纤维 1.5/s、螺丝 1.5/s</b>——都只用了单条 2/s 带的 67%~75%。<br>
<b>怎么跑满 2/s：</b>当前机器数是「向上取整」定的，产出是分数的整数倍，所以带子填不满。要填满，就把这几台机器加到让产出率 = 2/s 的整数倍：
铁锭/铜锭 1.33→<b>6 台=2.0/s（满）</b>、木纤维 1.5→<b>4 台=2.0/s（满）</b>、螺丝 1.5→ 需 4 台=6.0/s（3 条满带）。
代价是这些中间产物会超额生产（铁锭从 2400→3600/周期），连带下游晶体也超额——属于「用超额换满带」，是否划算看你舍不舍得堆机器。
</div>

<h2 style="font-size:16px;margin:18px 0 8px">厂内带明细（中间产物运输）</h2>
<table class="tbl"><thead><tr><th>物料链（父→子）</th><th class="num">吞吐 /s</th><th class="num">带数</th><th class="num">填充率</th></tr></thead><tbody>
${beltLines.sort((a,b)=>b.flow-a.flow).map(b=>{
  const [p,c]=b.k.split('>');
  return `<tr><td>${nodeInfo[p].name} → ${nodeInfo[c].name}</td><td class="num">${b.flow}</td><td class="num">${b.belts}</td><td class="num" style="color:${b.fill<95?'#f0b46a':'#7df0ad'}">${b.fill}%</td></tr>`;
}).join('')}
</tbody></table>

<div class="note" style="margin-top:20px">
<b>关于「合并」的实话：</b>铁锭、铜锭这类节点既被红色浅链吃、又被蓝色深链吃。合并成单节点后，蓝色深链那一侧必然拉出横跨 3~4 层的长带——
而 2/s 带恰恰拉不动这种长途。所以「完全合并成一条线」和「2/s 带」本身有张力。务实做法是：
<b>铁锭/铜锭/木纤维/螺丝 这些真·共享枢纽建一处</b>（它们本来就在产线底部、靠近矿源），蓝色深链里的专用分支（铁质核心→加固铁板→…）就地本地化，
不要为了合并而拉长途带。这也正是上一张分链图的逻辑——它其实已经是最优解。
</div>

</div></body></html>`;

fs.writeFileSync('./merged-line.html', html);
console.log('written merged-line.html; internalBelts=', totalBelt, 'underfull=', underfull, 'WxH=', W, 'x', H);
