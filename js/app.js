/**
 * 江城创业记产线计算器 - 主应用逻辑
 */

// ========== 状态管理 ==========
const state = {
  mode: "browse",        // browse | calc
  activeCategory: "all",  // all | category id
  searchQuery: "",
  timePeriod: 1800,       // 秒
  beltLevel: 2,           // 传送带等级 1-4
  plan: [],               // [{ id, qty }]
  machineChoices: {},     // { productId: machineName } 用户选择的机器
  calcResult: null,       // 计算结果缓存
};

// ========== 工具函数 ==========

function getTimePeriodSeconds() {
  const val = parseInt(document.getElementById("timePeriod").value) || 1800;
  const unit = parseInt(document.getElementById("timeUnit").value) || 1;
  return val * unit;
}

function getBeltRate() {
  const level = parseInt(document.getElementById("beltLevel").value) || 2;
  const belt = CONVEYOR_BELTS.find(b => b.level === level);
  return belt ? belt.rate : 2;
}

function getBeltLevel() {
  return parseInt(document.getElementById("beltLevel").value) || 2;
}

function getDefaultMachine(recipe) {
  // 默认选功耗最低的机器
  if (!recipe.equipment || recipe.equipment.length === 0) return "";
  let best = recipe.equipment[0];
  let bestPower = MACHINE_POWER[best] ?? 999;
  for (const m of recipe.equipment) {
    const p = MACHINE_POWER[m] ?? 999;
    if (p < bestPower) {
      best = m;
      bestPower = p;
    }
  }
  return best;
}

function getMachineForProduct(productId) {
  if (state.machineChoices[productId]) return state.machineChoices[productId];
  const recipe = ALL_ITEMS[productId];
  if (recipe && !recipe.isRaw) return getDefaultMachine(recipe);
  return "";
}

function fmtNum(n) {
  if (n === 0) return "0";
  if (Number.isInteger(n)) return n.toLocaleString();
  if (n < 0.01) return n.toFixed(4);
  if (n < 1) return n.toFixed(2);
  if (n < 100) return n.toFixed(1);
  return Math.ceil(n).toLocaleString();
}

function fmtQty(n) {
  if (n >= 10000) return (n / 1000).toFixed(1) + "k";
  if (n >= 100) return Math.ceil(n).toString();
  if (n >= 1) return n.toFixed(1);
  return n.toFixed(2);
}

// ========== 配平算法工具 ==========

function gcd(a, b) {
  a = Math.abs(Math.round(a)); b = Math.abs(Math.round(b));
  while (b) { [a, b] = [b, a % b]; }
  return a || 1;
}

function lcm(a, b) {
  return Math.abs(a * b) / gcd(a, b);
}

/**
 * 找到最小分母 d，使 d * x 近似为整数
 * 返回 0 表示找不到（超过 maxDen）
 */
function findDenominator(x, maxDen = 10000) {
  if (Math.abs(x - Math.round(x)) < 1e-9) return 1;
  for (let d = 2; d <= maxDen; d++) {
    if (Math.abs(d * x - Math.round(d * x)) < 1e-6) {
      return d;
    }
  }
  return 0;
}

// ========== 渲染：分类列表 ==========

function renderCategories() {
  const container = document.getElementById("catList");
  let html = "";

  // "全部" 选项
  html += `<div class="cat-item ${state.activeCategory === "all" ? "active" : ""}" data-cat="all">
    <span class="cat-icon">📋</span>
    <span class="cat-name">全部产物</span>
    <span class="cat-count">${RECIPES.length}</span>
  </div>`;

  CATEGORIES.forEach(cat => {
    const count = cat.id === "raw" ? RAW_RESOURCES.length : RECIPES.filter(r => r.category === cat.id).length;
    if (count === 0) return;
    html += `<div class="cat-item ${state.activeCategory === cat.id ? "active" : ""}" data-cat="${cat.id}">
      <span class="cat-icon">${cat.icon}</span>
      <span class="cat-name">${cat.name}</span>
      <span class="cat-count">${count}</span>
    </div>`;
  });

  container.innerHTML = html;

  container.querySelectorAll(".cat-item").forEach(el => {
    el.addEventListener("click", () => {
      state.activeCategory = el.dataset.cat;
      renderCategories();
      renderContent();
    });
  });
}

