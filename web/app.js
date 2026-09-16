const state = { q: "", game: "", kind: "", page: 1, limit: 40, total: 0 };
const previewableText = new Set([".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".jsonl", ".geojson", ".xml", ".yaml", ".yml", ".ini", ".cfg"]);
const previewableImages = new Set([".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]);
const kindNames = { document: "文档", image: "图片", data: "数据", archive: "压缩包", binary: "程序/二进制" };

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

async function api(path) {
  const response = await fetch(path);
  const type = response.headers.get("content-type") || "";
  const payload = type.includes("application/json") ? await response.json() : response;
  if (!response.ok) throw new Error(payload.error || `请求失败 (${response.status})`);
  return payload;
}

async function loadOverview() {
  try {
    const [stats, games] = await Promise.all([api("/api/stats"), api("/api/games")]);
    const meta = stats.metadata;
    $("#stats").innerHTML = `<span><b>${formatNumber(meta.indexed)}</b>份资料</span><span><b>${formatBytes(meta.total_bytes)}</b>索引体量</span><span><b>${games.games.length}</b>个分类</span>`;
    $("#allCount").textContent = formatNumber(meta.indexed);
    $("#gameList").innerHTML = games.games.map((item) => `<button class="filter" data-game="${escapeHtml(item.game)}"><span>${escapeHtml(item.game)}</span><b>${formatNumber(item.count)}</b></button>`).join("");
    $("#gameCards").innerHTML = games.games.slice(0, 8).map((item, index) => `<button class="game-card" data-game="${escapeHtml(item.game)}">
      <span class="game-card-index">0${index + 1}</span>
      <strong>${escapeHtml(item.game)}</strong>
      <small>${formatNumber(item.count)} FILES</small>
      <i aria-hidden="true">↗</i>
    </button>`).join("");
    $("#kinds").innerHTML = `<button class="kind active" data-kind="">全部</button>${stats.kinds.map((item) => `<button class="kind" data-kind="${item.kind}">${kindNames[item.kind] || item.kind} · ${formatNumber(item.count)}</button>`).join("")}`;
  } catch (error) {
    $("#stats").innerHTML = `<span class="error">${escapeHtml(error.message)}</span>`;
  }
}

async function loadFiles() {
  const params = new URLSearchParams({ page: state.page, limit: state.limit });
  if (state.q) params.set("q", state.q);
  if (state.game) params.set("game", state.game);
  if (state.kind) params.set("kind", state.kind);
  $("#fileList").innerHTML = `<div class="empty">正在查找馆藏…</div>`;
  try {
    const data = await api(`/api/files?${params}`);
    state.total = data.total;
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
  const canPreview = previewableText.has(file.extension) || previewableImages.has(file.extension);
  const modified = new Date(file.modified_at).toLocaleDateString("zh-CN");
  return `<article class="file-row">
    <div class="file-card-top"><div class="file-icon">${escapeHtml((file.extension || "file").slice(1, 5))}</div><span>${escapeHtml(kindNames[file.kind] || file.kind)}</span></div>
    <div class="file-main"><strong title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</strong><small>${escapeHtml(file.game)}</small><p title="${escapeHtml(file.relative_path)}">${escapeHtml(file.relative_path)}</p></div>
    <div class="file-meta"><span>${formatBytes(file.size)}</span><span>${modified}</span></div>
    <button class="preview-btn" data-path="${escapeHtml(file.relative_path)}" data-name="${escapeHtml(file.name)}" data-ext="${escapeHtml(file.extension)}" ${canPreview ? "" : "disabled"}>${canPreview ? "预览" : "仅元数据"}</button>
  </article>`;
}

async function openPreview(path, name, extension) {
  const dialog = $("#previewDialog");
  $("#previewTitle").textContent = name;
  $("#previewBody").innerHTML = `<div class="empty">正在按需读取单个文件…</div>`;
  dialog.showModal();
  const url = `/api/preview?path=${encodeURIComponent(path)}`;
  try {
    if (previewableImages.has(extension)) {
      const image = new Image();
      image.alt = name;
      image.src = url;
      image.onerror = () => { $("#previewBody").innerHTML = `<p class="error">图片预览失败。</p>`; };
      $("#previewBody").replaceChildren(image);
    } else {
      const data = await api(url);
      const pre = document.createElement("pre");
      pre.textContent = data.content;
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
  if (preview) openPreview(preview.dataset.path, preview.dataset.name, preview.dataset.ext);
});

$("#searchForm").addEventListener("submit", (event) => { event.preventDefault(); state.q = $("#searchInput").value.trim(); state.page = 1; loadFiles(); });
$("#prevPage").addEventListener("click", () => { state.page -= 1; loadFiles(); window.scrollTo({ top: $(".workspace").offsetTop, behavior: "smooth" }); });
$("#nextPage").addEventListener("click", () => { state.page += 1; loadFiles(); window.scrollTo({ top: $(".workspace").offsetTop, behavior: "smooth" }); });
$("#closePreview").addEventListener("click", () => $("#previewDialog").close());
$("#previewDialog").addEventListener("close", () => $("#previewBody").replaceChildren());
$("#themeToggle").addEventListener("click", toggleTheme);

applyTheme(document.documentElement.dataset.theme);
loadOverview().then(loadFiles);
