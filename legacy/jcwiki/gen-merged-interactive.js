/**
 * 合并三条晶能产线 -> 单一共享 DAG（可交互版）
 * 支持：拖拽平移、滚轮缩放、按钮复位/适配、悬停提示、节点高亮上游
 */
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('./ceil-result.json', 'utf8'));
const TIME = data.timePeriod, BELT = data.beltRate;
const machineMap = {};
data.machines.forEach(m => machineMap[m.id] = m);

// ---- 合并三棵树 ----
const edgeQty = {};
const nodeInfo = {};
const roots = [];
const childrenAdj = {};
const parentsAdj = {};
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
// 拓扑排序
const indeg = {}; allIds.forEach(id => indeg[id] = (parentsAdj[id] || []).length);
const queue = roots.slice(); const topo = [];
const adj = JSON.parse(JSON.stringify(childrenAdj));
while (queue.length) {
  const n = queue.shift(); topo.push(n);
  (adj[n] || []).forEach(c => { indeg[c]--; if (indeg[c] === 0) queue.push(c); });
}
// 最长路径分层
const tier = {};
topo.forEach(id => {
  if (roots.includes(id)) { tier[id] = 0; return; }
  let mx = 0;
  (parentsAdj[id] || []).forEach(p => mx = Math.max(mx, tier[p] + 1));
  tier[id] = mx;
});

// ---- 布局 ----
const NODE_W = 150, GAP = 48, TIER_H = 134, TOP = 70, SIDE = 40;
const tiers = {};
allIds.forEach(id => { if (!nodeInfo[id].isRaw) (tiers[tier[id]] = tiers[tier[id]] || []).push(id); });
const maxTier = Math.max(...Object.keys(tiers).map(Number));
const pos = {};
const rootOrder = ['红色晶能', '绿色晶能', '蓝色晶能'];
tiers[0].sort((a, b) => rootOrder.indexOf(a) - rootOrder.indexOf(b));
let cursor = SIDE, maxRight = 0;
tiers[0].forEach(id => { pos[id] = { x: cursor, y: TOP }; cursor += NODE_W + GAP; });
maxRight = Math.max(maxRight, cursor);
for (let tk = 1; tk <= maxTier; tk++) {
  const nodes = tiers[tk];
  nodes.sort((a, b) => avgParentX(a) - avgParentX(b));
  cursor = SIDE;
  nodes.forEach(id => { pos[id] = { x: cursor, y: TOP + tk * TIER_H }; cursor += NODE_W + GAP; });
  maxRight = Math.max(maxRight, cursor);
}
function avgParentX(id) {
  const ps = parentsAdj[id] || [];
  if (!ps.length) return 0;
  return ps.reduce((s, p) => s + (pos[p] ? pos[p].x + NODE_W / 2 : 0), 0) / ps.length;
}

function NODE_H() { return 60; }
const W = maxRight + SIDE - GAP;
const H = TOP + maxTier * TIER_H + NODE_H() + 60;

// 构建边信息对象，供 JS 使用
const edgeInfo = [];
const rawUsers = {};
Object.keys(edgeQty).forEach(k => {
  const [p, c] = k.split('>');
  if (nodeInfo[c].isRaw) { (rawUsers[p] = rawUsers[p] || []).push(c); return; }
  const flow = edgeQty[k] / TIME;
  const belts = Math.max(1, Math.ceil(flow / BELT));
  const fill = flow / (belts * BELT);
  edgeInfo.push({ id: `e-${p}-${c}`, parent: p, child: c, flow, belts, fill, qty: edgeQty[k] });
});

// ---- 生成 SVG（所有内容包在 viewport group 里） ----
let svgContent = '';

