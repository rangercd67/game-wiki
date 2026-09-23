/* 前端同时服务两种运行形态：
 * - server：本地 HTTP 服务，数据来自 /api/*，预览是运行时按需读取；
 * - static：构建产物（GitHub Pages 等纯静态托管），数据来自 data/library.json，
 *   预览是构建时预生成的 JSON / 图片。
 * 两者对外接口一致，页面逻辑只依赖 source 抽象，不感知形态差异。
 */
const state = { q: "", game: "", kind: "", page: 1, limit: 40, total: 0 };
const kindNames = { document: "文档", image: "图片", data: "数据", archive: "压缩包", binary: "程序/二进制" };
let fileIndex = new Map();

const $ = (selector) => document.querySelector(selector);
const formatNumber = (value) => new Intl.NumberFormat("zh-CN").format(Number(value || 0));
const formatBytes = (value) => {
  let size = Number(value || 0);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size.toFixed(unit ? 1 : 0)} ${units[unit]}`;
};
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);

// SQLite 的 LIKE 只对 ASCII 做大小写折叠，这里用同样的规则，
// 避免静态版与本地服务版的检索结果出现差异（例如中文大小写折叠）。
const asciiFold = (value) => String(value).replace(/[A-Z]/g, (char) => char.toLowerCase());

const STATIC_MODE = document.documentElement.dataset.wikiMode === "static";

async function fetchJson(path) {
  const response = await fetch(path);
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : response;
  if (!response.ok) throw new Error((payload && payload.error) || `请求失败 (${response.status})`);
  return payload;
}

const serverSource = {
  async overview() {
    const [stats, games] = await Promise.all([fetchJson("/api/stats"), fetchJson("/api/games")]);
    return { metadata: stats.metadata, kinds: stats.kinds, games: games.games };
  },
  async list({ q, game, kind, page, limit }) {
    const params = new URLSearchParams({ page, limit });
    if (q) params.set("q", q);
    if (game) params.set("game", game);
    if (kind) params.set("kind", kind);
    return fetchJson(`/api/files?${params}`);
  },
  previewUrl(file) {
    return `/api/preview?path=${encodeURIComponent(file.relative_path)}`;
  },
  async previewText(file) {
    const data = await fetchJson(this.previewUrl(file));
    return data.content;
  },
};

const staticSource = {
  library: null,
  async load() {
    if (!this.library) this.library = await fetchJson("./data/library.json");
    return this.library;
  },
  async overview() {
    const library = await this.load();
    return { metadata: library.metadata, kinds: library.kinds, games: library.games };
  },
  async list({ q, game, kind, page, limit }) {
    const library = await this.load();
    const keyword = asciiFold(q || "");
    // library.files 在构建时已按 (modified_ns DESC, name NOCASE) 排好序。
    // 这里刻意不重排：modified_ns 是纳秒整数，超出 JS 安全整数范围，
    // JSON 解析会丢失低位精度，重排反而可能打乱构建时确定的顺序。
    // 同理，过滤不改变相对顺序，因此分页结果与本地服务一致。
    const matched = library.files.filter((file) => {
      if (game && file.game !== game) return false;
      if (kind && file.kind !== kind) return false;
      if (!keyword) return true;
      return asciiFold(file.name).includes(keyword)
        || asciiFold(file.relative_path).includes(keyword);
    });
    const offset = (page - 1) * limit;
    return {
      files: matched.slice(offset, offset + limit),
      total: matched.length,
      page,
      limit,
    };
  },
  previewUrl(file) {
    return file.url ? new URL(file.url, document.baseURI).href : "";
  },
  async previewText(file) {
    if (!file.preview_key) throw new Error(file.preview_note || "此文件未在站点中发布正文");
    const data = await fetchJson(`./data/preview/${file.preview_key}.json`);
    return data.content;
  },
};

const source = STATIC_MODE ? staticSource : serverSource;

function applyModeCopy() {
  const mode = STATIC_MODE ? "static" : "server";
  document.querySelectorAll("[data-server]").forEach((element) => {
    element.textContent = element.dataset[mode];
  });
}

function applyTheme(theme) {
  const isDark = theme === "dark";
  document.documentElement.dataset.theme = isDark ? "dark" : "light";
  $("#themeToggle").setAttribute("aria-pressed", String(isDark));
  $("#themeToggle").setAttribute("aria-label", isDark ? "切换为浅色主题" : "切换为深色主题");
  $(".theme-label").textContent = isDark ? "浅色" : "深色";
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("wiki-theme", next);
  applyTheme(next);
}

async function loadOverview() {
  try {
    const { metadata, kinds, games } = await source.overview();
    $("#stats").innerHTML = `<span><b>${formatNumber(metadata.indexed)}</b>份资料</span><span><b>${formatBytes(metadata.total_bytes)}</b>索引体量</span><span><b>${games.length}</b>个分类</span>`;
    $("#allCount").textContent = formatNumber(metadata.indexed);
    $("#gameList").innerHTML = games.map((item) => `<button class="filter" data-game="${escapeHtml(item.game)}"><span>${escapeHtml(item.game)}</span><b>${formatNumber(item.count)}</b></button>`).join("");
    $("#gameCards").innerHTML = games.slice(0, 8).map((item, index) => `<button class="game-card" data-game="${escapeHtml(item.game)}">
      <span class="game-card-index">0${index + 1}</span>
      <strong>${escapeHtml(item.game)}</strong>
      <small>${formatNumber(item.count)} FILES</small>
      <i aria-hidden="true">↗</i>
    </button>`).join("");
    $("#kinds").innerHTML = `<button class="kind active" data-kind="">全部</button>${kinds.map((item) => `<button class="kind" data-kind="${item.kind}">${kindNames[item.kind] || item.kind} · ${formatNumber(item.count)}</button>`).join("")}`;
  } catch (error) {
    $("#stats").innerHTML = `<span class="error">${escapeHtml(error.message)}</span>`;
  }
}

async function loadFiles() {
  $("#fileList").innerHTML = `<div class="empty">正在查找馆藏…</div>`;
  try {
    const data = await source.list({
      q: state.q, game: state.game, kind: state.kind, page: state.page, limit: state.limit,
    });
    state.total = data.total;
    fileIndex = new Map();
    $("#resultCount").textContent = `${formatNumber(data.total)} 项结果`;
    $("#resultKicker").textContent = state.game || (state.q ? `搜索 · ${state.q}` : "全部馆藏");
    $("#resultTitle").textContent = state.kind ? kindNames[state.kind] : (state.q ? "检索结果" : "最新资料");
    $("#fileList").innerHTML = data.files.length ? data.files.map(fileRow).join("") : `<div class="empty">没有找到匹配的资料。</div>`;
    const pages = Math.max(1, Math.ceil(data.total / data.limit));
    $("#pageInfo").textContent = `${data.page} / ${pages}`;
    $("#prevPage").disabled = data.page <= 1;
    $("#nextPage").disabled = data.page >= pages;
  } catch (error) {
    $("#fileList").innerHTML = `<div class="empty error">${escapeHtml(error.message)}</div>`;
    $("#resultCount").textContent = "无法读取索引";
  }
}

function fileRow(file) {
  const canPreview = Boolean(file.preview);
  const modified = new Date(file.modified_at).toLocaleDateString("zh-CN");
  // 不可预览时说明原因（静态站点会在构建时记录 preview_note），
  // 避免公开站点上出现「点了没反应」或「静默少内容」的困惑。
  const note = canPreview ? "" : (file.preview_note || "此类型不提供内容预览");
  fileIndex.set(file.relative_path, file);
  return `<article class="file-row">
    <div class="file-card-top"><div class="file-icon">${escapeHtml((file.extension || "file").slice(1, 5))}</div><span>${escapeHtml(kindNames[file.kind] || file.kind)}</span></div>
    <div class="file-main"><strong title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</strong><small>${escapeHtml(file.game)}</small><p title="${escapeHtml(file.relative_path)}">${escapeHtml(file.relative_path)}</p></div>
    <div class="file-meta"><span>${formatBytes(file.size)}</span><span>${modified}</span></div>
    <button class="preview-btn" data-path="${escapeHtml(file.relative_path)}" title="${escapeHtml(note)}" ${canPreview ? "" : "disabled"}>${canPreview ? "预览" : "仅元数据"}</button>
  </article>`;
}

async function openPreview(file) {
  if (!file) return;
  const dialog = $("#previewDialog");
  $("#previewTitle").textContent = file.name;
  $("#previewBody").innerHTML = `<div class="empty">正在按需读取单个文件…</div>`;
  dialog.showModal();
  try {
    if (file.preview === "image") {
      const url = source.previewUrl(file);
      if (!url) throw new Error(file.preview_note || "此图片未在站点中发布");
      const image = new Image();
      image.alt = file.name;
      image.src = url;
      image.onerror = () => { $("#previewBody").innerHTML = `<p class="error">图片预览失败。</p>`; };
      $("#previewBody").replaceChildren(image);
    } else {
      const content = await source.previewText(file);
      const pre = document.createElement("pre");
      pre.textContent = content;
      $("#previewBody").replaceChildren(pre);
    }
  } catch (error) {
    $("#previewBody").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
}

document.addEventListener("click", (event) => {
  const game = event.target.closest("[data-game]");
  if (game) {
    document.querySelectorAll("[data-game]").forEach((el) => el.classList.remove("active"));
    game.classList.add("active"); state.game = game.dataset.game; state.page = 1; loadFiles();
    if (game.classList.contains("game-card")) $("#archive").scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const kind = event.target.closest("[data-kind]");
  if (kind) {
    document.querySelectorAll("[data-kind]").forEach((el) => el.classList.remove("active"));
    kind.classList.add("active"); state.kind = kind.dataset.kind; state.page = 1; loadFiles();
  }
  const preview = event.target.closest(".preview-btn:not(:disabled)");
  if (preview) openPreview(fileIndex.get(preview.dataset.path));
});

$("#searchForm").addEventListener("submit", (event) => { event.preventDefault(); state.q = $("#searchInput").value.trim(); state.page = 1; loadFiles(); });
$("#prevPage").addEventListener("click", () => { state.page -= 1; loadFiles(); window.scrollTo({ top: $(".workspace").offsetTop, behavior: "smooth" }); });
$("#nextPage").addEventListener("click", () => { state.page += 1; loadFiles(); window.scrollTo({ top: $(".workspace").offsetTop, behavior: "smooth" }); });
$("#closePreview").addEventListener("click", () => $("#previewDialog").close());
$("#previewDialog").addEventListener("close", () => $("#previewBody").replaceChildren());
$("#themeToggle").addEventListener("click", toggleTheme);

applyModeCopy();
applyTheme(document.documentElement.dataset.theme);
loadOverview().then(loadFiles);
