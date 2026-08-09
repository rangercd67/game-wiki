/**
 * 江城创业记 · 厂区机器摆放蓝图 v2
 * 关键修正：画全「区块内部」机器之间的带子（谁喂谁），矿石/原木直入画成喂料带。
 * 机器按产线上下游定位（不是网格小格），点机器高亮整条上/下游产线。
 *
 * 数据来源：ceil-result.json（50蓝/180绿/600红 · 30分钟周期 · 2级带 · 向上取整不配平）
 */

const fs = require('fs');
const R = JSON.parse(fs.readFileSync('./ceil-result.json', 'utf8'));
const T = R.timePeriod; // 1800

// 产物聚合需求 / 配方（来自 ceil-result）
const M = {};
R.machines.forEach(m => { M[m.id] = m; });
// 原料吞吐
const RAW = {};
R.materials.forEach(m => { RAW[m.id] = m; });

// 计算一条带子的吞吐（个/秒）：下游 B 每周期消耗 M 的量 / 周期
function rateOf(matId, toId) {
  const b = M[toId];
  if (!b) return 0;
  const inp = (b.recipe.inputs.find(i => i.item === matId) || {}).qty || 0;
  const crafts = b.demand / b.recipe.output; // 每周期制作次数
  return (crafts * inp) / T;
}
// 原料直入吞吐
function rateRaw(matId, toId) {
  const b = M[toId];
  const inp = (b.recipe.inputs.find(i => i.item === matId) || {}).qty || 0;
  const crafts = b.demand / b.recipe.output;
  return (crafts * inp) / T;
}

// ===================== 区块背景 =====================
const ZONES = [
  { key:'hub',  name:'冶炼中枢',     color:'#3b6ea5', x:355, y:38,  w:480, h:125, note:'全厂金属源头。铁锭/铜锭被红区蓝区共用，放正中；钢锭就近。' },
  { key:'red',  name:'红晶能区',     color:'#c0392b', x:950, y:52,  w:215, h:125, note:'最简单的一条线：2台晶体置换机，配方只吃铁锭×3+铜锭×3。' },
  { key:'wood', name:'木作/纺织/绿晶区', color:'#27ae60', x:30,  y:380, w:580, h:415, note:'两条木链+初级工具+绿晶能。绿晶能直接吃本区产物不跨带。' },
  { key:'blue', name:'蓝晶能核心区', color:'#2980b9', x:620, y:380, w:565, h:415, note:'最深的7层装配链。铁/铜/钢从中枢拉带进来，木质框架从木作区拉进来。' },
];

// ===================== 机器节点（x,y = 左上角，盒子 116×50）=====================
const BW = 116, BH = 50;
const NODES = [
  // HUB
  { key:'iron',   id:'铁锭',     label:'铁锭',     n:4, eq:'冶炼器',     x:400, y:64, zone:'hub' },
  { key:'copper', id:'铜锭',     label:'铜锭',     n:4, eq:'冶炼器',     x:560, y:64, zone:'hub' },
  { key:'steel',  id:'钢锭',     label:'钢锭',     n:1, eq:'熔铸机',     x:720, y:64, zone:'hub' },
  // RED
  { key:'red',    id:'红色晶能', label:'红色晶能', n:2, eq:'晶体置换机', x:965, y:82, zone:'red' },
  // BLUE（右下）
  { key:'plate',  id:'铁板',     label:'铁板',     n:1, eq:'制作台',     x:640, y:420, zone:'blue' },
  { key:'rod',    id:'铁棒',     label:'铁棒',     n:1, eq:'制作台',     x:640, y:512, zone:'blue' },
  { key:'screw',  id:'螺丝',     label:'螺丝',     n:1, eq:'制作台',     x:840, y:512, zone:'blue' },
  { key:'rplate', id:'加固铁板', label:'加固铁板', n:1, eq:'制作台',     x:840, y:420, zone:'blue' },
  { key:'cplate', id:'铜板',     label:'铜板',     n:1, eq:'制作台',     x:640, y:606, zone:'blue' },
  { key:'cblock', id:'C级能量块',label:'C级能量块',n:1, eq:'核心充能器', x:840, y:606, zone:'blue' },
  { key:'core',   id:'铁质核心', label:'铁质核心', n:1, eq:'制作台',     x:1040,y:470, zone:'blue' },
  { key:'pipe',   id:'钢管',     label:'钢管',     n:1, eq:'制作台',     x:640, y:698, zone:'blue' },
  { key:'blue',   id:'蓝色晶能', label:'蓝色晶能', n:1, eq:'晶体置换机', x:1040,y:650, zone:'blue' },
  // WOOD（左下）
  { key:'woodm',  id:'木材',     label:'木材',     n:2, eq:'制作台',     x:50,  y:450, zone:'wood' },
  { key:'fiber',  id:'木纤维',   label:'木纤维',   n:3, eq:'制作台',     x:50,  y:545, zone:'wood' },
  { key:'stick',  id:'木棒',     label:'木棒',     n:2, eq:'制作台',     x:250, y:450, zone:'wood' },
  { key:'thread', id:'线',       label:'线',       n:4, eq:'制作台',     x:250, y:545, zone:'wood' },
  { key:'cloth',  id:'布',       label:'布',       n:2, eq:'制作台',     x:450, y:545, zone:'wood' },
  { key:'stone',  id:'石材',     label:'石材',     n:1, eq:'制作台',     x:250, y:640, zone:'wood' },
  { key:'tool',   id:'初级工具', label:'初级工具', n:2, eq:'制作台',     x:250, y:735, zone:'wood' },
  { key:'frame',  id:'木质框架', label:'木质框架', n:1, eq:'制作台',     x:450, y:450, zone:'wood' },
  { key:'green',  id:'绿色晶能', label:'绿色晶能', n:1, eq:'晶体置换机', x:450, y:640, zone:'wood' },
];

