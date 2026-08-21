/**
 * 从 ceil-result.json 生成总线式产线 SVG
 */
const fs = require('fs');
const r = JSON.parse(fs.readFileSync('./ceil-result.json', 'utf8'));

const mMap = {};
r.machines.forEach(m => mMap[m.id] = m);
const matMap = {};
r.materials.forEach(m => matMap[m.id] = m);

// 每个产物的 [列, 行]
const POS = {
  // C0 原料
  '铁矿石':[0,0],'煤矿石':[0,1],'铜矿石':[0,2],'石头':[0,3],'原木':[0,4],
  // C1 冶炼
  '铁锭':[1,0],'铜锭':[1,1],'木材':[1,2],'木纤维':[1,3],
  // C2 成型
  '钢锭':[2,0],'铁板':[2,1],'铜板':[2,2],'木棒':[2,3],'石材':[2,4],
  // C3 零件
  '铁棒':[3,0],'螺丝':[3,1],'线':[3,2],'木质框架':[3,3],
  // C4 子装配
  '加固铁板':[4,0],'布':[4,1],'初级工具':[4,2],'钢管':[4,3],
  // C5 能量
  'C级能量块':[5,0],'铁质核心':[5,1],
  // C6 晶能
  '蓝色晶能':[6,0],'绿色晶能':[6,1],'红色晶能':[6,2],
};

const COLX = [10,175,340,505,670,835,1000];
const STEP = 54;
const YBASE = 252; // 第0行y
function boxY(col){
  const n = Object.values(POS).filter(p=>p[0]===col).length;
  const start = YBASE - (n*STEP)/2 + STEP/2 + 40;
  return start;
}
const BW = 155, BH = 48;

function coord(id){
  const [c,row] = POS[id];
  const y0 = boxY(c);
  return { x: COLX[c], y: y0 + row*STEP, cx: COLX[c]+BW/2, cy: y0+row*STEP+BH/2 };
}

// Stage labels
const STAGES = [
  [0,'①原料'],
  [1,'②冶炼'],
  [2,'③成型'],
  [3,'④零件'],
  [4,'⑤子装配'],
  [5,'⑥能量'],
  [6,'⑦晶能产出'],
];

// dependencies: consumer -> [inputs]
const DEPS = {
  '铁锭':['铁矿石'],'铜锭':['铜矿石'],'木材':['原木'],'木纤维':['原木'],
  '钢锭':['铁矿石','煤矿石'],'铁板':['铁锭'],'铜板':['铜锭'],'木棒':['木材'],'石材':['石头'],
  '铁棒':['铁锭'],'螺丝':['铁棒'],'线':['木纤维'],'木质框架':['木棒','螺丝'],
  '加固铁板':['铁板','螺丝'],'布':['线'],'初级工具':['木棒','石材'],'钢管':['钢锭'],
  'C级能量块':['铜板','木质框架'],'铁质核心':['加固铁板','C级能量块'],
  '蓝色晶能':['铁质核心','钢管'],'绿色晶能':['布','初级工具'],'红色晶能':['铁锭','铜锭'],
};

const STAGE_COLOR = ['#5b6472','#3d7fb8','#3d9e8f','#c9a227','#d98324','#c0504d','#8e44ad'];
const RAW_COLOR = '#5b6472';