// ========== 渲染：产物卡片 ==========

function renderProductCard(recipe) {
  if (recipe.isRaw) {
    return `<div class="product-card raw-card">
      <div class="card-header">
        <span class="card-name">${recipe.name}</span>
        <span class="card-time">采集</span>
      </div>
      <div class="card-footer">
        <span style="color:var(--accent-orange)">基础原料</span>
      </div>
    </div>`;
  }

  const inputsHtml = recipe.inputs.map(inp =>
    `<span class="recipe-input">${inp.item}<span class="qty">×${inp.qty}</span></span>`
  ).join('<span class="recipe-arrow">+</span>');

  const equipmentHtml = recipe.equipment.map(e =>
    `<span class="equipment-tag">${e}</span>`
  ).join("");

  const inPlan = state.plan.some(p => p.id === recipe.id);

  return `<div class="product-card" data-id="${recipe.id}">
    <button class="add-plan-btn ${inPlan ? "added" : ""}" data-id="${recipe.id}" title="加入生产计划">${inPlan ? "✓" : "+"}</button>
    <div class="card-header">
      <span class="card-name">${recipe.name}</span>
      <span class="card-time">${recipe.time}s</span>
    </div>
    <div class="card-recipe">
      ${inputsHtml}
      <span class="recipe-arrow">→</span>
      <span class="recipe-output">${recipe.name} ×${recipe.output}</span>
    </div>
    <div class="card-footer">
      <div class="card-equipment">${equipmentHtml}</div>
      <span>${recipe.unlock}</span>
    </div>
  </div>`;
}

// ========== 渲染：浏览模式 ==========

function renderBrowseMode() {
  const container = document.getElementById("mainContent");

  // 搜索模式
  if (state.searchQuery) {
    const q = state.searchQuery.toLowerCase();
    const matched = RECIPES.filter(r =>
      r.name.toLowerCase().includes(q) ||
      r.inputs.some(i => i.item.toLowerCase().includes(q)) ||
      r.unlock.toLowerCase().includes(q)
    );
    const matchedRaw = RAW_RESOURCES.filter(r => r.name.toLowerCase().includes(q));

    if (matched.length === 0 && matchedRaw.length === 0) {
      container.innerHTML = `<div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>未找到匹配"${state.searchQuery}"的产物</p>
      </div>`;
      return;
    }

    let html = `<div class="section-title">
      <span class="section-icon">🔍</span>
      搜索结果（${matched.length + matchedRaw.length}）
    </div>`;

    if (matchedRaw.length > 0) {
      html += `<div class="section-title" style="font-size:14px;">
        <span class="section-icon">⛏</span>基础原料
        <span class="section-desc">${matchedRaw.length} 项</span>
      </div><div class="product-grid">`;
      matchedRaw.forEach(r => { html += renderProductCard(r); });
      html += "</div>";
    }

    if (matched.length > 0) {
      html += `<div class="section-title" style="font-size:14px;">
        <span class="section-icon">📦</span>产物
        <span class="section-desc">${matched.length} 项</span>
      </div><div class="product-grid">`;
      matched.forEach(r => { html += renderProductCard(r); });
      html += "</div>";
    }

    container.innerHTML = html;
    attachCardEvents();
    return;
  }

  // 分类浏览
  if (state.activeCategory === "all") {
    let html = `<div class="welcome-hint" style="padding:30px 20px;">
      <h2>江城创业记产线计算器</h2>
      <p>共收录 ${RECIPES.length} 个产物配方 + ${RAW_RESOURCES.length} 种基础原料，数据来自BWiki</p>
      <div class="hint-steps">
        <div class="hint-step">
          <div class="step-num">1</div>
          <div class="step-text">左侧选择分类，浏览产物配方</div>
        </div>
        <div class="hint-step">
          <div class="step-num">2</div>
          <div class="step-text">点击产物卡片右上角 + 加入生产计划</div>
        </div>
        <div class="hint-step">
          <div class="step-num">3</div>
          <div class="step-text">设置需求量和生产周期，点击计算</div>
        </div>
        <div class="hint-step">
          <div class="step-num">4</div>
          <div class="step-text">查看所需机器、原料和产线树</div>
        </div>
      </div>
    </div>`;

    CATEGORIES.forEach(cat => {
      const items = cat.id === "raw" ? RAW_RESOURCES : RECIPES.filter(r => r.category === cat.id);
      if (items.length === 0) return;
      html += `<div class="section-title">
        <span class="section-icon">${cat.icon}</span>
        ${cat.name}
        <span class="section-desc">${cat.desc}（${items.length} 项）</span>
      </div><div class="product-grid">`;
      items.forEach(r => { html += renderProductCard(r); });
      html += "</div>";
    });

    container.innerHTML = html;
    attachCardEvents();
    return;
  }

  // 单个分类
  const cat = CATEGORIES.find(c => c.id === state.activeCategory);
  if (!cat) return;

  const items = cat.id === "raw" ? RAW_RESOURCES : RECIPES.filter(r => r.category === cat.id);
  let html = `<div class="section-title">
    <span class="section-icon">${cat.icon}</span>
    ${cat.name}
    <span class="section-desc">${cat.desc}（${items.length} 项）</span>
  </div>`;

  if (items.length === 0) {
    html += `<div class="empty-state"><div class="empty-icon">📦</div><p>该分类暂无产物</p></div>`;
  } else {
    html += '<div class="product-grid">';
    items.forEach(r => { html += renderProductCard(r); });
    html += '</div>';
  }

  container.innerHTML = html;
  attachCardEvents();
}

