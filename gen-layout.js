/**
 * 生成江城创业记 厂区布局蓝图 (俯视图)
 * 把 38 台机器按功能分成 4 个区块，标注内部摆放、区块间带子、矿石卸料点
 */

const fs = require('fs');

// ===== 区块定义（数据来自 ceil-result.json 聚合结果）=====
// machine: [名称, 数量, 设备类型, 单台功耗]
const BLOCKS = {
  hub: {
    name: '冶炼中枢',
    sub: '贴矿石卸料点',
    x: 370, y: 50, w: 260, h: 160,
    color: '#3b6ea5',
    machines: [
      ['铁锭', 4, '冶炼器', 5],
      ['铜锭', 4, '冶炼器', 5],
      ['钢锭', 1, '熔铸机', 16],
    ],
    power: 56,
    pulls: [], // 从其他区块拉
    pushes: [
      ['铁锭/铜锭', '红区', 1.0, 2, '红晶能直拉，铁铜各 1 带'],
      ['铁锭/铜锭/钢锭', '蓝区', 0.14, 2, '蓝区铁板/铁棒/铜板/钢管用，可共用 1-2 带'],
    ],
    note: '全厂金属源头。铁锭/铜锭被红区、蓝区共用，放正中让两边都够得着。钢锭走铁矿+煤矿，就近放中枢。',
  },
  red: {
    name: '红晶能区',
    sub: '紧挨中枢',
    x: 700, y: 70, w: 185, h: 120,
    color: '#c0392b',
    machines: [
      ['红色晶能', 2, '晶体置换机', 18],
    ],
    power: 36,
    pulls: [
      ['铁锭', '中枢', 1.0, 1, ''],
      ['铜锭', '中枢', 1.0, 1, ''],
    ],
    pushes: [],
    note: '最简单的一条线：2 台晶体置换机，配方只吃铁锭×3+铜锭×3。从中枢直接拉两条带即可，自带 100% 利用率无溢出。',
  },
  blue: {
    name: '蓝晶能核心区',
    sub: '左下·多级装配',
    x: 40, y: 370, w: 300, h: 250,
    color: '#2980b9',
    machines: [
      ['蓝色晶能', 1, '晶体置换机', 18],
      ['铁质核心', 1, '制作台', 0],
      ['加固铁板', 1, '制作台', 0],
      ['铁板', 1, '制作台', 0],
      ['螺丝', 1, '制作台', 0],
      ['铁棒', 1, '制作台', 0],
      ['C级能量块', 1, '核心充能器', 20],
      ['铜板', 1, '制作台', 0],
      ['钢管', 1, '制作台', 0],
    ],
    power: 38,
    pulls: [
      ['铁锭/铜锭/钢锭', '中枢', 0.14, 2, '铁板/铁棒/铜板/钢管用'],
      ['木质框架', '木作区', 0.03, 1, 'C级能量块用，流量极低'],
    ],
    pushes: [],
    note: '最深的链：铁质核心←加固铁板(铁板+螺丝) / C级能量块(铜板+木质框架)；钢管←钢锭；蓝晶能←铁质核心+钢管。建议按此链从上到下排成流水线，铁锭/铜锭从中枢、木质框架从木作区接入。',
  },
  wood: {
    name: '木作 / 纺织 / 绿晶区',
    sub: '右下·贴原木卸料',
    x: 380, y: 350, w: 565, h: 270,
    color: '#27ae60',
    machines: [
      ['木材', 2, '制作台', 0],
      ['木纤维', 3, '制作台', 0],
      ['木棒', 2, '制作台', 0],
      ['线', 4, '制作台', 0],
      ['布', 2, '制作台', 0],
      ['木质框架', 1, '制作台', 0],
      ['初级工具', 2, '制作台', 0],
      ['石材', 1, '制作台', 0],
      ['绿色晶能', 1, '晶体置换机', 18],
    ],
    power: 18,
    pulls: [
      ['原木', '卸料', 1.29, 1, '木纤维/木材用'],
      ['石头', '卸料', 0.2, 1, '初级工具用'],
    ],
    pushes: [
      ['布 / 初级工具', '绿晶能(本区)', 0.3, 0, '区内自产自销，不跨区'],
      ['木质框架', '蓝区', 0.03, 1, ''],
    ],
    note: '两条木链：原木→木纤维→线→布；原木→木材→木棒→初级工具(需石材)/木质框架。绿晶能(布×3+初级工具×2)直接吃本区产物，所以绿晶能放本区不跨带。',
  },
};