// ===================== 原料直入喂料点 =====================
const INTAKE = [
  { key:'ife1',  label:'铁矿直入', x:400, y:14, mat:'铁矿石' },
  { key:'ife2',  label:'铁矿直入', x:680, y:14, mat:'铁矿石' },
  { key:'icu',   label:'铜矿直入', x:560, y:14, mat:'铜矿石' },
  { key:'icoal', label:'煤矿直入', x:790, y:14, mat:'煤矿石' },
  { key:'ilog',  label:'原木直入', x:70,  y:356, mat:'原木' },
  { key:'istone',label:'石头直入', x:250, y:765, mat:'石头' },
];

// ===================== 带子（from→to，mat 为传输物料）=====================
// from/to 为节点 key（机器）或 intake key（原料）
const LINKS = [
  // —— 矿石/原木直入 ——
  { from:'ife1',  to:'iron',  mat:'铁矿石' },
  { from:'ife2',  to:'steel', mat:'铁矿石' },
  { from:'icu',   to:'copper',mat:'铜矿石' },
  { from:'icoal', to:'steel', mat:'煤矿石' },
  { from:'ilog',  to:'woodm', mat:'原木' },
  { from:'ilog',  to:'fiber', mat:'原木' },
  { from:'istone',to:'stone', mat:'石头' },
  // —— 中枢 → 红区 ——
  { from:'iron',   to:'red',    mat:'铁锭' },
  { from:'copper', to:'red',    mat:'铜锭' },
  // —— 中枢 → 蓝区 ——
  { from:'iron',   to:'plate',  mat:'铁锭' },
  { from:'iron',   to:'rod',    mat:'铁锭' },
  { from:'copper', to:'cplate', mat:'铜锭' },
  { from:'steel',  to:'pipe',   mat:'钢锭' },
  // —— 木作区 → 蓝区 ——
  { from:'frame',  to:'cblock', mat:'木质框架' },
  // —— 蓝区内部 ——
  { from:'rod',    to:'screw',  mat:'铁棒' },
  { from:'plate',  to:'rplate', mat:'铁板' },
  { from:'screw',  to:'rplate', mat:'螺丝' },
  { from:'cplate', to:'cblock', mat:'铜板' },
  { from:'rplate', to:'core',   mat:'加固铁板' },
  { from:'cblock', to:'core',   mat:'C级能量块' },
  { from:'core',   to:'blue',   mat:'铁质核心' },
  { from:'pipe',   to:'blue',   mat:'钢管' },
  // —— 蓝区 → 木作区（螺丝反哺木质框架）——
  { from:'screw',  to:'frame',  mat:'螺丝' },
  // —— 木作区内部 ——
  { from:'woodm',  to:'stick',  mat:'木材' },
  { from:'fiber',  to:'thread', mat:'木纤维' },
  { from:'stick',  to:'tool',   mat:'木棒' },
  { from:'stick',  to:'frame',  mat:'木棒' },
  { from:'thread', to:'cloth',  mat:'线' },
  { from:'stone',  to:'tool',   mat:'石材' },
  { from:'cloth',  to:'green',  mat:'布' },
  { from:'tool',   to:'green',  mat:'初级工具' },
];