// ========== 卡片事件绑定 ==========

function attachCardEvents() {
  document.querySelectorAll(".add-plan-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = btn.dataset.id;
      togglePlanItem(id);
      renderProductCardsUpdate();
      renderPlan();
    });
  });
}

function renderProductCardsUpdate() {
  document.querySelectorAll(".add-plan-btn").forEach(btn => {
    const id = btn.dataset.id;
    const inPlan = state.plan.some(p => p.id === id);
    btn.classList.toggle("added", inPlan);
    btn.textContent = inPlan ? "✓" : "+";
  });
}

// ========== 生产计划管理 ==========

function togglePlanItem(id) {
  const idx = state.plan.findIndex(p => p.id === id);
  if (idx >= 0) {
    state.plan.splice(idx, 1);
    delete state.machineChoices[id];
  } else {
    state.plan.push({ id, qty: 10 });
  }
  updatePlanCount();
}

function removeFromPlan(id) {
  state.plan = state.plan.filter(p => p.id !== id);
  delete state.machineChoices[id];
  renderPlan();
  renderProductCardsUpdate();
  updatePlanCount();
}

function updatePlanCount() {
  document.getElementById("planCount").textContent = `${state.plan.length} 项`;
}

function renderPlan() {
  const container = document.getElementById("planList");
  if (state.plan.length === 0) {
    container.innerHTML = `<div style="font-size:12px;color:var(--text-muted);padding:8px 0;">点击产物卡片 + 添加</div>`;
    return;
  }

  let html = "";
  state.plan.forEach(p => {
    const item = ALL_ITEMS[p.id];
    if (!item) return;
    html += `<div class="plan-item">
      <span class="plan-item-name" data-id="${p.id}">${item.name}</span>
      <input type="number" value="${p.qty}" min="0" data-id="${p.id}" class="plan-qty-input" />
      <button class="remove-btn" data-id="${p.id}" title="移除">✕</button>
    </div>`;
  });
  container.innerHTML = html;

  container.querySelectorAll(".plan-qty-input").forEach(inp => {
    inp.addEventListener("change", (e) => {
      const id = e.target.dataset.id;
      const qty = Math.max(0, parseInt(e.target.value) || 0);
      const p = state.plan.find(p => p.id === id);
      if (p) p.qty = qty;
    });
  });

  container.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", () => removeFromPlan(btn.dataset.id));
  });

  container.querySelectorAll(".plan-item-name").forEach(el => {
    el.addEventListener("click", () => {
      const id = el.dataset.id;
      const recipe = ALL_ITEMS[id];
      if (recipe && recipe.category) {
        state.activeCategory = recipe.category;
        state.searchQuery = "";
        document.getElementById("searchInput").value = "";
        renderCategories();
        renderContent();
      }
    });
  });
}