// 内部边
edgeInfo.forEach(e => {
  const p = e.parent, c = e.child;
  const x1 = pos[p].x + NODE_W / 2, y1 = pos[p].y + NODE_H();
  const x2 = pos[c].x + NODE_W / 2, y2 = pos[c].y;
  const col = e.belts <= 1 ? '#3a4252' : '#e0913a';
  const d = (tier[c] - tier[p] === 1)
    ? `M${x1},${y1} L${x2},${y2}`
    : `M${x1},${y1} C${x1},${y1 + 60} ${x2},${y2 - 60} ${x2},${y2}`;
  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
  const lbl = `${e.flow.toFixed(2)}/s · ${e.belts}带`;
  const tw = lbl.length * 7 + 12;
  const fillCol = e.fill > 0.95 ? '#9fb0c8' : '#f0b46a';
  svgContent += `<g class="edge" data-parent="${p}" data-child="${c}">`;
  svgContent += `<path id="${e.id}" d="${d}" stroke="${col}" stroke-width="2" fill="none" opacity="0.9"/>`;
  svgContent += `<rect x="${mx - tw / 2}" y="${my - 11}" width="${tw}" height="20" rx="5" fill="#0e1117" stroke="${col}" stroke-width="1"/>`;
  svgContent += `<text x="${mx}" y="${my + 4}" fill="${fillCol}" font-size="12" text-anchor="middle">${lbl}</text>`;
  svgContent += `</g>`;
});