// ===== 机器单元格绘制 =====
function drawMachineCells(block) {
  const m = block.machines;
  const total = m.reduce((s, x) => s + x[1], 0);
  const cw = 50, ch = 38, gap = 6;
  const perRow = Math.max(4, Math.min(6, Math.ceil(Math.sqrt(total)) + 1));
  // 计算起始位置（水平居中）
  let drawn = 0;
  let rows = [];
  // 把数量展开成单元列表
  let cells = [];
  m.forEach(([name, cnt, eq, pw]) => {
    for (let i = 0; i < cnt; i++) cells.push({ name, eq, pw });
  });
  // 按 perRow 分行
  let y = block.y + 34;
  let xStart = block.x + (block.w - (perRow * cw + (perRow - 1) * gap)) / 2;
  let out = '';
  cells.forEach((c, i) => {
    const col = i % perRow;
    const row = Math.floor(i / perRow);
    const cx = xStart + col * (cw + gap);
    const cy = y + row * (ch + gap);
    const eqShort = c.eq === '晶体置换机' ? '晶体' : c.eq === '核心充能器' ? '充能' : c.eq === '熔铸机' ? '熔铸' : c.eq === '冶炼器' ? '冶炼' : '制作';
    out += `<g class="mcell">
      <rect x="${cx}" y="${cy}" width="${cw}" height="${ch}" rx="4" fill="${block.color}" stroke="rgba(255,255,255,.35)" stroke-width="1"/>
      <text x="${cx + cw/2}" y="${cy + 15}" text-anchor="middle" font-size="11" fill="#fff" font-weight="600">${c.name}</text>
      <text x="${cx + cw/2}" y="${cy + 30}" text-anchor="middle" font-size="9" fill="rgba(255,255,255,.75)">${eqShort}</text>
    </g>`;
  });
  return out;
}

// ===== 区块外框 =====
function drawBlock(key) {
  const b = BLOCKS[key];
  const cells = drawMachineCells(b);
  return `<g class="block" data-block="${key}">
    <rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="10" fill="rgba(255,255,255,.04)" stroke="${b.color}" stroke-width="2.5" class="block-rect"/>
    <text x="${b.x + 12}" y="${b.y + 22}" font-size="14" fill="${b.color}" font-weight="700">${b.name}</text>
    <text x="${b.x + b.w - 12}" y="${b.y + 22}" text-anchor="end" font-size="11" fill="rgba(255,255,255,.6)">${b.sub}</text>
    ${cells}
  </g>`;
}

// ===== 区块间带子 =====
function belt(x1, y1, x2, y2, label, belts, rate) {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  return `<g class="belt">
    <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#e0a458" stroke-width="${belts * 3}" opacity="0.8"/>
    <circle cx="${mx}" cy="${my}" r="3" fill="#e0a458"/>
    <text x="${mx}" y="${my - 8}" text-anchor="middle" font-size="10" fill="#e0a458" font-weight="600">${label}${belts > 1 ? ` ×${belts}带` : ''}</text>
  </g>`;
}

const belts = [
  // 中枢 → 红区（铁锭、铜锭 各 1 带）
  belt(630, 110, 700, 110, '铁锭', 1, 1.0),
  belt(630, 140, 700, 140, '铜锭', 1, 1.0),
  // 中枢 → 蓝区（铁/铜/钢 共用 2 带）
  belt(450, 210, 450, 370, '铁/铜/钢锭', 2, 0.14),
  // 木作区 → 蓝区（木质框架）
  belt(380, 500, 340, 500, '木质框架', 1, 0.03),
];

// ===== 矿石卸料点 =====
const intake = [
  { x: 430, y: 18, label: '铁矿 3.27/s', belts: 2 },
  { x: 520, y: 18, label: '铜矿 2.33/s', belts: 2 },
  { x: 600, y: 18, label: '煤矿 0.33/s', belts: 1 },
  { x: 560, y: 640, label: '原木 1.29/s', belts: 1 },
  { x: 760, y: 640, label: '石头 0.2/s', belts: 1 },
];