// 预计算每条带子吞吐（个/秒）与所需带数
LINKS.forEach(l => {
  const toNode = NODES.find(n => n.key === l.to);
  const toId = toNode ? toNode.id : null;
  if (INTAKE.find(i => i.key === l.from)) {
    l.rate = rateRaw(l.mat, toId);
  } else {
    l.rate = rateOf(l.mat, toId);
  }
  l.belts = Math.max(1, Math.ceil(l.rate / 2)); // 2/s 带速
  l.sameZone = (() => {
    const a = INTAKE.find(i => i.key === l.from);
    const fn = a ? a.key : (NODES.find(n=>n.key===l.from)||{}).zone;
    const tn = (NODES.find(n=>n.key===l.to)||{}).zone;
    if (a) return false; // 直入带算跨区/供料
    return fn === tn;
  })();
});

// ===================== 绘制 =====================
function nodeCenter(n){ return { x:n.x+BW/2, y:n.y+BH/2 }; }
function intakeCenter(i){ return { x:i.x, y:i.y }; }

// 计算带子起止点（盒子边缘），并生成正交折线
function beltPath(fromPt, toPt, fromBox, toBox) {
  const c1 = fromBox ? nodeCenter(fromBox) : fromPt;
  const c2 = toBox   ? nodeCenter(toBox)   : toPt;
  let sx, sy, tx, ty;
  // 出口：fromBox 朝 c2 方向的边中点
  if (fromBox) {
    if (Math.abs(c2.x - c1.x) >= Math.abs(c2.y - c1.y)) { sx = c2.x > c1.x ? fromBox.x+BW : fromBox.x; sy = c1.y; }
    else { sy = c2.y > c1.y ? fromBox.y+BH : fromBox.y; sx = c1.x; }
  } else { sx = fromPt.x; sy = fromPt.y + 14; } // 直入点（向下出）
  // 入口：toBox 朝 c1 方向的边中点
  if (toBox) {
    if (Math.abs(c1.x - c2.x) >= Math.abs(c1.y - c2.y)) { tx = c1.x > c2.x ? toBox.x : toBox.x+BW; ty = c2.y; }
    else { ty = c1.y > c2.y ? toBox.y : toBox.y+BH; tx = c2.x; }
  } else { tx = toPt.x; ty = toPt.y; }
  const dx = tx - sx, dy = ty - sy;
  let d;
  if (Math.abs(dx) >= Math.abs(dy)) {
    const mx = sx + dx/2;
    d = `M ${sx} ${sy} L ${mx} ${sy} L ${mx} ${ty} L ${tx} ${ty}`;
  } else {
    const my = sy + dy/2;
    d = `M ${sx} ${sy} L ${sx} ${my} L ${tx} ${my} L ${tx} ${ty}`;
  }
  return { d, mx:(sx+tx)/2, my:(sy+ty)/2 };
}

// 节点 key→对象
const NODEMAP = {}; NODES.forEach(n => NODEMAP[n.key]=n);
const INTMAP = {}; INTAKE.forEach(i => INTMAP[i.key]=i);

function drawZones() {
  return ZONES.map(z => `<g class="zone">
    <rect x="${z.x}" y="${z.y}" width="${z.w}" height="${z.h}" rx="12" fill="${z.color}1a" stroke="${z.color}" stroke-width="2" stroke-dasharray="6 4" opacity="0.9"/>
    <text x="${z.x+12}" y="${z.y+22}" font-size="14" fill="${z.color}" font-weight="700">${z.name}</text>
  </g>`).join('\n');
}