let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 380" font-family="-apple-system,'Segoe UI',sans-serif">
<g transform="scale(0.5763)">
<rect width="1180" height="660" fill="#1a1d24"/>`;

// title
svg += `<text x="20" y="26" fill="#e8eaed" font-size="18" font-weight="700">江城创业记 · 产线总线图</text>`;
svg += `<text x="20" y="46" fill="#9aa0a6" font-size="12">目标 50蓝 / 180绿 / 600红 · 周期 1800s(30分) · 2级带 · 机器向上取整</text>`;

// stage labels
STAGES.forEach(([c,label])=>{
  svg += `<text x="${COLX[c]+BW/2}" y="74" fill="${STAGE_COLOR[c]}" font-size="12" font-weight="700" text-anchor="middle">${label}</text>`;
  svg += `<line x1="${COLX[c]}" y1="82" x2="${COLX[c]+BW}" y2="82" stroke="${STAGE_COLOR[c]}" stroke-width="2" opacity="0.5"/>`;
});

// arrows (draw first, behind boxes)
function arrow(x1,y1,x2,y2){
  // curve
  const mx = (x1+x2)/2;
  return `<path d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" fill="none" stroke="#4a5160" stroke-width="1.3" opacity="0.65"/>
  <circle cx="${x2}" cy="${y2}" r="2.5" fill="#6b7689"/>`;
}
Object.keys(DEPS).forEach(consumer=>{
  const cc = coord(consumer);
  DEPS[consumer].forEach(inp=>{
    const ic = coord(inp);
    const x1 = ic.x+BW, y1 = ic.cy;
    const x2 = cc.x, y2 = cc.cy;
    svg += arrow(x1,y1,x2,y2);
  });
});

// boxes
function box(id, isRaw){
  const c = coord(id);
  const info = isRaw ? matMap[id] : mMap[id];
  const x=c.x, y=c.y;
  const col = isRaw ? RAW_COLOR : STAGE_COLOR[POS[id][0]];
  let title = info.name;
  let line2, line3;
  if(isRaw){
    line2 = `需求 ${info.totalQty}`;
    line3 = `带${info.belts}条`;
  } else {
    line2 = `×${info.machineCount}台 ${info.machine}`;
    line3 = `带${info.belts}条 · 实际${info.actualOutput}`;
  }
  svg += `<g>
    <rect x="${x}" y="${y}" width="${BW}" height="${BH}" rx="6" fill="#252a33" stroke="${col}" stroke-width="2"/>
    <rect x="${x}" y="${y}" width="5" height="${BH}" rx="2" fill="${col}"/>
    <text x="${x+11}" y="${y+19}" fill="#e8eaed" font-size="13" font-weight="700">${title}</text>
    <text x="${x+11}" y="${y+33}" fill="#9aa0a6" font-size="10.5">${line2}</text>
    <text x="${x+11}" y="${y+45}" fill="#7d8590" font-size="10">${line3}</text>
  </g>`;
}
// draw raw first then machines (machines on top)
Object.keys(POS).forEach(id=>{
  if(matMap[id]) box(id,true);
});
Object.keys(POS).forEach(id=>{
  if(mMap[id]) box(id,false);
});

// legend
let ly = 600;
svg += `<rect x="20" y="${ly-14}" width="1140" height="40" rx="6" fill="#22262f" stroke="#3a414d"/>`;
svg += `<text x="32" y="${ly+10}" fill="#9aa0a6" font-size="11">图例：</text>`;
svg += `<rect x="72" y="${ly-2}" width="14" height="14" rx="3" fill="#252a33" stroke="#5b6472" stroke-width="2"/><text x="92" y="${ly+10}" fill="#9aa0a6" font-size="11">原料</text>`;
svg += `<rect x="150" y="${ly-2}" width="14" height="14" rx="3" fill="#252a33" stroke="#3d7fb8" stroke-width="2"/><text x="170" y="${ly+10}" fill="#9aa0a6" font-size="11">工序产物(颜色=阶段)</text>`;
svg += `<text x="360" y="${ly+10}" fill="#9aa0a6" font-size="11">框内：产物名 / ×台数+设备 / 传送带条数+实际产量</text>`;
svg += `<text x="800" y="${ly+10}" fill="#9aa0a6" font-size="11">箭头：物料流向(上游→下游)　总线自左向右：原料→晶能</text>`;

svg += `</g></svg>`;
fs.writeFileSync('./bus.svg', svg);
console.log('bus.svg written, size=', svg.length);
// print extra products
console.log('\n=== 额外产出（除晶能外） ===');
r.machines.filter(m=>m.overproduce>0.5).sort((a,b)=>b.overproduce-a.overproduce).forEach(m=>{
  console.log(m.name.padEnd(7), '需求', m.demand, '实际', m.actualOutput, '多余', m.overproduce, '('+m.efficiency+'%)');
});
console.log('\n目标晶能实际产出:',
  '蓝', mMap['蓝色晶能'].actualOutput, '(需50)',
  '绿', mMap['绿色晶能'].actualOutput, '(需180)',
  '红', mMap['红色晶能'].actualOutput, '(需600)');