let intakeSvg = '';
intake.forEach(it => {
  // 箭头指向对应区块（上方三个指向中枢，下方两个指向木作区）
  let tx, ty, ty2;
  if (it.y < 30) { tx = it.x; ty = it.y + 8; ty2 = 50; }
  else { tx = it.x; ty = it.y - 8; ty2 = 620; }
  intakeSvg += `<g class="intake">
    <text x="${it.x}" y="${it.y}" text-anchor="middle" font-size="11" fill="#f1c40f" font-weight="700">▼ ${it.label}</text>
    <line x1="${tx}" y1="${ty}" x2="${tx}" y2="${ty2}" stroke="#f1c40f" stroke-width="${it.belts * 2}" opacity="0.7" stroke-dasharray="4 3"/>
  </g>`;
});

// ===== 详情面板数据 =====
const detail = {};
Object.keys(BLOCKS).forEach(k => {
  const b = BLOCKS[k];
  detail[k] = {
    name: b.name, color: b.color, power: b.power,
    machines: b.machines,
    pulls: b.pulls, pushes: b.pushes, note: b.note,
  };
});

const W = 1000, H = 670;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" font-family="-apple-system,'Segoe UI',sans-serif">
<rect width="${W}" height="${H}" fill="#171a21"/>
<text x="20" y="30" font-size="18" fill="#fff" font-weight="700">江城创业记 · 厂区布局蓝图（50蓝 / 180绿 / 600红 · 30分钟周期 · 2/s 带）</text>
${belts.join('\n')}
${intakeSvg}
${drawBlock('hub')}
${drawBlock('red')}
${drawBlock('blue')}
${drawBlock('wood')}
<text x="20" y="${H - 12}" font-size="11" fill="rgba(255,255,255,.45)">橙色带=区块间物料输送（全部单带够用）　黄色虚线=矿石/原木直接卸料（厂外，双带仅矿石）　点击区块看内部明细</text>
</svg>`;

const headHtml = `<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>江城创业记 · 厂区布局蓝图</title>
<style>
* { box-sizing: border-box; }
body { margin:0; background:#0f1115; color:#e8eaed; font-family:-apple-system,'Segoe UI',sans-serif; }
.wrap { display:flex; height:100vh; }
.left { flex:1; overflow:auto; padding:10px; }
.right { width:380px; background:#1c1f27; border-left:1px solid #2a2e38; padding:20px; overflow:auto; }
svg { width:100%; height:auto; display:block; }
.block-rect { cursor:pointer; transition:fill .15s; }
.block:hover .block-rect { fill:rgba(255,255,255,.09); }
.block-rect.active { stroke-width:4; filter:drop-shadow(0 0 6px currentColor); }
.mcell rect { pointer-events:none; }
h2 { margin:0 0 4px; font-size:20px; }
.sub { color:#8a90a0; font-size:13px; margin-bottom:16px; }
.card { background:#23262f; border-radius:10px; padding:14px; margin-bottom:14px; border-left:4px solid #444; }
.card h3 { margin:0 0 10px; font-size:15px; }
.mrow { display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #2c3038; font-size:13px; }
.mrow:last-child { border-bottom:none; }
.tag { font-size:11px; padding:1px 7px; border-radius:10px; background:#333a47; color:#aab; margin-left:6px; }
.flow { font-size:12px; padding:8px 10px; background:#1a1d24; border-radius:8px; margin:6px 0; }
.flow b { color:#e0a458; }
.note { font-size:13px; line-height:1.6; color:#c5c9d3; background:#1a1d24; padding:12px; border-radius:8px; }
.legend { font-size:12px; color:#9aa; margin-top:10px; line-height:1.7; }
.kpi { display:flex; gap:10px; margin-bottom:16px; }
.kpi div { flex:1; background:#23262f; border-radius:8px; padding:10px; text-align:center; }
.kpi .v { font-size:20px; font-weight:700; }
.kpi .l { font-size:11px; color:#8a90a0; }
.hint { color:#6f7686; font-size:12px; }
</style></head>
<body>
<div class="wrap">
  <div class="left">
    <div class="sub">俯视图 · 把 38 台机器按功能分成 4 个区块，区块内小格=单台机器，橙色带=区块间输送，黄虚线=矿石直接卸料</div>
    ${svg}
  </div>
  <div class="right" id="panel">
    <h2>布局总览</h2>
    <div class="sub">点击左侧任意区块查看内部机器清单与接带方式</div>
    <div class="kpi">
      <div><div class="v">38</div><div class="l">机器总数</div></div>
      <div><div class="v">148</div><div class="l">总功耗 kW</div></div>
      <div><div class="v">4</div><div class="l">功能区块</div></div>
    </div>
    <div class="card" style="border-left-color:#e0a458">
      <h3>区块间带子（全部单带）</h3>
      <div class="flow">中枢 → 红区：<b>铁锭 1.0/s</b> + <b>铜锭 1.0/s</b>，各 1 条带</div>
      <div class="flow">中枢 → 蓝区：铁锭/铜锭/钢锭，共用 1-2 条带（最大 0.17/s）</div>
      <div class="flow">木作区 → 蓝区：<b>木质框架 0.03/s</b>，1 条带</div>
    </div>
    <div class="card" style="border-left-color:#f1c40f">
      <h3>矿石 / 原木卸料（厂外直入）</h3>
      <div class="flow">铁矿 <b>3.27/s</b> · 铜矿 <b>2.33/s</b> → 各并 2 条带进中枢</div>
      <div class="flow">煤矿 0.33/s · 原木 1.29/s · 石头 0.2/s → 单带</div>
    </div>
    <div class="legend">
      为什么不做"总线(main bus)"：当前带速上限仅 4/s、实际 2/s，长途主干带拉不动多级物料；正确做法是<b>区块本地化</b>——每个区块就近直连下一工序，短带喂料。共享枢纽（铁锭/铜锭）放正中供两边用即可。
    </div>
  </div>
</div>`;

const rawScript = `
const panel = document.getElementById('panel');
function showBlock(k){
  var b = DETAIL[k];
  var macRows = b.machines.map(function(m){
    return '<div class="mrow"><span>'+m[0]+' <span class="tag">'+m[2]+(m[3]?(' '+m[3]+'kW'):'')+'</span></span><span style="font-weight:700;color:#7fd">×'+m[1]+'</span></div>';
  }).join('');
  var pulls = b.pulls.length? b.pulls.map(function(p){
    return '<div class="flow">从 <b>'+p[1]+'</b> 拉 '+p[0]+'（'+p[2]+'/s）'+(p[3]?(' · '+p[3]+' 带'):'')+'</div>';
  }).join('') : '<div class="hint">无跨区输入（靠本区/卸料）</div>';
  var pushes = b.pushes.length? b.pushes.map(function(p){
    return '<div class="flow">送 <b>'+p[1]+'</b>：'+p[0]+'（'+p[2]+'/s）'+(p[3]?(' · '+p[3]+' 带'):'')+'</div>';
  }).join('') : '<div class="hint">终点产物，无外送</div>';
  var total = b.machines.reduce(function(s,m){return s+m[1];},0);
  panel.innerHTML = '<h2 style="color:'+b.color+'">'+b.name+'</h2><div class="sub">功耗 '+b.power+' kW</div><div class="kpi"><div><div class="v">'+total+'</div><div class="l">机器台数</div></div></div><div class="card" style="border-left-color:'+b.color+'"><h3>内部机器清单</h3>'+macRows+'</div><div class="card" style="border-left-color:#5a8"><h3>跨区输入</h3>'+pulls+'</div><div class="card" style="border-left-color:#e0a458"><h3>跨区输出</h3>'+pushes+'</div><div class="note">'+b.note+'</div>';
  document.querySelectorAll('.block-rect').forEach(function(r){r.classList.remove('active');});
  var rect = document.querySelector('.block[data-block="'+k+'"] .block-rect');
  if(rect) rect.classList.add('active');
}
document.querySelectorAll('.block').forEach(function(g){
  g.addEventListener('click',function(){showBlock(g.dataset.block);});
});
`;

const scriptSrc = 'const DETAIL = ' + JSON.stringify(detail) + ';\n' + rawScript;
const html = headHtml + '<script>' + scriptSrc + '</script></body></html>';

fs.writeFileSync('./layout.html', html);
console.log('layout.html written, size=', html.length);