function drawIntake() {
  return INTAKE.map(i => `<g class="intake" data-key="${i.key}">
    <rect x="${i.x-44}" y="${i.y-12}" width="88" height="26" rx="5" fill="#3a3320" stroke="#f1c40f" stroke-width="1.5"/>
    <text x="${i.x}" y="${i.y+6}" text-anchor="middle" font-size="11" fill="#f1c40f" font-weight="600">${i.label}</text>
  </g>`).join('\n');
}

function drawNodes() {
  return NODES.map(n => {
    const power = (M[n.id] ? M[n.id].power : 0);
    const equipShort = n.eq.replace('晶体置换机','晶体').replace('核心充能器','充能').replace('熔铸机','熔铸').replace('冶炼器','冶炼').replace('制作台','制作');
    return `<g class="node" data-key="${n.key}" data-id="${n.id}">
      <rect x="${n.x}" y="${n.y}" width="${BW}" height="${BH}" rx="7" fill="#222a36" stroke="${zoneColor(n.zone)}" stroke-width="2"/>
      <text x="${n.x+8}" y="${n.y+20}" font-size="13" fill="#fff" font-weight="700">${n.label}</text>
      <text x="${n.x+8}" y="${n.y+38}" font-size="11" fill="#9fb0c3">×${n.n} ${equipShort}${power?(' '+power+'kW'):''}</text>
    </g>`;
  }).join('\n');
}

function zoneColor(zk){ return (ZONES.find(z=>z.key===zk)||{}).color || '#888'; }

function drawBelts() {
  return LINKS.map((l, idx) => {
    const fk = l.from, tk = l.to;
    const fNode = NODEMAP[fk], tNode = NODEMAP[tk];
    const fPt = fNode ? nodeCenter(fNode) : intakeCenter(INTMAP[fk]);
    const tPt = tNode ? nodeCenter(tNode) : {x:0,y:0};
    const { d, mx, my } = beltPath(fPt, tPt, fNode, tNode);
    const isIntake = !!INTMAP[fk];
    const col = isIntake ? '#f1c40f' : (l.sameZone ? '#7fd1ff' : '#e0a458');
    const dash = isIntake ? 'stroke-dasharray="5 3"' : '';
    const label = `${l.mat} ${l.rate.toFixed(2)}/s${l.belts>1?(' ×'+l.belts+'带'):''}`;
    return `<g class="belt" data-idx="${idx}" data-from="${fk}" data-to="${tk}">
      <path d="${d}" fill="none" stroke="${col}" stroke-width="${l.belts*2.5}" opacity="0.55" ${dash} marker-end="url(#arrow)"/>
      <text x="${mx}" y="${my-4}" text-anchor="middle" font-size="10" fill="${col}" font-weight="600" paint-order="stroke" stroke="#0d0f14" stroke-width="3">${label}</text>
    </g>`;
  }).join('\n');
}

const W = 1190, H = 820;
const svg = `<svg id="floorsvg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" font-family="-apple-system,'Segoe UI',sans-serif">
<defs>
  <marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
    <path d="M0,0 L9,4.5 L0,9 Z" fill="#e8eaed"/>
  </marker>
</defs>
<rect width="${W}" height="${H}" fill="#11141b"/>
${drawZones()}
${drawIntake()}
${drawBelts()}
${drawNodes()}
</svg>`;

// 详情数据（点机器时显示）
const DETAIL = {};
NODES.forEach(n => {
  const m = M[n.id];
  const inputs = m ? m.recipe.inputs.map(i=>`${i.item}×${i.qty}`).join(' + ') : '';
  const sends = LINKS.filter(l => l.from === n.key).map(l => {
    const tn = NODEMAP[l.to]; return `${l.mat}→${tn?tn.label:l.to} (${l.rate.toFixed(2)}/s)`;
  });
  const feeds = LINKS.filter(l => l.to === n.key).map(l => {
    const fn = INTAKE.find(i=>i.key===l.from) || NODEMAP[l.from];
    return `${fn?fn.label:l.from}→${l.mat} (${l.rate.toFixed(2)}/s)`;
  });
  DETAIL[n.key] = {
    label:n.label, n:n.n, eq:n.eq, power: m?m.power:0,
    output: m?m.recipe.output:0, time: m?m.recipe.time:0,
    demand: m?m.demand:0, actual: m?m.actualOutput:0, eff: m?m.efficiency:0,
    inputs, sends, feeds,
  };
});

