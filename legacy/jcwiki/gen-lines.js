/**
 * 生成「按产物分链的树状产线图」HTML
 * 不使用总线(main bus)：每条晶能一条独立产线，忠实还原递归树
 * 每根物料边标注吞吐量(个/s)与所需传送带条数(基于 2/s 带速)
 */
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('./ceil-result.json', 'utf8'));

const TIME = data.timePeriod;        // 1800
const BELT = data.beltRate;          // 2

// 全局机器数 (ceil 后)
const machineMap = {};
data.machines.forEach(m => { machineMap[m.id] = m; });

const CRYSTALS = [
  { id: '红色晶能', color: '#ff5c5c', accent: '#ff8a8a' },
  { id: '绿色晶能', color: '#3ddc84', accent: '#7df0ad' },
  { id: '蓝色晶能', color: '#4aa8ff', accent: '#8ccbff' },
];

const NODE_W = 158, NODE_H = 60, TIER_H = 138, LEAF_GAP = 188, TOP = 70, SIDE = 40;

function buildPanel(treeRoot, crystal) {
  // 布局：叶子顺序分配 x，内部节点取子节点中点
  let leafX = 0;
  const maxDepth = { v: 0 };
  function layout(n, depth) {
    n._depth = depth;
    if (depth > maxDepth.v) maxDepth.v = depth;
    if (!n.children || n.children.length === 0) {
      n._x = leafX; leafX += LEAF_GAP;
    } else {
      n.children.forEach(c => layout(c, depth + 1));
      n._x = (n.children[0]._x + n.children[n.children.length - 1]._x) / 2;
    }
  }
  layout(treeRoot, 0);

  const W = leafX + SIDE;
  const H = maxDepth.v * TIER_H + TOP + NODE_H + 40;

  // 本地原始资源合计
  const rawLocal = {};
  function sumRaw(n) {
    if (n.isRaw) { rawLocal[n.id] = (rawLocal[n.id] || 0) + n.qty; }
    (n.children || []).forEach(sumRaw);
  }
  sumRaw(treeRoot);

  let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px;display:block;margin:0 auto;" font-family="-apple-system,'Segoe UI',sans-serif">`;
  svg += `<rect width="${W}" height="${H}" fill="#161922"/>`;

  // 边
  const edges = [];
  function collectEdges(n) {
    (n.children || []).forEach(c => {
      const flow = c.qty / TIME;                 // 该子产物被交付的吞吐
      const belts = Math.max(1, Math.ceil(flow / BELT));
      edges.push({ from: n, to: c, flow, belts });
      collectEdges(c);
    });
  }
  collectEdges(treeRoot);

  edges.forEach(e => {
    const x1 = e.from._x + NODE_W / 2, y1 = TOP + e.from._depth * TIER_H + NODE_H;
    const x2 = e.to._x + NODE_W / 2, y2 = TOP + e.to._depth * TIER_H;
    const fit = e.belts <= 1;
    const col = fit ? '#3a4252' : '#e0913a';
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${col}" stroke-width="2"/>`;
    // 边标签
    const lbl = `${e.flow.toFixed(2)}/s · ${e.belts}带`;
    const tw = lbl.length * 7 + 12;
    svg += `<rect x="${mx - tw / 2}" y="${my - 11}" width="${tw}" height="20" rx="5" fill="#0e1117" stroke="${col}" stroke-width="1"/>`;
    svg += `<text x="${mx}" y="${my + 4}" fill="${fit ? '#9fb0c8' : '#f0b46a'}" font-size="12" text-anchor="middle">${lbl}</text>`;
  });

  // 节点
  function drawNode(n) {
    const x = n._x, y = TOP + n._depth * TIER_H;
    const cx = x + NODE_W / 2, cy = y + NODE_H / 2;
    let fill, stroke, title, sub;
    if (n.id === crystal.id) {
      fill = '#1d2330'; stroke = crystal.color;
      title = n.name;
      sub = `${n.machine} ×${machineMap[n.id] ? machineMap[n.id].machineCount : '?'}`;
    } else if (n.isRaw) {
      fill = '#241f17'; stroke = '#caa14a';
      title = n.name;
      sub = `采集 · 本链 ${Math.round(rawLocal[n.id] || n.qty)}`;
    } else {
      fill = '#1b212c'; stroke = '#5b6b86';
      title = n.name;
      const mc = machineMap[n.id] ? machineMap[n.id].machineCount : '?';
      sub = `${n.machine} ×${mc}`;
    }
    svg += `<rect x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H}" rx="9" fill="${fill}" stroke="${stroke}" stroke-width="2.5"/>`;
    svg += `<text x="${cx}" y="${cy - 6}" fill="#eef2f8" font-size="15" font-weight="700" text-anchor="middle">${title}</text>`;
    svg += `<text x="${cx}" y="${cy + 14}" fill="#9fb0c8" font-size="12" text-anchor="middle">${sub}</text>`;
    (n.children || []).forEach(drawNode);
  }
  drawNode(treeRoot);

  svg += `</svg>`;
  return { svg, W, H };
}