// ========== 计算器核心逻辑 ==========

/**
 * 递归计算生产需求
 * @param {string} productId - 产物ID
 * @param {number} quantity - 需求数量
 * @param {number} timePeriod - 生产周期（秒）
 * @param {Map} aggregate - 汇总表 { id: { totalQty, recipe, machine, machineCount, power, children } }
 * @param {Set} visited - 防循环
 * @param {number} depth - 递归深度
 * @returns {object} 节点信息
 */
function calculateNode(productId, quantity, timePeriod, aggregate, visited = new Set(), depth = 0) {
  const recipe = ALL_ITEMS[productId];

  // 基础原料 - 叶节点
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

  // 累加需求量
  if (!aggregate.has(productId)) {
    const machine = getMachineForProduct(productId);
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
    // 重新计算机器数
    const craftsNeeded = existing.totalQty / recipe.output;
    const craftsPerMachine = timePeriod / recipe.time;
    existing.machineCount = craftsNeeded / craftsPerMachine;
    existing.power = existing.machineCount * (MACHINE_POWER[existing.machine] || 0);
  }

  // 递归计算子材料
  const node = {
    id: productId,
    name: recipe.name,
    qty: quantity,
    isRaw: false,
    machine: aggregate.get(productId).machine,
    machineCount: aggregate.get(productId).machineCount,
    children: [],
  };

  // 防循环
  if (visited.has(productId)) return node;
  const newVisited = new Set(visited);
  newVisited.add(productId);

  const craftsNeeded = quantity / recipe.output;
  recipe.inputs.forEach(inp => {
    const childQty = craftsNeeded * inp.qty;
    const childNode = calculateNode(inp.item, childQty, timePeriod, aggregate, newVisited, depth + 1);
    node.children.push(childNode);
  });

  return node;
}

/**
 * 执行完整计算（自动配平版）
 * 第一遍：用原始需求算出小数机器台数
 * 第二遍：求配平倍率 M，需求×M 重算，机器台数自然变整数
 */
function runCalculation() {
  if (state.plan.length === 0) return null;

  const timePeriod = getTimePeriodSeconds();
  const beltRate = getBeltRate();
  const beltLevel = getBeltLevel();

  // === 第一遍：原始需求计算，收集小数机器台数 ===
  const agg1 = new Map();
  state.plan.forEach(p => {
    calculateNode(p.id, p.qty, timePeriod, agg1);
  });

  // 求配平倍率 M = 所有机器台数分母的 LCM
  let scaleM = 1;
  let scaleWarning = false;
  agg1.forEach(item => {
    if (!item.isRaw && item.machineCount > 0) {
      const den = findDenominator(item.machineCount);
      if (den > 0) {
        scaleM = lcm(scaleM, den);
      } else {
        scaleWarning = true;
      }
    }
  });

  // 防止倍率爆炸
  if (scaleM > 10000) {
    scaleM = 1;
    scaleWarning = true;
  }

  // === 第二遍：用 ×M 的需求重新计算 ===
  const aggregate = new Map();
  const trees = [];
  const scaledPlan = state.plan.map(p => ({ id: p.id, qty: p.qty * scaleM }));

  scaledPlan.forEach(p => {
    const tree = calculateNode(p.id, p.qty, timePeriod, aggregate);
    trees.push({ target: p, tree: tree });
  });

  // 处理结果
  const machines = [];
  const materials = [];
  let totalPower = 0;
  let totalMachines = 0;
  let totalBelts = 0;

  aggregate.forEach(item => {
    item.flowRate = item.totalQty / timePeriod;
    item.belts = Math.ceil(item.flowRate / beltRate);
    item.beltRate = beltRate;
    totalBelts += item.belts;

    if (item.isRaw) {
      materials.push(item);
    } else {
      // 配平后应该是整数，用 round 清理浮点误差
      const rounded = Math.round(item.machineCount);
      if (Math.abs(item.machineCount - rounded) > 0.01) {
        // 配平失败的情况，保留小数
        item.machineCountExact = item.machineCount;
      } else {
        item.machineCount = rounded;
      }
      item.power = item.machineCount * (MACHINE_POWER[item.machine] || 0);
      machines.push(item);
      totalPower += item.power;
      totalMachines += item.machineCount;
    }
  });

  machines.sort((a, b) => b.machineCount - a.machineCount);
  materials.sort((a, b) => b.totalQty - a.totalQty);

  return {
    timePeriod,
    beltLevel,
    beltRate,
    scaleM,
    scaleWarning,
    trees,
    machines,
    materials,
    totalPower,
    totalMachines,
    totalBelts,
    planItems: state.plan.map(p => ({
      ...p,
      name: ALL_ITEMS[p.id]?.name || p.id,
      scaledQty: p.qty * scaleM,
    })),
  };
}