const headHtml = `<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>江城创业记 · 机器摆放蓝图 v2</title>
<style>
* { box-sizing: border-box; }
body { margin:0; background:#0d0f14; color:#e8eaed; font-family:-apple-system,'Segoe UI',sans-serif; }
.wrap { display:flex; height:100vh; }
.left { flex:1; overflow:hidden; position:relative; }
.right { width:360px; background:#161a22; border-left:1px solid #2a2e38; padding:18px; overflow:auto; }
#floorsvg { width:100%; height:100%; display:block; cursor:grab; }
#floorsvg.grabbing { cursor:grabbing; }
.toolbar { position:absolute; top:10px; left:10px; display:flex; gap:6px; z-index:5; }
.toolbar button { background:#222a36; color:#cdd6e2; border:1px solid #39414f; border-radius:6px; padding:6px 10px; font-size:12px; cursor:pointer; }
.toolbar button:hover { background:#2c3543; }
.legend { position:absolute; bottom:10px; left:10px; background:rgba(20,24,32,.85); border:1px solid #2a2e38; border-radius:8px; padding:8px 12px; font-size:11px; line-height:1.8; color:#aab; z-index:5; }
.legend .sw { display:inline-block; width:18px; height:3px; vertical-align:middle; margin-right:5px; }
.node rect { cursor:pointer; transition:stroke .12s; }
.node:hover rect { stroke:#fff; }
.belt.dim, .node.dim, .intake.dim, .zone.dim { opacity:0.12 !important; }
.belt.hot path { stroke:#ffffff !important; opacity:1 !important; stroke-width:6 !important; }
.belt.hot text { fill:#fff !important; }
.node.hot rect { stroke:#fff !important; stroke-width:3.5 !important; }
h2 { margin:0 0 4px; font-size:19px; }
.sub { color:#8a90a0; font-size:12px; margin-bottom:14px; }
.kpi { display:flex; gap:8px; margin-bottom:14px; }
.kpi div { flex:1; background:#1d222c; border-radius:8px; padding:9px; text-align:center; }
.kpi .v { font-size:18px; font-weight:700; }
.kpi .l { font-size:10px; color:#8a90a0; }
.card { background:#1d222c; border-radius:10px; padding:12px; margin-bottom:12px; border-left:4px solid #39414f; }
.card h3 { margin:0 0 8px; font-size:14px; }
.flow { font-size:12px; padding:5px 8px; background:#11151c; border-radius:6px; margin:4px 0; color:#c5c9d3; }
.flow b { color:#7fd1ff; }
.recipe { font-size:13px; color:#e0a458; font-weight:600; }
.note { font-size:12px; line-height:1.6; color:#b8c0cc; background:#11151c; padding:10px; border-radius:8px; margin-top:6px; }
.hint { color:#6f7686; font-size:12px; }
</style></head>
<body>
<div class="wrap">
  <div class="left">
    <div class="toolbar">
      <button id="btnZoomIn">放大 +</button>
      <button id="btnZoomOut">缩小 -</button>
      <button id="btnReset">复位</button>
      <button id="btnFit">适配</button>
      <button id="btnClear">清除高亮</button>
    </div>
    <div class="legend">
      <span class="sw" style="background:#f1c40f"></span>原料直入喂料带（厂外直供）<br>
      <span class="sw" style="background:#7fd1ff"></span>区块内部带（同区机器直连）<br>
      <span class="sw" style="background:#e0a458"></span>区块间带（跨区输送）<br>
      点任意机器 → 高亮它整条上游+下游产线
    </div>
    <div id="svgWrap">${svg}</div>
  </div>
  <div class="right" id="panel">
    <h2>机器摆放蓝图 v2</h2>
    <div class="sub">50蓝 / 180绿 / 600红 · 30分钟周期 · 2/s 带速 · 向上取整</div>
    <div class="kpi">
      <div><div class="v">38</div><div class="l">机器</div></div>
      <div><div class="v">148</div><div class="l">kW</div></div>
      <div><div class="v">29</div><div class="l">条带</div></div>
    </div>
    <div class="card" style="border-left-color:#e0a458">
      <h3>怎么看这张图</h3>
      <div class="note">每个方块 = 一台/一组机器，盒子写明「产物 ×台数 设备 功耗」。带子 = 传送带，连着「上一台的输出」到「下一台的输入」，标签写传输物料和吞吐(/s)。<br><br>
      <b>矿石/原木/石头</b>从顶部/底部黄色「直入」框喂进来，不占厂内带。<br><br>
      点任意机器（如蓝色晶能），会高亮它的整条产线：上游铁质核心→加固铁板→铁板→铁锭→铁矿，下游无（终点），一眼看清这条线要摆哪些机器、谁接谁。</div>
    </div>
    <div class="card" style="border-left-color:#6f7686">
      <h3>关于布局的实话</h3>
      <div class="note">冶炼(铁锭/铜锭/钢锭)集中放中枢，红/蓝两区都来拉带——好处是共享枢纽只建一处；代价是中枢到蓝区有几条横跨半个厂区的长带。但它们吞吐都 &lt;0.2/s，2/s 带单条轻松扛，只是物理上长。<br><br>若嫌长带碍眼，可把 1~2 台冶炼器拆到蓝区门口就近供铁——这是集中 vs 分散的取舍，图上先按集中画。</div>
    </div>
    <div id="nodeDetail"></div>
  </div>
</div>`;