// 组装 HTML
let html = `<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>江城创业记 · 分链产线图 (50蓝 / 180绿 / 600红)</title>
<style>
  body{margin:0;background:#0d0f14;color:#dfe6f0;font-family:-apple-system,'Segoe UI',sans-serif;}
  .wrap{max-width:1100px;margin:0 auto;padding:28px 18px 80px;}
  h1{font-size:22px;margin:0 0 6px;}
  .sub{color:#8a97ad;font-size:13px;margin:0 0 22px;line-height:1.6;}
  .panel{background:#11141b;border:1px solid #222a38;border-radius:14px;padding:18px 14px 8px;margin-bottom:30px;}
  .panel h2{font-size:17px;margin:0 0 4px;}
  .panel .note{font-size:12px;color:#8a97ad;margin:0 0 12px;}
  .legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:#aab6c8;margin:14px 0 26px;padding:12px 16px;background:#11141b;border:1px solid #222a38;border-radius:12px;}
  .legend span{display:inline-flex;align-items:center;gap:6px;}
  .box{width:14px;height:14px;border-radius:4px;border:2px solid #5b6b86;background:#1b212c;}
  .box.cry{border-color:#4aa8ff;background:#1d2330;}
  .box.raw{border-color:#caa14a;background:#241f17;}
  .sw{width:22px;height:0;border-top:3px solid #3a4252;}
  .sw.hot{border-color:#e0913a;}
  .insight{background:#15201a;border:1px solid #2c4a36;border-radius:12px;padding:14px 18px;margin:0 0 26px;font-size:13.5px;line-height:1.7;color:#cfe6d6;}
  .insight b{color:#7df0ad;}
  code{background:#1c2230;padding:1px 6px;border-radius:5px;color:#ffd479;}
</style></head><body><div class="wrap">
<h1>江城创业记 · 分链产线图</h1>
<p class="sub">需求：<b>50 蓝色晶能 / 180 绿色晶能 / 600 红色晶能</b> · 生产周期 1800s(30min) · 传送带 2/s（上限 4/s）· 机器数按向上取整（非配平）</p>

<div class="insight">
<b>布厂结论（基于 2/s 带速）：</b><br>
· 三条晶能各自独立成线，<b>不需要总线(main bus)</b>——总线依赖高速带串全厂，你这带子最慢只有 2/s，串不起来。<br>
· 产线<b>内部每一段物料流都 ≤1.5/s</b>，单条 2/s 带子全部够用（图上灰色边）。<br>
· 只有<b>原始矿 intake 超 2/s</b>（铁 3.27/s、铜 2.33/s），图上橙色边，需要并 2 条带或双矿场。<br>
· 推论：做法应该是<b>就近本地化生产</b>——每台机器直连下一台、短带喂料，别拉长途主干带。升级到 4/s 带后，连矿石都只需单带。
</div>

<div class="legend">
  <span><i class="box cry"></i>晶能(目标)</span>
  <span><i class="box"></i>中间产物(设备×台数)</span>
  <span><i class="box raw"></i>基础原料(采集)</span>
  <span><i class="sw"></i>≤2/s 单带够</span>
  <span><i class="sw hot"></i>&gt;2/s 需双带</span>
  <span>边标签：吞吐/s · 所需带数</span>
</div>
`;

data.trees.forEach(t => {
  const crystal = CRYSTALS.find(c => c.id === t.target.id);
  const p = buildPanel(t.tree, crystal);
  html += `<div class="panel">
    <h2 style="color:${crystal.color}">${t.target.id} 产线 · 需求 ${t.target.qty}</h2>
    <p class="note">忠实还原依赖树；中间产物在多个分支重复出现 = 各分支需独立供给（或自行拉带汇流）。</p>
    ${p.svg}
  </div>`;
});

html += `</div></body></html>`;
fs.writeFileSync('./production-lines.html', html);
console.log('written production-lines.html');