// 原始矿侧输入
Object.keys(rawUsers).forEach(sm => {
  const sx = pos[sm].x, sy = pos[sm].y;
  rawUsers[sm].forEach((r, i) => {
    const rx = sx - NODE_W - 30, ry = sy + i * 34 - 6;
    svgContent += `<g class="raw-node" data-id="${r}">`;
    svgContent += `<rect x="${rx}" y="${ry}" width="118" height="28" rx="6" fill="#241f17" stroke="#caa14a" stroke-width="2"/>`;
    svgContent += `<text x="${rx + 59}" y="${ry + 18}" fill="#e8d49a" font-size="12" text-anchor="middle">${nodeInfo[r].name} 直入</text>`;
    svgContent += `<path d="M${rx + 118},${ry + 14} L${sx},${sy + 14}" stroke="#caa14a" stroke-width="1.5" stroke-dasharray="4 3" fill="none"/>`;
    svgContent += `</g>`;
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
  const tooltip = mc
    ? `${nodeInfo[id].name}\\n设备：${mc.machine}\\n台数：${mc.machineCount}\\n需求：${mc.demand}\\n实际：${mc.actualOutput}\\n溢出：${mc.overproduce}（${mc.efficiency}%）`
    : nodeInfo[id].name;
  svgContent += `<g class="node" data-id="${id}" data-name="${nodeInfo[id].name}" data-tip="${tooltip}" transform="translate(${x},${y})">`;
  svgContent += `<rect width="${NODE_W}" height="${NODE_H()}" rx="9" fill="${fill}" stroke="${stroke}" stroke-width="2.5"/>`;
  svgContent += `<text x="${NODE_W / 2}" y="${NODE_H() / 2 - 6}" fill="#eef2f8" font-size="15" font-weight="700" text-anchor="middle">${nodeInfo[id].name}</text>`;
  svgContent += `<text x="${NODE_W / 2}" y="${NODE_H() / 2 + 14}" fill="#9fb0c8" font-size="12" text-anchor="middle">${sub}</text>`;
  svgContent += `</g>`;
});

const svg = `<svg id="lineSvg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" font-family="-apple-system,'Segoe UI',sans-serif">
  <rect width="${W}" height="${H}" fill="#161922"/>
  <g id="viewport">${svgContent}</g>
</svg>`;

// 统计内部带
let beltLines = [], totalBelt = 0, underfull = 0;
edgeInfo.forEach(e => {
  beltLines.push({ k: e.parent + '>' + e.child, flow: +e.flow.toFixed(2), belts: e.belts, fill: +(e.fill * 100).toFixed(0) });
  totalBelt += e.belts;
  if (e.fill < 0.95) underfull++;
});

// ---- HTML 外壳：交互控制 + 提示框 ----
const html = `<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>江城创业记 · 合并产线图（交互版）</title>
<style>
* { box-sizing: border-box; }
body { margin: 0; background: #0d0f14; color: #dfe6f0; font-family: -apple-system, 'Segoe UI', sans-serif; }
.wrap { max-width: 1200px; margin: 0 auto; padding: 26px 16px 70px; }
h1 { font-size: 21px; margin: 0 0 6px; }
.sub { color: #8a97ad; font-size: 13px; margin: 0 0 18px; line-height: 1.6; }
.legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: #aab6c8; margin: 8px 0 16px; padding: 12px 16px; background: #11141b; border: 1px solid #222a38; border-radius: 12px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.box { width: 14px; height: 14px; border-radius: 4px; border: 2px solid #5b6b86; background: #1b212c; }
.box.cry { border-color: #4aa8ff; background: #1d2330; }
.box.raw { border-color: #caa14a; background: #241f17; }
.sw { width: 22px; height: 0; border-top: 3px solid #3a4252; }
.sw.hot { border-color: #e0913a; }

.viewer { position: relative; background: #11141b; border: 1px solid #222a38; border-radius: 14px; overflow: hidden; height: 720px; }
.toolbar { position: absolute; top: 12px; left: 12px; z-index: 10; display: flex; gap: 6px; }
.toolbar button { background: #1b212c; border: 1px solid #2f3a4d; color: #c8d0e0; border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
.toolbar button:hover { background: #252d3a; border-color: #4aa8ff; }
.help { position: absolute; top: 12px; right: 12px; z-index: 10; color: #8a97ad; font-size: 12px; background: rgba(13,15,20,.85); padding: 6px 12px; border-radius: 8px; border: 1px solid #222a38; }
#svgWrap { width: 100%; height: 100%; cursor: grab; }
#svgWrap:active { cursor: grabbing; }
#svgWrap svg { display: block; width: 100%; height: 100%; }

.tooltip { position: fixed; pointer-events: none; background: rgba(17,20,27,.95); border: 1px solid #3a4252; border-radius: 10px; padding: 10px 14px; font-size: 13px; color: #dfe6f0; box-shadow: 0 8px 24px rgba(0,0,0,.45); opacity: 0; transition: opacity .08s; z-index: 100; max-width: 260px; line-height: 1.5; }
.tooltip.show { opacity: 1; }
.tooltip .tt-title { font-weight: 700; color: #fff; margin-bottom: 4px; }
.tooltip .tt-row { color: #aab6c8; }
.tooltip .tt-row b { color: #7df0ad; }

.tbl { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 6px; }
.tbl th, .tbl td { padding: 7px 10px; border-bottom: 1px solid #222a38; text-align: left; }
.tbl th { color: #8a97ad; font-weight: 600; }
.tbl td.num { text-align: right; font-variant-numeric: tabular-nums; }
.note { font-size: 12.5px; color: #9fb0c8; line-height: 1.7; background: #15201a; border: 1px solid #2c4a36; border-radius: 10px; padding: 12px 16px; margin: 14px 0; }
.note b { color: #7df0ad; }

/* 高亮样式 */
.dim { opacity: 0.12 !important; }
.highlight path { stroke: #4aa8ff !important; stroke-width: 4 !important; opacity: 1 !important; }
.highlight .node rect { stroke: #4aa8ff !important; stroke-width: 3.5 !important; }
.highlight-node rect { stroke: #4aa8ff !important; stroke-width: 4 !important; }
.tb-sep { width: 1px; height: 22px; background: #2f3a4d; margin: 0 4px; }
.fbtn { background: #1b212c; border: 1px solid #2f3a4d; border-radius: 8px; padding: 6px 12px; font-size: 13px; cursor: pointer; color: #c8d0e0; }
.fbtn:hover { background: #252d3a; }
.fbtn.active { background: #243044; border-color: #4aa8ff; color: #fff !important; }
</style></head><body><div class="wrap">
<h1>江城创业记 · 合并产线图（共享中间产物 · 可交互）</h1>
<p class="sub">需求 50蓝 / 180绿 / 600红 · 周期 1800s · 带速 2/s · 机器按向上取整（已全局共享，共 38 台）<br>
<b>原始矿「直接进入」</b>：矿石/原木/石头不作为厂内带，直接喂入对应冶炼/加工节点（金色虚线侧框）。厂内带只算中间产物运输。</p>

<div class="legend">
<span><i class="box cry"></i>晶能(目标)</span>
<span><i class="box"></i>中间产物(设备×台数)</span>
<span><i class="box raw"></i>原始矿(直入)</span>
<span><i class="sw"></i>≤2/s 单带</span>
<span><i class="sw hot"></i>&gt;2/s 需双带</span>
<span>边标签：吞吐/s · 带数（填充率&lt;95% 标橙）</span>
</div>

<div class="viewer">
  <div class="toolbar">
    <button id="btnZoomIn">放大 +</button>
    <button id="btnZoomOut">缩小 -</button>
    <button id="btnReset">复位 1:1</button>
    <button id="btnFit">适配窗口</button>
    <span class="tb-sep"></span>
    <button id="btnAll" class="fbtn active">全部</button>
    <button id="btnRed" class="fbtn" style="color:#ff5c5c">只看红</button>
    <button id="btnGreen" class="fbtn" style="color:#3ddc84">只看绿</button>
    <button id="btnBlue" class="fbtn" style="color:#4aa8ff">只看蓝</button>
  </div>
  <div class="help">滚轮缩放 · 拖拽平移 · 点「只看X」隔离该晶能供应链 · 点节点高亮上游 · 悬停看详情</div>
  <div id="svgWrap">${svg}</div>
</div>

<div class="note">
<b>合并后的带况：</b>厂内带共 <b>${totalBelt}</b> 条，其中 <b>${underfull}</b> 条未跑满（&lt;95%）。最粗的四条带是
<b>铁锭 1.33/s、铜锭 1.33/s、木纤维 1.5/s、螺丝 1.5/s</b>——都只用了单条 2/s 带的 67%~75%。<br>
<b>怎么跑满 2/s：</b>当前机器数是「向上取整」定的，产出是分数的整数倍，所以带子填不满。要填满，就把这几台机器加到让产出率 = 2/s 的整数倍：
铁锭/铜锭 1.33→<b>6 台=2.0/s（满）</b>、木纤维 1.5→<b>4 台=2.0/s（满）</b>、螺丝 1.5→ 需 4 台=6.0/s（3 条满带）。
代价是这些中间产物会超额生产（铁锭从 2400→3600/周期），连带下游晶体也超额——属于「用超额换满带」，是否划算看你舍不舍得堆机器。
</div>

<h2 style="font-size:16px;margin:18px 0 8px">厂内带明细（中间产物运输）</h2>
<table class="tbl"><thead><tr><th>物料链（父→子）</th><th class="num">吞吐 /s</th><th class="num">带数</th><th class="num">填充率</th></tr></thead><tbody>
${beltLines.sort((a, b) => b.flow - a.flow).map(b => {
  const [p, c] = b.k.split('>');
  return `<tr><td>${nodeInfo[p].name} → ${nodeInfo[c].name}</td><td class="num">${b.flow}</td><td class="num">${b.belts}</td><td class="num" style="color:${b.fill < 95 ? '#f0b46a' : '#7df0ad'}">${b.fill}%</td></tr>`;
}).join('')}
</tbody></table>

<div class="note" style="margin-top:20px">
<b>关于「合并」的实话：</b>铁锭、铜锭这类节点既被红色浅链吃、又被蓝色深链吃。合并成单节点后，蓝色深链那一侧必然拉出横跨 3~4 层的长带——
而 2/s 带恰恰拉不动这种长途。所以「完全合并成一条线」和「2/s 带」本身有张力。务实做法是：
<b>铁锭/铜锭/木纤维/螺丝 这些真·共享枢纽建一处</b>（它们本来就在产线底部、靠近矿源），蓝色深链里的专用分支（铁质核心→加固铁板→…）就地本地化，
不要为了合并而拉长途带。
</div>

</div>
<div id="tooltip" class="tooltip"></div>

<script>
(function(){
  const wrap = document.getElementById('svgWrap');
  const svg = document.getElementById('lineSvg');
  const vp = document.getElementById('viewport');
  const tooltip = document.getElementById('tooltip');

  let sx = 0, sy = 0, k = 1, dragging = false, lastX = 0, lastY = 0;

  function apply() {
    vp.setAttribute('transform', \`translate(\${sx}, \${sy}) scale(\${k})\`);
  }

  function fit() {
    const rect = wrap.getBoundingClientRect();
    const vbW = ${W}, vbH = ${H};
    const padding = 24;
    const scale = Math.min((rect.width - padding * 2) / vbW, (rect.height - padding * 2) / vbH);
    k = Math.max(0.15, Math.min(scale, 3));
    sx = (rect.width - vbW * k) / 2;
    sy = (rect.height - vbH * k) / 2;
    apply();
  }

  wrap.addEventListener('wheel', e => {
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    const newK = Math.max(0.2, Math.min(k * factor, 5));
    sx = mx - (mx - sx) * (newK / k);
    sy = my - (my - sy) * (newK / k);
    k = newK;
    apply();
  }, { passive: false });

  wrap.addEventListener('mousedown', e => {
    dragging = true; lastX = e.clientX; lastY = e.clientY; wrap.style.cursor = 'grabbing';
  });
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    sx += e.clientX - lastX; sy += e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    apply();
  });
  window.addEventListener('mouseup', () => { dragging = false; wrap.style.cursor = 'grab'; });

  document.getElementById('btnZoomIn').onclick = () => {
    const rect = wrap.getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 2;
    const newK = Math.min(k * 1.25, 5);
    sx = cx - (cx - sx) * (newK / k);
    sy = cy - (cy - sy) * (newK / k);
    k = newK; apply();
  };
  document.getElementById('btnZoomOut').onclick = () => {
    const rect = wrap.getBoundingClientRect();
    const cx = rect.width / 2, cy = rect.height / 2;
    const newK = Math.max(k / 1.25, 0.2);
    sx = cx - (cx - sx) * (newK / k);
    sy = cy - (cy - sy) * (newK / k);
    k = newK; apply();
  };
  document.getElementById('btnReset').onclick = () => { sx = 0; sy = 0; k = 1; apply(); };
  document.getElementById('btnFit').onclick = fit;

  // 晶能供应链隔离按钮
  const fbtns = { btnAll: null, btnRed: '红色晶能', btnGreen: '绿色晶能', btnBlue: '蓝色晶能' };
  function setActiveFilter(id) {
    Object.keys(fbtns).forEach(k => document.getElementById(k).classList.toggle('active', k === id));
  }
  document.getElementById('btnAll').onclick = () => { setActiveFilter('btnAll'); highlightUpstream(null); };
  document.getElementById('btnRed').onclick = () => { setActiveFilter('btnRed'); highlightUpstream('红色晶能'); };
  document.getElementById('btnGreen').onclick = () => { setActiveFilter('btnGreen'); highlightUpstream('绿色晶能'); };
  document.getElementById('btnBlue').onclick = () => { setActiveFilter('btnBlue'); highlightUpstream('蓝色晶能'); };

  // 提示框
  function showTip(e, title, html) {
    tooltip.innerHTML = '<div class="tt-title">' + title + '</div>' + html;
    tooltip.classList.add('show');
    moveTip(e);
  }
  function moveTip(e) {
    const x = e.clientX + 14, y = e.clientY + 14;
    const maxX = window.innerWidth - tooltip.offsetWidth - 10;
    const maxY = window.innerHeight - tooltip.offsetHeight - 10;
    tooltip.style.left = Math.min(x, maxX) + 'px';
    tooltip.style.top = Math.min(y, maxY) + 'px';
  }
  function hideTip() { tooltip.classList.remove('show'); }

  // 节点事件
  document.querySelectorAll('.node').forEach(g => {
    g.addEventListener('mouseenter', e => {
      const tip = g.dataset.tip.replace(/\\n/g, '<br>');
      showTip(e, g.dataset.name, '<div class="tt-row">' + tip.split('<br>').slice(1).join('<br>') + '</div>');
    });
    g.addEventListener('mousemove', moveTip);
    g.addEventListener('mouseleave', hideTip);
    g.addEventListener('click', e => {
      e.stopPropagation();
      const id = g.dataset.id;
      highlightUpstream(id);
    });
  });

  // 边提示
  document.querySelectorAll('.edge').forEach(g => {
    g.addEventListener('mouseenter', e => {
      const p = g.dataset.parent, c = g.dataset.child;
      const info = ${JSON.stringify(edgeInfo)}.find(x => x.parent === p && x.child === c);
      if (!info) return;
      showTip(e, nodeInfo[p].name + ' → ' + nodeInfo[c].name,
        '<div class="tt-row">吞吐：<b>' + info.flow.toFixed(2) + '</b> 个/s</div>' +
        '<div class="tt-row">带数：<b>' + info.belts + '</b> 条（' + (info.belts * BELT) + ' /s 容量）</div>' +
        '<div class="tt-row">填充率：<b>' + (info.fill * 100).toFixed(0) + '%</b></div>' +
        '<div class="tt-row">周期需求：<b>' + info.qty.toFixed(0) + '</b></div>');
    });
    g.addEventListener('mousemove', moveTip);
    g.addEventListener('mouseleave', hideTip);
  });

  // 高亮上游；targetId 为 null 时清除全部高亮
  function highlightUpstream(targetId) {
    const edges = document.querySelectorAll('.edge');
    const nodes = document.querySelectorAll('.node');
    const raws = document.querySelectorAll('.raw-node');
    const allNodeIds = new Set(Array.from(nodes).map(n => n.dataset.id));
    const allRawIds = new Set(Array.from(raws).map(n => n.dataset.id));
    if (!targetId) {
      nodes.forEach(n => n.classList.remove('dim', 'highlight', 'highlight-node'));
      raws.forEach(n => n.classList.remove('dim'));
      edges.forEach(g => g.classList.remove('dim', 'highlight'));
      return;
    }
    const highlightNodes = new Set([targetId]);
    // 反向 BFS 找所有上游节点（含原始矿）
    let changed = true;
    while (changed) {
      changed = false;
      edges.forEach(g => {
        if (highlightNodes.has(g.dataset.child) && (allNodeIds.has(g.dataset.parent) || allRawIds.has(g.dataset.parent))) {
          if (!highlightNodes.has(g.dataset.parent)) { highlightNodes.add(g.dataset.parent); changed = true; }
        }
      });
    }
    nodes.forEach(n => {
      n.classList.toggle('dim', !highlightNodes.has(n.dataset.id));
      n.classList.toggle('highlight-node', n.dataset.id === targetId);
    });
    raws.forEach(n => n.classList.toggle('dim', !highlightNodes.has(n.dataset.id)));
    edges.forEach(g => {
      const active = highlightNodes.has(g.dataset.parent) && highlightNodes.has(g.dataset.child);
      g.classList.toggle('dim', !active);
      g.classList.toggle('highlight', active && g.dataset.child !== targetId);
    });
  }

  // 点击空白取消高亮并复位过滤按钮
  wrap.addEventListener('click', e => {
    if (e.target === wrap || e.target === svg) {
      highlightUpstream(null);
      setActiveFilter('btnAll');
    }
  });

  // 初始适配窗口
  window.addEventListener('load', fit);
  if (document.readyState === 'complete') fit();
})();
</script>
</body></html>`;

fs.writeFileSync('./merged-line.html', html);
console.log('written merged-line.html (interactive); WxH=', W, 'x', H);