const rawScript = `
var DETAIL = ` + JSON.stringify(DETAIL) + `;
var svg = document.getElementById('floorsvg');
var wrap = document.getElementById('svgWrap');
var viewport = (function(){ var g = document.createElementNS('http://www.w3.org/2000/svg','g'); g.setAttribute('id','viewport'); while(svg.firstChild) g.appendChild(svg.firstChild); svg.appendChild(g); return g; })();
var sx=0, sy=0, k=1;
function apply(){ viewport.setAttribute('transform','translate('+sx+','+sy+') scale('+k+')'); }
function fit(){
  var b = svg.getBoundingClientRect();
  var s = Math.min(b.width/1180, b.height/820);
  k = s; sx = (b.width - 1180*s)/2; sy = (b.height - 820*s)/2; apply();
}
// 缩放（以鼠标为中心）
wrap.addEventListener('wheel', function(e){
  e.preventDefault();
  var r = svg.getBoundingClientRect();
  var mx = e.clientX - r.left, my = e.clientY - r.top;
  var factor = e.deltaY < 0 ? 1.12 : 0.89;
  var nk = Math.max(0.2, Math.min(5, k*factor));
  sx = mx - (mx - sx) * (nk/k);
  sy = my - (my - sy) * (nk/k);
  k = nk; apply();
}, {passive:false});
// 拖拽平移
var dragging=false, lx=0, ly=0;
wrap.addEventListener('mousedown', function(e){ dragging=true; lx=e.clientX; ly=e.clientY; svg.classList.add('grabbing'); });
window.addEventListener('mousemove', function(e){ if(!dragging) return; sx += e.clientX-lx; sy += e.clientY-ly; lx=e.clientX; ly=e.clientY; apply(); });
window.addEventListener('mouseup', function(){ dragging=false; svg.classList.remove('grabbing'); });

document.getElementById('btnZoomIn').onclick=function(){ k=Math.min(5,k*1.2); apply(); };
document.getElementById('btnZoomOut').onclick=function(){ k=Math.max(0.2,k*0.83); apply(); };
document.getElementById('btnReset').onclick=function(){ sx=0; sy=0; k=1; apply(); };
document.getElementById('btnFit').onclick=fit;
document.getElementById('btnClear').onclick=function(){ clearHot(); };

// 节点邻接
var ADJ = {};
function ensure(k){ if(!ADJ[k]) ADJ[k]={up:[],down:[]}; }
` + (function(){
  // build adjacency from LINKS (need LINKS in browser). Embed LINKS.
  return 'var LINKS=' + JSON.stringify(LINKS.map(l=>({from:l.from,to:l.to}))) + ';\n' +
  'LINKS.forEach(function(l){ ensure(l.from); ensure(l.to); ADJ[l.from].down.push(l.to); ADJ[l.to].up.push(l.from); });\n';
})() + `
function collectChain(key){
  var set = new Set([key]);
  // up
  var stack = ADJ[key]?ADJ[key].up.slice():[];
  while(stack.length){ var c=stack.pop(); if(!set.has(c)){ set.add(c); (ADJ[c]?ADJ[c].up:[]).forEach(function(p){ stack.push(p); }); } }
  // down
  stack = ADJ[key]?ADJ[key].down.slice():[];
  while(stack.length){ var c=stack.pop(); if(!set.has(c)){ set.add(c); (ADJ[c]?ADJ[c].down:[]).forEach(function(p){ stack.push(p); }); } }
  return set;
}
function clearHot(){
  document.querySelectorAll('.node,.belt,.intake').forEach(function(el){ el.classList.remove('dim','hot'); });
}
function showNode(key){
  var d = DETAIL[key]; if(!d) return;
  var sends = d.sends.length ? d.sends.map(function(s){ return '<div class="flow">送 <b>'+s+'</b></div>'; }).join('') : '<div class="hint">终点产物，无外送</div>';
  var feeds = d.feeds.length ? d.feeds.map(function(s){ return '<div class="flow">收 <b>'+s+'</b></div>'; }).join('') : '<div class="hint">原料直入 / 起点</div>';
  var html = '<h2>'+d.label+'</h2><div class="sub">×'+d.n+' '+d.eq+(d.power?(' · '+d.power+'kW'):'')+'</div>'+
    '<div class="kpi"><div><div class="v">'+d.output+'</div><div class="l">单次产出</div></div><div><div class="v">'+d.time+'s</div><div class="l">制作时间</div></div><div><div class="v">'+d.eff+'%</div><div class="l">利用率</div></div></div>'+
    '<div class="card" style="border-left-color:#e0a458"><h3>配方</h3><div class="recipe">'+d.inputs+' → '+d.output+'</div><div class="hint" style="margin-top:4px">周期需求 '+Math.round(d.demand)+' / 实际产出 '+Math.round(d.actual)+'</div></div>'+
    '<div class="card" style="border-left-color:#7fd1ff"><h3>↓ 送去（下游）</h3>'+sends+'</div>'+
    '<div class="card" style="border-left-color:#5a8"><h3>↑ 收取（上游）</h3>'+feeds+'</div>';
  document.getElementById('nodeDetail').innerHTML = html;
}
document.querySelectorAll('.node').forEach(function(g){
  g.addEventListener('click', function(e){
    e.stopPropagation();
    var key = g.dataset.key;
    var chain = collectChain(key);
    clearHot();
    document.querySelectorAll('.node').forEach(function(el){ if(!chain.has(el.dataset.key)) el.classList.add('dim'); else el.classList.add('hot'); });
    document.querySelectorAll('.belt').forEach(function(el){ var f=el.dataset.from,t=el.dataset.to; if(chain.has(f)&&chain.has(t)) el.classList.add('hot'); else el.classList.add('dim'); });
    document.querySelectorAll('.intake').forEach(function(el){ if(chain.has(el.dataset.key)) el.classList.add('hot'); else el.classList.add('dim'); });
    showNode(key);
  });
});
document.querySelectorAll('.intake').forEach(function(g){
  g.addEventListener('click', function(e){
    e.stopPropagation();
    var key = g.dataset.key;
    var chain = collectChain(key);
    clearHot();
    document.querySelectorAll('.intake').forEach(function(el){ if(chain.has(el.dataset.key)) el.classList.add('hot'); else el.classList.add('dim'); });
    document.querySelectorAll('.node').forEach(function(el){ if(chain.has(el.dataset.key)) el.classList.add('hot'); else el.classList.add('dim'); });
    document.querySelectorAll('.belt').forEach(function(el){ var f=el.dataset.from,t=el.dataset.to; if(chain.has(f)&&chain.has(t)) el.classList.add('hot'); else el.classList.add('dim'); });
  });
});
svg.addEventListener('click', function(e){ if(e.target===svg||e.target===viewport) clearHot(); });
window.addEventListener('load', fit);
`;

const html = headHtml + '<script>' + rawScript + '</script></body></html>';
fs.writeFileSync('./layout2.html', html);
console.log('layout2.html written, size=', html.length, 'nodes=', NODES.length, 'links=', LINKS.length);
