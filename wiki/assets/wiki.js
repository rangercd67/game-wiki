/* wiki 前端交互：主题、移动端导航、图片灯箱、大表格过滤、站内搜索。
 * 站点是纯静态的（GitHub Pages 不能跑服务端），因此搜索在浏览器里完成：
 * 构建时产出 search.json，这里只做加载、匹配与高亮。 */

const PREFIX = document.documentElement.dataset.prefix || "./";
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

/* ---------- 主题 ---------- */

function applyTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  const toggle = $("#themeToggle");
  toggle.setAttribute("aria-pressed", String(dark));
  toggle.setAttribute("aria-label", dark ? "切换为浅色主题" : "切换为深色主题");
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("wiki-theme", next);
  applyTheme(next);
}

/* ---------- 移动端导航 ---------- */

function setupSidebar() {
  const sidebar = $("#sidebar");
  const toggle = $("#navToggle");
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  // 点走链接后自动收起，否则手机上会挡住目标页面
  sidebar.addEventListener("click", (event) => {
    if (event.target.closest("a")) {
      sidebar.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    }
  });
}

/* ---------- 图片灯箱 ---------- */

function setupLightbox() {
  const dialog = document.createElement("dialog");
  dialog.className = "lightbox";
  dialog.innerHTML = '<button class="lightbox-close" type="button" aria-label="关闭">×</button><img alt="">';
  document.body.append(dialog);

  const image = dialog.querySelector("img");
  dialog.querySelector(".lightbox-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  $$(".prose img").forEach((thumbnail) => {
    thumbnail.addEventListener("click", () => {
      image.src = thumbnail.src;
      image.alt = thumbnail.alt;
      dialog.showModal();
    });
  });
}

/* ---------- 大表格：横向滚动容器 + 过滤框 ---------- */

const TABLE_FILTER_THRESHOLD = 12;

function setupTables() {
  $$(".prose table").forEach((table) => {
    const wrapper = document.createElement("div");
    wrapper.className = "table-scroll";
    table.replaceWith(wrapper);
    wrapper.append(table);

    const rows = table.querySelectorAll("tbody tr").length;
    if (rows < TABLE_FILTER_THRESHOLD) return;

    const tools = document.createElement("div");
    tools.className = "table-tools";
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = `在 ${rows} 行中筛选…`;
    const count = document.createElement("span");
    count.textContent = `${rows} 行`;
    tools.append(input, count);
    wrapper.before(tools);

    input.addEventListener("input", () => {
      const keyword = input.value.trim().toLowerCase();
      let visible = 0;
      table.querySelectorAll("tbody tr").forEach((row) => {
        const hit = !keyword || row.textContent.toLowerCase().includes(keyword);
        row.hidden = !hit;
        if (hit) visible += 1;
      });
      count.textContent = keyword ? `${visible} / ${rows} 行` : `${rows} 行`;
    });
  });
}

/* ---------- 站内搜索 ---------- */

const searchState = { index: null, hits: [], cursor: -1 };

async function loadSearchIndex() {
  if (searchState.index) return searchState.index;
  const response = await fetch(`${PREFIX}search.json`);
  if (!response.ok) throw new Error("搜索索引加载失败");
  searchState.index = await response.json();
  return searchState.index;
}

function highlight(text, keyword) {
  const escaped = text.replace(/[&<>"]/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]
  ));
  if (!keyword) return escaped;
  const pattern = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return escaped.replace(new RegExp(pattern, "gi"), (hit) => `<mark>${hit}</mark>`);
}

function renderHits(keyword) {
  const container = $("#searchResults");
  const index = searchState.index || [];
  const lowered = keyword.trim().toLowerCase();
  if (!lowered) {
    searchState.hits = index.slice(0, 12);
  } else {
    searchState.hits = index
      .map((page) => {
        const title = page.title.toLowerCase();
        const inTitle = title.includes(lowered);
        const inBody = page.text.toLowerCase().includes(lowered);
        return inTitle || inBody ? { page, score: inTitle ? 2 : 1 } : null;
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score)
      .slice(0, 30)
      .map((item) => item.page);
  }
  searchState.cursor = -1;

  if (!searchState.hits.length) {
    container.innerHTML = '<div class="search-empty">没有匹配的攻略页面。</div>';
    return;
  }
  container.innerHTML = searchState.hits.map((page) => {
    const summary = page.summary || page.text.slice(0, 70);
    return `<a class="search-hit" href="${PREFIX}${page.url.replace(/^\//, "")}">
      <strong>${highlight(page.title, keyword.trim())}</strong>
      <small>${highlight(summary, keyword.trim())}</small>
    </a>`;
  }).join("");
}

function moveCursor(step) {
  const hits = $$("#searchResults .search-hit");
  if (!hits.length) return;
  searchState.cursor = (searchState.cursor + step + hits.length) % hits.length;
  hits.forEach((hit, position) => hit.classList.toggle("active", position === searchState.cursor));
  hits[searchState.cursor].scrollIntoView({ block: "nearest" });
}

function setupSearch() {
  const dialog = $("#searchDialog");
  const input = $("#searchInput");

  const open = async () => {
    dialog.showModal();
    input.focus();
    input.select();
    try {
      await loadSearchIndex();
      renderHits(input.value);
    } catch (error) {
      $("#searchResults").innerHTML = `<div class="search-empty">${error.message}</div>`;
    }
  };

  $("#searchOpen").addEventListener("click", open);
  $("#searchClose").addEventListener("click", () => dialog.close());
  input.addEventListener("input", () => renderHits(input.value));
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") { event.preventDefault(); moveCursor(1); }
    if (event.key === "ArrowUp") { event.preventDefault(); moveCursor(-1); }
    if (event.key === "Enter" && searchState.cursor >= 0) {
      const hit = $$("#searchResults .search-hit")[searchState.cursor];
      if (hit) window.location.href = hit.getAttribute("href");
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (!dialog.open) open();
    }
  });
}

/* ---------- 启动 ---------- */

applyTheme(document.documentElement.dataset.theme);
setupSidebar();
setupLightbox();
setupTables();
setupSearch();