// ========== 渲染：计算模式 ==========

function renderCalcMode() {
  const container = document.getElementById("mainContent");

  if (state.plan.length === 0) {
    container.innerHTML = `<div class="empty-state">
      <div class="empty-icon">📋</div>
      <p>生产计划为空，请先在浏览模式中添加产物</p>
    </div>`;
    return;
  }

  const result = runCalculation();
  if (!result) return;
  state.calcResult = result;
  state._currentTimePeriod = result.timePeriod;

  let html = '<div class="calc-results">';

  // === 汇总卡片 ===
  html += '<div class="calc-summary">';
  html += `<div class="summary-card ${result.scaleM > 1 ? "highlight" : ""}">
    <div class="summary-label">配平倍率</div>
    <div class="summary-value" style="color:var(--accent-orange)">×${result.scaleM}</div>
  </div>`;
  html += `<div class="summary-card">
    <div class="summary-label">目标产物</div>
    <div class="summary-value products">${result.planItems.length}<span class="summary-unit">种</span></div>
  </div>`;
  html += `<div class="summary-card">
    <div class="summary-label">生产机器总数</div>
    <div class="summary-value machines">${fmtNum(result.totalMachines)}<span class="summary-unit">台</span></div>
  </div>`;
  html += `<div class="summary-card">
    <div class="summary-label">总功耗</div>
    <div class="summary-value power">${fmtNum(result.totalPower)}<span class="summary-unit">kW/s</span></div>
  </div>`;
  html += `<div class="summary-card">
    <div class="summary-label">基础原料种类</div>
    <div class="summary-value materials">${result.materials.length}<span class="summary-unit">种</span></div>
  </div>`;
  html += `<div class="summary-card">
    <div class="summary-label">传送带总数</div>
    <div class="summary-value belts">${fmtNum(result.totalBelts)}<span class="summary-unit">条</span></div>
  </div>`;
  html += `<div class="summary-card">
    <div class="summary-label">生产周期</div>
    <div class="summary-value" style="color:var(--accent-cyan)">${fmtNum(result.timePeriod)}<span class="summary-unit">秒</span></div>
  </div>`;
  html += '</div>';

  // 配平说明
  if (result.scaleM > 1) {
    html += `<div class="balance-info">
      <span class="balance-icon">⚖</span>
      <span>已自动配平：需求量 ×${result.scaleM}，所有机器台数为整数，无空转浪费。多余产出 = 原需求的 ${result.scaleM - 1} 倍。</span>
    </div>`;
  }
  if (result.scaleWarning) {
    html += `<div class="balance-info warning">
      <span class="balance-icon">⚠</span>
      <span>部分产物配平倍率过大（>10000），这些产物保留小数机器台数。</span>
    </div>`;
  }

  // === 目标产物列表 ===
  html += `<div class="machines-table">
    <div class="table-header">
      <h3>🎯 目标产物</h3>
      ${result.scaleM > 1 ? `<span style="font-size:12px;color:var(--accent-orange)">配平倍率 ×${result.scaleM}</span>` : ""}
    </div>
    <table>
      <thead><tr><th>产物名称</th><th>原始需求</th><th>配平需求</th><th>配方</th><th>单次产出</th><th>制作时间</th></tr></thead>
      <tbody>`;
  result.planItems.forEach(p => {
    const recipe = ALL_ITEMS[p.id];
    const inputsStr = recipe.inputs.map(i => `${i.item}×${i.qty}`).join(" + ");
    html += `<tr>
      <td><strong>${p.name}</strong></td>
      <td style="color:var(--text-secondary)">${p.qty}</td>
      <td style="color:var(--accent-green);font-weight:600">${p.scaledQty}</td>
      <td style="font-size:12px;color:var(--text-secondary)">${inputsStr}</td>
      <td>${recipe.output}</td>
      <td>${recipe.time}s</td>
    </tr>`;
  });
  html += '</tbody></table></div>';

  // === 机器汇总表 ===
  html += `<div class="machines-table">
    <div class="table-header">
      <h3>⚙ 机器需求明细</h3>
      <span class="power-total">总功耗 ${fmtNum(result.totalPower)} kW/s · 传送带 ${fmtNum(result.totalBelts)} 条 (${result.beltLevel}级/${result.beltRate}个/秒)</span>
    </div>
    <table>
      <thead><tr>
        <th>产物</th><th>使用机器</th><th>配平需求</th><th>流量(个/秒)</th><th>传送带</th><th>机器台数</th><th>单台功耗</th><th>小计功耗</th>
      </tr></thead>
      <tbody>`;
  result.machines.forEach(m => {
    const powerPerMachine = MACHINE_POWER[m.machine] || 0;
    const html_options = m.recipe.equipment.map(e =>
      `<option value="${e}" ${e === m.machine ? "selected" : ""}>${e}${MACHINE_POWER[e] > 0 ? ` (${MACHINE_POWER[e]}kW)` : ""}</option>`
    ).join("");
    // 配平后机器台数为整数；极少数配平失败的保留小数
    const mcDisplay = m.machineCountExact !== undefined
      ? `<span style="color:var(--accent-orange)" title="配平失败，保留小数">${m.machineCountExact.toFixed(2)}</span>`
      : `<span style="color:var(--accent-blue);font-weight:700;font-size:15px">${m.machineCount}</span>`;
    html += `<tr>
      <td><strong>${m.name}</strong></td>
      <td><select class="machine-select" data-id="${m.id}">${html_options}</select></td>
      <td style="color:var(--accent-green)">${fmtQty(m.totalQty)}</td>
      <td style="color:var(--accent-cyan)">${m.flowRate.toFixed(2)}</td>
      <td style="color:var(--accent-purple);font-weight:600">${m.belts}<span style="font-size:10px;color:var(--text-muted)"> 条</span></td>
      <td>${mcDisplay}</td>
      <td>${powerPerMachine} kW/s</td>
      <td style="color:var(--accent-yellow)">${fmtNum(m.power)} kW/s</td>
    </tr>`;
  });
  html += '</tbody></table></div>';

  // === 基础原料汇总 ===
  if (result.materials.length > 0) {
    html += `<div class="materials-list">
      <div class="table-header">
        <h3>⛏ 基础原料消耗</h3>
        <span style="font-size:12px;color:var(--text-muted)">需采集的原始资源 · 传送带 ${result.materials.reduce((s,m)=>s+m.belts,0)} 条</span>
      </div>
      <div class="mat-grid">`;
    result.materials.forEach(m => {
      html += `<div class="mat-item">
        <div class="mat-info">
          <span class="mat-name">${m.name}</span>
          <span class="mat-qty">${fmtQty(m.totalQty)}</span>
        </div>
        <div class="mat-belt">
          <span class="mat-flow">${m.flowRate.toFixed(2)}/s</span>
          <span class="mat-belts">${m.belts}条</span>
        </div>
      </div>`;
    });
    html += '</div></div>';
  }

  // === 产线树 ===
  html += '<div class="tree-container"><h3>🌲 产线依赖树</h3>';
  result.trees.forEach(t => {
    html += renderTreeNode(t.tree, true, 0, result.beltRate);
  });
  html += '</div>';

  html += '</div>'; // calc-results

  container.innerHTML = html;

  // 绑定机器选择事件
  container.querySelectorAll(".machine-select").forEach(sel => {
    sel.addEventListener("change", (e) => {
      const id = e.target.dataset.id;
      state.machineChoices[id] = e.target.value;
      renderCalcMode();
    });
  });

  // 绑定树展开/收起
  container.querySelectorAll(".node-toggle").forEach(toggle => {
    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      const node = toggle.closest(".tree-node");
      node.classList.toggle("collapsed");
      toggle.textContent = node.classList.contains("collapsed") ? "▶" : "▼";
    });
  });
}

// ========== 渲染：产线树节点 ==========

function renderTreeNode(node, isRoot, depth, beltRate) {
  const item = ALL_ITEMS[node.id];
  const isRaw = node.isRaw || (item && item.isRaw);

  // 计算该节点的传送带需求
  const flowRate = node.qty / state._currentTimePeriod;
  const belts = Math.ceil(flowRate / beltRate);

  let infoStr = "";
  if (!isRaw && node.machineCount !== undefined) {
    const mc = Math.round(node.machineCount);
    infoStr = `<span class="node-machine">${node.machine} ×${mc}</span>`;
  }
  // 传送带信息（所有非根节点都需要传送带运输）
  const beltStr = (!isRoot && belts > 0)
    ? `<span class="node-belt">🔗 ${belts}条</span>`
    : "";

  const toggleStr = (!isRaw && node.children && node.children.length > 0)
    ? `<span class="node-toggle">▼</span>`
    : `<span class="node-toggle"></span>`;

  let html = `<div class="tree-node ${depth === 0 ? "" : ""}">`;
  html += `<div class="node-content">
    ${toggleStr}
    <span class="node-name ${isRaw ? "raw" : ""}">${node.name}</span>
    <span class="node-qty">×${fmtQty(node.qty)}</span>
    ${infoStr}
    ${beltStr}
  </div>`;

  if (node.children && node.children.length > 0) {
    html += '<div class="tree-children expanded">';
    node.children.forEach(child => {
      html += renderTreeNode(child, false, depth + 1, beltRate);
    });
    html += '</div>';
  }

  html += '</div>';
  return html;
}

// ========== 渲染：主内容区 ==========

function renderContent() {
  if (state.mode === "calc") {
    renderCalcMode();
  } else {
    renderBrowseMode();
  }
}

// ========== 事件绑定 ==========

function initEvents() {
  // 搜索
  document.getElementById("searchInput").addEventListener("input", (e) => {
    state.searchQuery = e.target.value.trim();
    if (state.mode !== "browse") {
      state.mode = "browse";
      document.getElementById("btnBrowse").classList.add("active");
      document.getElementById("btnCalc").classList.remove("active");
    }
    renderContent();
  });

  // 时间周期
  document.getElementById("timePeriod").addEventListener("input", () => {
    if (state.mode === "calc") renderCalcMode();
  });
  document.getElementById("timeUnit").addEventListener("change", () => {
    if (state.mode === "calc") renderCalcMode();
  });

  // 传送带等级
  document.getElementById("beltLevel").addEventListener("change", () => {
    state.beltLevel = parseInt(document.getElementById("beltLevel").value) || 2;
    if (state.mode === "calc") renderCalcMode();
  });

  // 模式切换
  document.getElementById("btnBrowse").addEventListener("click", () => {
    state.mode = "browse";
    document.getElementById("btnBrowse").classList.add("active");
    document.getElementById("btnCalc").classList.remove("active");
    renderContent();
  });

  document.getElementById("btnCalc").addEventListener("click", () => {
    state.mode = "calc";
    document.getElementById("btnCalc").classList.add("active");
    document.getElementById("btnBrowse").classList.remove("active");
    renderContent();
  });

  // 计算按钮
  document.getElementById("btnDoCalc").addEventListener("click", () => {
    if (state.plan.length === 0) {
      alert("请先添加产物到生产计划");
      return;
    }
    state.mode = "calc";
    document.getElementById("btnCalc").classList.add("active");
    document.getElementById("btnBrowse").classList.remove("active");
    renderContent();
  });

  // 清空计划
  document.getElementById("btnClearPlan").addEventListener("click", () => {
    if (state.plan.length === 0) return;
    if (confirm("确认清空生产计划？")) {
      state.plan = [];
      state.machineChoices = {};
      renderPlan();
      renderProductCardsUpdate();
      updatePlanCount();
      if (state.mode === "calc") renderContent();
    }
  });
}

// ========== 初始化 ==========

function init() {
  renderCategories();
  renderPlan();
  renderContent();
  initEvents();
}

document.addEventListener("DOMContentLoaded", init);
