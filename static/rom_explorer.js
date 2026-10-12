/**
 * Explorador visual de /roms/ — árvore, grelha, DnD interno e drop do SO.
 * Depende de helpers em app.js: getApi, waitForApi, escapeHtml, setBusy,
 * appendLog, selectedDrive, fetchDrives, busy.
 */
const RomExplorer = (() => {
  const MIME = "application/x-route1-roms";
  const CHEVRON =
    '<svg class="rom-x-tree-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/></svg>';

  let cwd = "";
  let tree = [];
  let dirs = [];
  let files = [];
  let selection = new Set();
  let lastClickedRel = null;
  let loadInFlight = false;
  let dragRels = null;
  let dropTargetRel = null;
  let sheetBound = false;
  let searchQuery = "";
  let searchHits = null;
  let catalogCache = null;
  let searchTimer = null;
  let searchGen = 0;
  let tipTimer = null;
  let tipRel = null;
  let tipVisible = false;
  let drawerRel = null;
  let drawerGen = 0;
  let drawerData = null;
  let artKind = "boxart";
  let artCandidates = [];
  let artSearching = false;
  let artQueryDraft = "";
  let gridRenderGen = 0;
  let escBound = false;

  const TIP_DELAY_MS = 3000;

  function isSearching() {
    return !!(searchQuery && searchQuery.trim());
  }

  function foldText(s) {
    return String(s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function updateSearchClearBtn() {
    const btn = document.getElementById("rom-x-search-clear");
    if (btn) btn.classList.toggle("hidden", !isSearching());
  }

  function clearSearchUi(rerender) {
    searchQuery = "";
    searchHits = null;
    searchGen += 1;
    if (searchTimer) {
      clearTimeout(searchTimer);
      searchTimer = null;
    }
    const input = document.getElementById("rom-x-search");
    if (input && input.value) input.value = "";
    updateSearchClearBtn();
    if (rerender) renderGrid();
  }

  function invalidateCatalog() {
    catalogCache = null;
  }

  function romMatchesQuery(rom, qFold) {
    if (!qFold) return true;
    const hay = foldText(
      [
        rom.display_name,
        rom.name,
        rom.title,
        rom.rel_path,
        rom.platform,
        rom.game_code,
      ]
        .filter(Boolean)
        .join(" ")
    );
    return hay.includes(qFold);
  }

  async function ensureCatalog() {
    const m = mount();
    if (!m) return [];
    if (catalogCache && catalogCache.mount === m && Array.isArray(catalogCache.roms)) {
      return catalogCache.roms;
    }
    const api = getApi() || (await waitForApi());
    if (!api || typeof api.list_roms !== "function") {
      throw new Error("API de listagem indisponível.");
    }
    const data = await api.list_roms(m);
    if (!data || !data.success) {
      throw new Error((data && data.error) || "Falha ao indexar jogos.");
    }
    const roms = Array.isArray(data.roms) ? data.roms : [];
    catalogCache = { mount: m, roms };
    return roms;
  }

  async function runSearch(rawQuery, gen) {
    const q = (rawQuery || "").trim();
    searchQuery = q;
    updateSearchClearBtn();
    if (!q) {
      searchHits = null;
      if (gen === searchGen) renderGrid();
      return;
    }
    if (!mount()) {
      searchHits = [];
      if (gen === searchGen) renderGrid();
      return;
    }
    try {
      const roms = await ensureCatalog();
      if (gen !== searchGen) return;
      const qFold = foldText(q);
      const hits = roms
        .filter((r) => romMatchesQuery(r, qFold))
        .slice(0, 200)
        .map((r) => Object.assign({}, r, { type: "file" }));
      searchHits = hits;
      selection = new Set([...selection].filter((rel) => hits.some((h) => h.rel_path === rel)));
      renderGrid();
    } catch (err) {
      if (gen !== searchGen) return;
      searchHits = [];
      const grid = document.getElementById("rom-x-grid");
      if (grid) {
        grid.innerHTML = emptyHtml(
          "Falha na pesquisa",
          escapeHtml(err.message || String(err))
        );
      }
      renderStatus();
    }
  }

  function onSearchInput(ev) {
    const value = ev && ev.target ? ev.target.value : "";
    searchQuery = value;
    updateSearchClearBtn();
    if (searchTimer) clearTimeout(searchTimer);
    const gen = ++searchGen;
    searchTimer = setTimeout(() => {
      searchTimer = null;
      runSearch(value, gen);
    }, 180);
  }

  function onSearchKeyDown(ev) {
    if (ev.key === "Escape") {
      ev.preventDefault();
      clearSearch();
    }
  }

  function clearSearch() {
    clearSearchUi(false);
    renderGrid();
  }

  function mount() {
    return selectedDrive && selectedDrive.mount_path
      ? selectedDrive.mount_path
      : null;
  }

  function layoutChoice() {
    return (
      document.querySelector('input[name="organize-layout"]:checked')?.value ||
      "console"
    );
  }

  function emptyHtml(title, sub) {
    return (
      `<div class="rom-x-empty" role="status">` +
      `<p class="rom-x-empty-title">${escapeHtml(title)}</p>` +
      (sub
        ? `<p class="rom-x-empty-sub">${sub}</p>`
        : "") +
      `</div>`
    );
  }

  function updateRemoveBtn() {
    const btn = document.getElementById("rom-x-remove");
    if (!btn) return;
    const n = selection.size;
    btn.disabled = n === 0 || busy;
    const label = btn.querySelector(".rom-x-toolbtn-label");
    const text = n > 0 ? `Remover (${n})` : "Remover";
    if (label) label.textContent = text;
    btn.title = n > 0 ? `Remover ${n} seleccionado(s)` : "Remover seleccionados";
    btn.setAttribute("aria-label", btn.title);
  }

  function updateUpBtn() {
    const btn = document.getElementById("rom-x-up");
    if (btn) btn.disabled = !cwd || busy;
  }

  function renderStatus() {
    const el = document.getElementById("rom-x-status");
    if (!el) return;
    if (!mount()) {
      el.textContent = "Seleccione um cartão SD.";
      return;
    }
    if (isSearching()) {
      const n = Array.isArray(searchHits) ? searchHits.length : 0;
      const q = escapeHtml(searchQuery.trim());
      el.innerHTML =
        `<strong>${n}</strong> resultado(s) para «${q}»` +
        (n >= 200 ? " · a mostrar os primeiros 200" : "") +
        ` · pesquisa em todo <code>/roms/</code>`;
      return;
    }
    const total = dirs.length + files.length;
    const sel = selection.size;
    const path = cwd ? `/roms/${cwd}/` : "/roms/";
    el.innerHTML =
      `<strong>${total}</strong> itens` +
      (sel ? ` · <strong>${sel}</strong> seleccionados` : "") +
      ` · <span title="${escapeHtml(path)}">${escapeHtml(path)}</span>`;
  }

  function renderCrumb() {
    const el = document.getElementById("rom-x-crumb");
    if (!el) return;
    const parts = cwd ? cwd.split("/").filter(Boolean) : [];
    let html =
      `<button type="button" class="rom-x-crumb-seg" data-rel="" aria-current="${
        parts.length ? "false" : "page"
      }">/roms</button>`;
    let acc = "";
    parts.forEach((p, i) => {
      acc = acc ? `${acc}/${p}` : p;
      const rel = acc;
      const last = i === parts.length - 1;
      html +=
        `<span class="rom-x-crumb-sep" aria-hidden="true">/</span>` +
        `<button type="button" class="rom-x-crumb-seg" data-rel="${escapeHtml(
          rel
        )}" aria-current="${last ? "page" : "false"}">${escapeHtml(p)}</button>`;
    });
    el.innerHTML = html;
    el.querySelectorAll("[data-rel]").forEach((btn) => {
      btn.onclick = () => navigate(btn.getAttribute("data-rel") || "");
    });
  }

  function renderTreeNode(node, depth) {
    if (!node) return "";
    const rel = node.rel_path || "";
    const active = rel === cwd;
    const kids = Array.isArray(node.children) ? node.children : [];
    const hasKids = kids.length > 0;
    const pad = 0.55 + depth * 0.75;
    let html =
      `<button type="button" role="treeitem" ` +
      `class="rom-x-tree-item${active ? " rom-x-tree-item--active" : ""}" ` +
      `style="padding-left:${pad}rem" ` +
      `data-rel="${escapeHtml(rel)}" ` +
      `aria-selected="${active ? "true" : "false"}" ` +
      `aria-expanded="${hasKids ? "true" : "false"}" ` +
      `ondragover="RomExplorer.onTreeDragOver(event)" ` +
      `ondrop="RomExplorer.onTreeDrop(event)" ` +
      `ondragleave="RomExplorer.onTreeDragLeave(event)">` +
      (hasKids
        ? CHEVRON
        : `<span class="rom-x-tree-chevron" aria-hidden="true"></span>`) +
      platformSvgHtml("folder", "rom-x-ico--tree") +
      `<span class="rom-x-tree-label">${escapeHtml(node.name || "roms")}</span>` +
      `</button>`;
    kids.forEach((c) => {
      html += renderTreeNode(c, depth + 1);
    });
    return html;
  }

  function renderTree() {
    const el = document.getElementById("rom-x-tree");
    if (!el) return;
    if (!tree.length) {
      el.innerHTML =
        '<p class="text-[11px] text-fg-mute px-3 py-2">Sem pastas ainda.</p>';
      return;
    }
    el.innerHTML = tree.map((n) => renderTreeNode(n, 0)).join("");
    el.querySelectorAll(".rom-x-tree-item").forEach((btn) => {
      btn.onclick = () => navigate(btn.getAttribute("data-rel") || "");
    });
  }

  const PLATFORM_LABEL = {
    gba: "GBA",
    gb: "GB",
    gbc: "GBC",
    nds: "NDS",
    dsi: "DSi",
    apps: "APP",
    nes: "NES",
    snes: "SNES",
    gen: "GEN",
    sms: "SMS",
    gg: "GG",
  };

  const PLATFORM_SVG_KEYS = new Set([
    "nds",
    "dsi",
    "gba",
    "gb",
    "gbc",
    "nes",
    "fds",
    "snes",
    "gen",
    "sms",
    "gg",
    "sg",
    "tg16",
    "pce",
    "a26",
    "a52",
    "a78",
    "col",
    "cpc",
    "m5",
    "ngp",
    "ws",
    "int",
    "msx",
    "xex",
    "min",
    "apps",
    "bios",
  ]);

  function platformKey(entry) {
    if (!entry) return "rom";
    if (entry.type === "dir") return "folder";
    if (entry.kind === "app" || entry.platform === "apps") return "apps";
    const plat = (entry.platform || "").toLowerCase();
    if (PLATFORM_SVG_KEYS.has(plat)) return plat;
    const ext = (entry.name || "").split(".").pop()?.toLowerCase() || "";
    const byExt = {
      gba: "gba",
      agb: "gba",
      mb: "gba",
      gb: "gb",
      sgb: "gb",
      gbc: "gbc",
      nds: "nds",
      dsi: "dsi",
      ids: "nds",
      nes: "nes",
      fds: "fds",
      smc: "snes",
      sfc: "snes",
      md: "gen",
      gen: "gen",
      sms: "sms",
      gg: "gg",
    };
    return byExt[ext] || "rom";
  }

  function platformSvgHtml(key, extraClass) {
    const k = PLATFORM_SVG_KEYS.has(key) || key === "folder" || key === "rom"
      ? key
      : "rom";
    const cls = extraClass
      ? `rom-x-ico rom-x-ico--plat ${extraClass}`
      : "rom-x-ico rom-x-ico--plat";
    return (
      `<img class="${cls}" src="assets/platforms/${escapeHtml(k)}.svg" ` +
      `alt="" width="48" height="48" draggable="false" decoding="async" aria-hidden="true">`
    );
  }

  function platformBadge(item) {
    if (!item || item.type === "dir") return "";
    const plat = (item.platform || "").toLowerCase();
    const label = PLATFORM_LABEL[plat];
    if (!label) return "";
    // Com ícone real (banner/custom): badge omitido
    if (item.icon) return "";
    const mod =
      plat === "gba"
        ? " rom-x-badge--gba"
        : plat === "gb" || plat === "gbc"
          ? " rom-x-badge--gb"
          : "";
    return `<span class="rom-x-badge${mod}">${label}</span>`;
  }

  function iconHtml(item) {
    if (item.type === "dir") {
      return platformSvgHtml("folder");
    }
    const src = item.icon;
    if (src && typeof src === "string" && src.indexOf("data:image/") === 0) {
      return (
        `<img class="rom-x-ico rom-x-ico--game" src="${src}" alt="" ` +
        `width="48" height="48" draggable="false" decoding="async">`
      );
    }
    return platformSvgHtml(platformKey(item));
  }

  function renderGrid() {
    const el = document.getElementById("rom-x-grid");
    if (!el) return;
    const searching = isSearching();

    if (!mount()) {
      el.innerHTML = emptyHtml(
        "Nenhum cartão seleccionado",
        "Escolha um volume SD acima para explorar <code>/roms/</code>."
      );
      updateRemoveBtn();
      updateUpBtn();
      renderStatus();
      return;
    }

    const items = searching
      ? Array.isArray(searchHits)
        ? searchHits
        : []
      : [...dirs, ...files];

    if (searching && searchHits === null) {
      el.innerHTML = emptyHtml("A pesquisar…", "");
      updateRemoveBtn();
      updateUpBtn();
      renderStatus();
      return;
    }

    if (!items.length) {
      el.innerHTML = searching
        ? emptyHtml(
            "Nenhum jogo encontrado",
            `Nada corresponde a «${escapeHtml(searchQuery.trim())}».`
          )
        : emptyHtml(
            "Pasta vazia",
            "Arraste ROMs para aqui ou use <strong>Adicionar</strong>."
          );
      updateRemoveBtn();
      updateUpBtn();
      renderStatus();
      return;
    }

    // Virtualizar listas grandes (>200) para manter o orçamento de performance.
    if (
      items.length > 200 &&
      window.R1K &&
      R1K.virtual &&
      typeof R1K.virtual.createVirtualList === "function"
    ) {
      if (!el._vlist) {
        el.style.height = el.style.height || "420px";
        el._vlist = R1K.virtual.createVirtualList(el, items, {
          rowHeight: 64,
          renderRow: (item) => {
            const wrap = document.createElement("div");
            wrap.innerHTML = gridItemHtml(item, searching);
            const node = wrap.firstElementChild;
            bindGridItem(node, item);
            return node;
          },
        });
      } else {
        el._vlist.setItems(items);
      }
      updateRemoveBtn();
      updateUpBtn();
      renderStatus();
      return;
    }
    if (el._vlist) {
      el._vlist.destroy();
      el._vlist = null;
    }

    el.innerHTML = items.map((item) => gridItemHtml(item, searching)).join("");
    updateRemoveBtn();
    updateUpBtn();
    renderStatus();
    gridRenderGen += 1;
    hideTip();
  }

  function gridItemHtml(item, searching) {
    const rel = item.rel_path || "";
    const isDir = item.type === "dir";
    const selected = selection.has(rel);
    const save = item.has_save
      ? '<span class="rom-x-badge rom-x-badge--save">save</span>'
      : "";
    const platBadge = platformBadge(item);
    const parent = !isDir && rel.includes("/")
      ? rel.slice(0, rel.lastIndexOf("/"))
      : "";
    const pathHint =
      searching && parent
        ? `<span class="rom-x-item-path" title="${escapeHtml(
            "/roms/" + parent + "/"
          )}">${escapeHtml(parent)}</span>`
        : "";
    const meta = isDir
      ? `${item.item_count || 0} itens`
      : `${platBadge}${platBadge ? " " : ""}${pathHint}${
          pathHint ? " " : ""
        }${escapeHtml(item.size_label || "")}${save ? " " + save : ""}`;
    const title = escapeHtml(
      isDir ? item.name : item.display_name || item.name || ""
    );
    return (
      `<div class="rom-x-item${selected ? " rom-x-item--selected" : ""}" ` +
      `role="listitem" tabindex="0" ` +
      `aria-selected="${selected ? "true" : "false"}" ` +
      `data-rel="${escapeHtml(rel)}" data-type="${isDir ? "dir" : "file"}" ` +
      `data-platform="${escapeHtml(item.platform || "")}" ` +
      `draggable="${isDir ? "false" : "true"}" ` +
      `ondragstart="RomExplorer.onItemDragStart(event)" ` +
      `ondragend="RomExplorer.onItemDragEnd(event)" ` +
      `ondragover="RomExplorer.onItemDragOver(event)" ` +
      `ondrop="RomExplorer.onItemDrop(event)" ` +
      `ondragleave="RomExplorer.onItemDragLeave(event)" ` +
      `onmouseenter="RomExplorer.onItemMouseEnter(event)" ` +
      `onmouseleave="RomExplorer.onItemMouseLeave(event)" ` +
      `onmousemove="RomExplorer.onItemMouseMove(event)" ` +
      `onclick="RomExplorer.onItemClick(event)" ` +
      `ondblclick="RomExplorer.onItemDblClick(event)" ` +
      `onkeydown="RomExplorer.onItemKeyDown(event)">` +
      iconHtml(item) +
      `<span class="rom-x-item-name">${title}</span>` +
      `<span class="rom-x-item-meta">${meta}</span>` +
      `</div>`
    );
  }

  function bindGridItem(_node, _item) {
    /* handlers via atributos on* no HTML */
  }

  function renderAll() {
    renderCrumb();
    renderTree();
    renderGrid();
  }

  async function refresh() {
    const grid = document.getElementById("rom-x-grid");
    invalidateCatalog();
    if (!mount()) {
      cwd = "";
      tree = [];
      dirs = [];
      files = [];
      selection.clear();
      searchHits = isSearching() ? [] : null;
      renderAll();
      return;
    }
    if (loadInFlight) return;
    loadInFlight = true;
    if (grid && !isSearching()) {
      grid.innerHTML = emptyHtml("A carregar…", "");
    }
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.browse_roms !== "function") {
        if (grid) {
          grid.innerHTML = emptyHtml(
            "API indisponível",
            "Reinicie a aplicação e tente de novo."
          );
        }
        renderStatus();
        return;
      }
      const data = await api.browse_roms(mount(), cwd);
      if (!data || !data.success) {
        dirs = [];
        files = [];
        tree = [];
        if (grid && !isSearching()) {
          grid.innerHTML = emptyHtml(
            "Falha ao listar",
            escapeHtml((data && data.error) || "Não foi possível ler a pasta.")
          );
        }
        renderCrumb();
        renderTree();
        updateRemoveBtn();
        if (isSearching()) {
          await runSearch(searchQuery, searchGen);
        } else {
          renderStatus();
        }
        return;
      }
      cwd = data.rel_dir || "";
      dirs = Array.isArray(data.dirs) ? data.dirs : [];
      files = Array.isArray(data.files) ? data.files : [];
      tree = Array.isArray(data.tree) ? data.tree : [];
      const alive = new Set([
        ...dirs.map((d) => d.rel_path),
        ...files.map((f) => f.rel_path),
      ]);
      if (!isSearching()) {
        selection = new Set([...selection].filter((r) => alive.has(r)));
      }
      renderCrumb();
      renderTree();
      if (isSearching()) {
        await runSearch(searchQuery, ++searchGen);
      } else {
        renderGrid();
      }
    } catch (err) {
      if (grid && !isSearching()) {
        grid.innerHTML = emptyHtml(
          "Erro",
          escapeHtml(err.message || String(err))
        );
      }
      renderStatus();
    } finally {
      loadInFlight = false;
    }
  }

  function navigate(rel) {
    clearSearchUi(false);
    cwd = rel || "";
    selection.clear();
    lastClickedRel = null;
    refresh();
  }

  function goUp() {
    if (!cwd) return;
    const parts = cwd.split("/").filter(Boolean);
    parts.pop();
    navigate(parts.join("/"));
  }

  function hideTip() {
    if (tipTimer) {
      clearTimeout(tipTimer);
      tipTimer = null;
    }
    tipRel = null;
    tipVisible = false;
    const tip = document.getElementById("rom-x-tip");
    if (tip) {
      tip.classList.add("hidden");
      tip.setAttribute("aria-hidden", "true");
      tip.innerHTML = "";
    }
  }

  function positionTip(clientX, clientY) {
    const tip = document.getElementById("rom-x-tip");
    if (!tip || tip.classList.contains("hidden")) return;
    const pad = 12;
    const tw = tip.offsetWidth || 200;
    const th = tip.offsetHeight || 60;
    let x = clientX + pad;
    let y = clientY + pad;
    const vw = window.innerWidth || 800;
    const vh = window.innerHeight || 600;
    if (x + tw > vw - 8) x = Math.max(8, clientX - tw - pad);
    if (y + th > vh - 8) y = Math.max(8, clientY - th - pad);
    tip.style.left = `${Math.round(x)}px`;
    tip.style.top = `${Math.round(y)}px`;
  }

  function showTipForItem(item, clientX, clientY) {
    const tip = document.getElementById("rom-x-tip");
    if (!tip || !item) return;
    const name = item.display_name || item.name || "";
    const plat = (item.platform || "").toUpperCase() || "?";
    const size = item.size_label || "";
    tip.innerHTML =
      `<span class="rom-x-tip-name">${escapeHtml(name)}</span>` +
      `<span class="rom-x-tip-meta">${escapeHtml(plat)}` +
      (size ? ` · ${escapeHtml(size)}` : "") +
      `</span>`;
    tip.classList.remove("hidden");
    tip.setAttribute("aria-hidden", "false");
    tipVisible = true;
    positionTip(clientX, clientY);
  }

  function findItemByRel(rel) {
    if (!rel) return null;
    if (isSearching() && Array.isArray(searchHits)) {
      return searchHits.find((i) => i.rel_path === rel) || null;
    }
    return (
      files.find((i) => i.rel_path === rel) ||
      dirs.find((i) => i.rel_path === rel) ||
      null
    );
  }

  function onItemMouseEnter(ev) {
    const el = ev.currentTarget;
    if (!el || el.getAttribute("data-type") === "dir") return;
    if (dragRels) return;
    const rel = el.getAttribute("data-rel");
    const gen = gridRenderGen;
    hideTip();
    tipRel = rel;
    const x = ev.clientX;
    const y = ev.clientY;
    tipTimer = setTimeout(() => {
      tipTimer = null;
      if (gen !== gridRenderGen || tipRel !== rel || dragRels) return;
      if (!el.isConnected) return;
      const item = findItemByRel(rel);
      if (!item) return;
      showTipForItem(item, x, y);
    }, TIP_DELAY_MS);
  }

  function onItemMouseLeave(_ev) {
    hideTip();
  }

  function onItemMouseMove(ev) {
    if (tipVisible) positionTip(ev.clientX, ev.clientY);
  }

  function isDrawerOpen() {
    const d = document.getElementById("rom-x-drawer");
    return !!(d && !d.classList.contains("hidden"));
  }

  function isDeleteSheetOpen() {
    const s = document.getElementById("rom-x-delete-sheet");
    return !!(s && !s.classList.contains("hidden"));
  }

  function closeDrawer() {
    twlArtQuery();
    drawerRel = null;
    drawerData = null;
    artCandidates = [];
    artSearching = false;
    drawerGen += 1;
    const d = document.getElementById("rom-x-drawer");
    const b = document.getElementById("rom-x-drawer-backdrop");
    if (d) {
      d.classList.add("hidden");
      d.setAttribute("aria-hidden", "true");
    }
    if (b) b.classList.add("hidden");
  }

  function twlArtQuery() {
    const el = document.getElementById("rom-x-art-query");
    if (el) artQueryDraft = String(el.value || "");
    return artQueryDraft;
  }

  function bindTwlArtControls(candidates) {
    const body = document.getElementById("rom-x-drawer-body");
    if (!body) return;
    body.querySelectorAll("[data-twl-kind]").forEach((tab) => {
      tab.onclick = () => {
        const k = tab.getAttribute("data-twl-kind");
        if (k !== "boxart" && k !== "icon") return;
        if (artKind === k) return;
        twlArtQuery();
        artKind = k;
        artCandidates = [];
        artSearching = false;
        if (drawerData) {
          renderDrawerBody(drawerData, {
            candidates: [],
            message:
              "Escolha «Pesquisar» ou «Buscar online» para ver opções de " +
              (artKind === "icon" ? "ícone" : "capa") +
              ".",
          });
        }
      };
    });
    const queryEl = document.getElementById("rom-x-art-query");
    if (queryEl) {
      queryEl.oninput = () => {
        artQueryDraft = String(queryEl.value || "");
      };
      queryEl.onkeydown = (ev) => {
        if (ev.key === "Enter") {
          ev.preventDefault();
          runTwlArtSearch(twlArtQuery());
        }
      };
    }
    const searchBtn = document.getElementById("rom-x-art-search-btn");
    if (searchBtn) searchBtn.onclick = () => runTwlArtSearch(twlArtQuery());
    const autoBtn = document.getElementById("rom-x-art-auto");
    if (autoBtn) autoBtn.onclick = () => runTwlArtSearch("");
    const manBtn = document.getElementById("rom-x-art-manual");
    if (manBtn) manBtn.onclick = () => pickArtwork(artKind);
    body.querySelectorAll("[data-twl-art-idx]").forEach((btn) => {
      btn.onclick = () => {
        const idx = parseInt(btn.getAttribute("data-twl-art-idx") || "-1", 10);
        const c = candidates[idx];
        if (c && c.url) applyTwlArtUrl(c.url);
      };
    });
  }

  function renderDrawerBody(data, artState) {
    const body = document.getElementById("rom-x-drawer-body");
    if (!body) return;
    drawerData = data;
    const rom = (data && data.rom) || {};
    const run = (data && data.run_info) || {};
    const hints = (data && data.hints) || {};
    const plat = (rom.platform || "").toUpperCase() || "—";
    const cover =
      artState && artState.current && artKind === "boxart"
        ? artState.current
        : data.boxart;
    const iconSrc =
      artState && artState.current && artKind === "icon"
        ? artState.current
        : data.display_icon || data.custom_icon || rom.icon;
    const sidecars = Array.isArray(rom.sidecars) ? rom.sidecars : [];
    const reqs = Array.isArray(run.requirements) ? run.requirements : [];
    const candidates = Array.isArray(artState && artState.candidates)
      ? artState.candidates
      : artCandidates;
    artCandidates = candidates;

    const qEl = document.getElementById("rom-x-art-query");
    if (qEl) artQueryDraft = String(qEl.value || "");
    if (artState && typeof artState.query === "string") {
      artQueryDraft = artState.query;
    }
    const queryVal = artQueryDraft;
    const restoreFocus =
      qEl && document.activeElement === qEl ? qEl.selectionStart : null;

    let coverHtml = cover
      ? `<img src="${cover}" alt="" draggable="false">`
      : `<div class="rom-x-drawer-cover-ph">${platformSvgHtml(
          platformKey(rom),
          "rom-x-ico--cover-ph"
        )}</div>`;

    let iconHtmlInner = iconSrc
      ? `<img class="rom-x-ico rom-x-ico--game" src="${iconSrc}" alt="" width="48" height="48" draggable="false">`
      : platformSvgHtml(platformKey(rom));

    const rows = [
      ["Plataforma", plat],
      ["Tamanho", rom.size_label || "—"],
      ["Ficheiro", rom.name || "—"],
      ["Tipo", rom.kind || "game"],
    ];
    if (rom.game_code) rows.push(["Game code", rom.game_code]);
    if (rom.title) rows.push(["Título (header)", rom.title]);

    const dl = rows
      .map(
        ([k, v]) =>
          `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd>`
      )
      .join("");

    const sideList = sidecars.length
      ? `<ul class="rom-x-drawer-sidecars">${sidecars
          .map(
            (s) =>
              `<li>${escapeHtml(s.name || "")}${
                s.is_save ? " · save" : ""
              }</li>`
          )
          .join("")}</ul>`
      : `<p class="rom-x-drawer-hint">Sem saves/sidecars detectados.</p>`;

    const reqList = reqs.length
      ? `<ul class="rom-x-drawer-reqs">${reqs
          .map((r) => `<li>${escapeHtml(r)}</li>`)
          .join("")}</ul>`
      : "";

    const isIcon = artKind === "icon";
    const opts = candidates
      .map((c, i) => {
        const src = escapeHtml(c.preview || c.url || "");
        return (
          `<button type="button" class="dspico-art-opt ${
            isIcon ? "dspico-art-opt--icon" : ""
          }" data-twl-art-idx="${i}">
            <img src="${src}" alt="" draggable="false" loading="lazy" referrerpolicy="no-referrer"
                 onerror="this.classList.add('hidden'); this.insertAdjacentHTML('afterend','<div class=\\'dspico-art-ph${
                   isIcon ? " dspico-art-ph--icon" : ""
                 }\\'>—</div>');">
            <span class="dspico-art-opt-label">${escapeHtml(
              (c.source ? c.source + " · " : "") + (c.label || "opção")
            )}</span>
          </button>`
        );
      })
      .join("");

    const artMsg =
      (artState && artState.message) ||
      (artSearching
        ? "A procurar na Internet…"
        : "Use «Pesquisar» ou «Buscar online» para ver opções.");

    body.innerHTML =
      `<div class="rom-x-drawer-cover">${
        artKind === "boxart" ? coverHtml : iconHtmlInner
      }</div>` +
      (artKind === "boxart"
        ? `<div class="rom-x-drawer-icons">${iconHtmlInner}</div>`
        : "") +
      `<p class="rom-x-drawer-name">${escapeHtml(
        rom.display_name || rom.name || ""
      )}</p>` +
      `<p class="rom-x-drawer-path">/roms/${escapeHtml(rom.rel_path || "")}</p>` +
      `<dl class="rom-x-drawer-dl">${dl}</dl>` +
      `<div class="rom-x-drawer-section">` +
      `<h5>Arte TWiLight</h5>` +
      `<div class="dspico-art-tabs mt-1">
        <button type="button" class="dspico-art-tab ${
          artKind === "boxart" ? "dspico-art-tab--on" : ""
        }" data-twl-kind="boxart">Capa</button>
        <button type="button" class="dspico-art-tab ${
          artKind === "icon" ? "dspico-art-tab--on" : ""
        }" data-twl-kind="icon">Ícone</button>
      </div>` +
      `<div class="dspico-art-search mt-2">
        <div class="dspico-art-search-row">
          <input type="text" id="rom-x-art-query" placeholder="Pesquisar capa/ícone…" autocomplete="off" spellcheck="false" value="${escapeHtml(
            queryVal
          )}">
          <button type="button" class="btn-secondary" id="rom-x-art-search-btn">Pesquisar</button>
        </div>
      </div>` +
      `<div class="dspico-art-actions mt-2">
        <button type="button" class="btn-primary !py-1.5 !px-3 text-[11px]" id="rom-x-art-auto">Buscar online</button>
        <button type="button" class="btn-secondary !py-1.5 !px-3 text-[11px]" id="rom-x-art-manual">Ficheiro do PC…</button>
      </div>` +
      `<p class="dspico-art-local-hint">PNG ou BMP. JPEG não suportado.</p>` +
      `<p class="rom-x-drawer-hint">${escapeHtml(
        hints[artKind === "icon" ? "icon" : "boxart"] || ""
      )}</p>` +
      (artMsg
        ? `<p class="text-[12px] text-fg-soft mt-1">${escapeHtml(artMsg)}</p>`
        : "") +
      (candidates.length
        ? `<div class="dspico-art-grid mt-2">${opts}</div>
           <p class="rom-x-drawer-hint">Clique para gravar PNG no cartão.</p>`
        : !artSearching
          ? `<p class="rom-x-drawer-hint mt-1">Ainda sem resultados — pesquise ou escolha um ficheiro.</p>`
          : "") +
      `</div>` +
      `<div class="rom-x-drawer-section">` +
      `<h5>Como corre</h5>` +
      `<p><strong>${escapeHtml(run.title || "")}</strong></p>` +
      `<p>${escapeHtml(run.body || "")}</p>` +
      reqList +
      `</div>` +
      `<div class="rom-x-drawer-section">` +
      `<h5>Saves e extras</h5>${sideList}</div>`;

    bindTwlArtControls(candidates);
    const newQ = document.getElementById("rom-x-art-query");
    if (newQ && restoreFocus != null) {
      newQ.focus();
      try {
        const pos = Math.min(restoreFocus, newQ.value.length);
        newQ.setSelectionRange(pos, pos);
      } catch (_e) {
        /* ignore */
      }
    }
  }

  async function openDrawer(rel) {
    if (!rel || !mount()) return;
    hideTip();
    ensureGlobalBindings();
    const gen = ++drawerGen;
    const same = drawerRel === rel;
    drawerRel = rel;
    if (!same) {
      artKind = "boxart";
      artQueryDraft = "";
    }
    artCandidates = [];
    artSearching = false;
    const d = document.getElementById("rom-x-drawer");
    const b = document.getElementById("rom-x-drawer-backdrop");
    const body = document.getElementById("rom-x-drawer-body");
    if (body) {
      body.innerHTML = `<p class="rom-x-drawer-hint">A carregar detalhes…</p>`;
    }
    if (d) {
      d.classList.remove("hidden");
      d.setAttribute("aria-hidden", "false");
    }
    if (b) b.classList.remove("hidden");

    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.rom_details !== "function") {
        if (gen !== drawerGen) return;
        if (body) {
          body.innerHTML = `<p class="rom-x-drawer-hint">API de detalhes indisponível.</p>`;
        }
        return;
      }
      const data = await api.rom_details(mount(), rel);
      if (gen !== drawerGen) return;
      if (!data || !data.success) {
        if (body) {
          body.innerHTML = `<p class="rom-x-drawer-hint">${escapeHtml(
            (data && data.error) || "Falha ao carregar."
          )}</p>`;
        }
        return;
      }
      renderDrawerBody(data, {
        searching: false,
        query: artQueryDraft,
        message:
          "Use «Pesquisar» ou «Buscar online» para ver opções, ou escolha um ficheiro do PC.",
        candidates: [],
      });
    } catch (err) {
      if (gen !== drawerGen) return;
      if (body) {
        body.innerHTML = `<p class="rom-x-drawer-hint">${escapeHtml(
          err.message || String(err)
        )}</p>`;
      }
    }
  }

  async function runTwlArtSearch(query, opts) {
    if (!drawerRel || !mount()) return;
    if (typeof isHardBusy === "function" ? isHardBusy() : busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    const options = opts && typeof opts === "object" ? opts : {};
    const gen =
      options.expectedGen != null ? options.expectedGen : ++drawerGen;
    let q = typeof query === "string" ? query : twlArtQuery();
    if (options.clearQuery) {
      artQueryDraft = "";
      q = "";
    } else {
      artQueryDraft = q;
    }
    artSearching = true;
    artCandidates = [];
    if (drawerData) {
      renderDrawerBody(drawerData, {
        searching: true,
        query: artQueryDraft,
        message: "A procurar na Internet…",
        candidates: [],
      });
    }
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.search_rom_artwork !== "function") {
        if (gen !== drawerGen) return;
        artSearching = false;
        // Fallback: fetch automático antigo
        await fetchArtwork();
        return;
      }
      setBusy(true, null, { soft: true });
      const data = await api.search_rom_artwork(
        mount(),
        drawerRel,
        artKind,
        q
      );
      if (gen !== drawerGen) return;
      artSearching = false;
      if (!(data && data.success)) {
        if (drawerData) {
          renderDrawerBody(drawerData, {
            query: artQueryDraft,
            message: (data && data.error) || "Pesquisa falhou.",
            candidates: [],
          });
        }
        return;
      }
      artCandidates = data.candidates || [];
      if (drawerData) {
        renderDrawerBody(drawerData, {
          ...data,
          query: artQueryDraft,
          current:
            data.current ||
            (artKind === "icon"
              ? drawerData.custom_icon || drawerData.display_icon
              : drawerData.boxart),
          searching: false,
        });
      }
    } catch (err) {
      if (gen !== drawerGen) return;
      artSearching = false;
      if (drawerData) {
        renderDrawerBody(drawerData, {
          query: artQueryDraft,
          message: err.message || String(err),
          candidates: [],
        });
      }
    } finally {
      setBusy(false);
    }
  }

  async function applyTwlArtUrl(url) {
    if (!drawerRel || !mount() || !url) return;
    if (typeof isHardBusy === "function" ? isHardBusy() : busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    let ok = false;
    const rel = drawerRel;
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.apply_rom_artwork_url !== "function") {
        appendLog("API de aplicação de arte indisponível.", "error");
        return;
      }
      setBusy(true);
      appendLog(
        artKind === "icon" ? "A gravar ícone…" : "A gravar capa…",
        "info"
      );
      const res = await api.apply_rom_artwork_url(
        mount(),
        rel,
        artKind,
        url
      );
      if (res && res.success) {
        appendLog(res.message || "Arte gravada.", "success");
        ok = true;
      } else {
        appendLog((res && res.error) || "Falha ao gravar arte.", "error");
      }
    } catch (err) {
      appendLog(`Falha na arte: ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
    if (ok) {
      invalidateCatalog();
      await openDrawer(rel);
      await refresh();
    }
  }

  function renderTwilightBatchMissing(missing) {
    const el = document.getElementById("rom-x-batch-missing");
    if (!el) return;
    const list = Array.isArray(missing) ? missing : [];
    if (!list.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("hidden");
    const rows = list
      .map((item) => {
        const name = escapeHtml(item.display_name || item.rel_path || "?");
        const bits = [];
        if (item.missing_cover) bits.push("capa");
        if (item.missing_icon) bits.push("ícone");
        const need = bits.length ? bits.join(" + ") : "arte";
        const rel = escapeHtml(item.rel_path || "");
        return `<div class="flex flex-wrap items-center justify-between gap-2 p-2 rounded border border-line text-[12px]">
          <div>
            <div class="font-medium text-fg">${name}</div>
            <div class="text-[11px] text-fg-mute">Em falta: ${escapeHtml(need)}</div>
          </div>
          <div class="flex flex-wrap gap-1">
            <button type="button" class="btn-secondary !text-[11px] !py-1 !px-2" data-twl-search="${rel}">Pesquisar</button>
            <button type="button" class="btn-ghost !text-[11px] !py-1 !px-2" data-twl-file="${rel}" data-twl-kind="${
              item.missing_cover ? "boxart" : "icon"
            }">Escolher ficheiro</button>
          </div>
        </div>`;
      })
      .join("");
    el.innerHTML = `
      <div class="rounded-lg border border-line p-3 space-y-2">
        <p class="text-[12px] font-semibold text-fg">Jogos sem capa/ícone TWiLight após o lote</p>
        <p class="text-[11px] text-fg-mute">Abra o jogo para buscar online ou escolha um ficheiro. Só TWiLight — não afecta DSPico.</p>
        <div class="space-y-2 max-h-56 overflow-y-auto">${rows}</div>
      </div>`;
    el.querySelectorAll("[data-twl-search]").forEach((btn) => {
      btn.onclick = () => {
        const rel = btn.getAttribute("data-twl-search") || "";
        if (rel) openDrawer(rel);
      };
    });
    el.querySelectorAll("[data-twl-file]").forEach((btn) => {
      btn.onclick = async () => {
        const rel = btn.getAttribute("data-twl-file") || "";
        const kind = btn.getAttribute("data-twl-kind") || "boxart";
        if (!rel) return;
        drawerRel = rel;
        await pickArtwork(kind === "icon" ? "icon" : "boxart");
      };
    });
  }

  async function batchArtwork() {
    if (!mount()) {
      appendLog("Seleccione um cartão SD.", "warn");
      return;
    }
    if (busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.generate_twilight_artwork_batch !== "function") {
        appendLog("API de lote TWiLight indisponível.", "error");
        return;
      }
      setBusy(true, null, {
        op: "generate_twilight_artwork_batch",
        label: "A buscar capas e ícones…",
      });
      appendLog("A buscar capas e ícones TWiLight em lote…", "info");
      const res = await api.generate_twilight_artwork_batch(mount());
      if (res && res.success) {
        appendLog(res.message || "Lote TWiLight concluído.", "success");
        renderTwilightBatchMissing(res.missing || []);
        invalidateCatalog();
        await refresh();
      } else {
        appendLog((res && res.error) || "Falha no lote TWiLight.", "error");
        renderTwilightBatchMissing([]);
      }
    } catch (err) {
      appendLog(`Falha no lote TWiLight: ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function fetchArtwork() {
    if (!drawerRel || !mount()) return;
    if (typeof isHardBusy === "function" ? isHardBusy() : busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.fetch_rom_artwork !== "function") {
        appendLog("API de capas remotas indisponível.", "error");
        return;
      }
      setBusy(true);
      appendLog("A procurar capa e ícone online…", "info");
      const result = await api.fetch_rom_artwork(mount(), drawerRel);
      if (result && result.success) {
        appendLog(result.message || "Arte descarregada.", "success");
        invalidateCatalog();
        await openDrawer(drawerRel);
        await refresh();
      } else {
        appendLog(
          `Arte: ${(result && result.error) || "não encontrada"}`,
          "warn"
        );
        if (drawerData) {
          renderDrawerBody(drawerData, {
            message: (result && result.error) || "Não encontrada.",
            candidates: [],
          });
        }
      }
    } catch (err) {
      appendLog(`Falha ao buscar arte: ${err.message}`, "error");
    } finally {
      setBusy(false);
      artSearching = false;
    }
  }

  async function pickArtwork(kind) {
    if (!drawerRel || !mount()) return;
    if (typeof isHardBusy === "function" ? isHardBusy() : busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    const k = kind === "icon" ? "icon" : "boxart";
    artKind = k;
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.pick_image_file !== "function") {
        appendLog("Diálogo de imagem indisponível.", "error");
        return;
      }
      const picked = await api.pick_image_file();
      if (!picked || !picked.success) {
        appendLog(
          `Erro ao escolher imagem: ${(picked && picked.error) || "falha"}`,
          "error"
        );
        return;
      }
      if (picked.cancelled || !picked.path) return;

      setBusy(true);
      appendLog(
        k === "boxart" ? "A gravar capa…" : "A gravar ícone…",
        "info"
      );
      const result = await api.set_rom_artwork(
        mount(),
        drawerRel,
        k,
        picked.path
      );
      if (result && result.success) {
        appendLog(result.message || "Arte actualizada.", "success");
        invalidateCatalog();
        await openDrawer(drawerRel);
        await refresh();
      } else {
        appendLog(
          `Erro: ${(result && result.error) || "falha ao gravar arte"}`,
          "error"
        );
      }
    } catch (err) {
      appendLog(`Falha na arte: ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  function ensureGlobalBindings() {
    if (escBound) return;
    escBound = true;
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      if (isDeleteSheetOpen()) {
        closeDeleteSheet();
        return;
      }
      if (isDrawerOpen()) {
        closeDrawer();
      }
    });
  }

  function onItemClick(ev) {
    const el = ev.currentTarget;
    const rel = el.getAttribute("data-rel");
    if (!rel) return;
    const multi = ev.metaKey || ev.ctrlKey;
    const range = ev.shiftKey;
    const allRels = (
      isSearching() && Array.isArray(searchHits) ? searchHits : [...dirs, ...files]
    ).map((i) => i.rel_path);

    if (range && lastClickedRel) {
      const a = allRels.indexOf(lastClickedRel);
      const b = allRels.indexOf(rel);
      if (a >= 0 && b >= 0) {
        const [lo, hi] = a < b ? [a, b] : [b, a];
        if (!multi) selection.clear();
        for (let i = lo; i <= hi; i++) selection.add(allRels[i]);
      }
    } else if (multi) {
      if (selection.has(rel)) selection.delete(rel);
      else selection.add(rel);
      lastClickedRel = rel;
    } else {
      selection.clear();
      selection.add(rel);
      lastClickedRel = rel;
    }
    renderGrid();
    if (!multi && !range && el.getAttribute("data-type") !== "dir") {
      openDrawer(rel);
    } else if (!multi && !range) {
      closeDrawer();
    }
  }

  function onItemDblClick(ev) {
    const el = ev.currentTarget;
    const rel = el.getAttribute("data-rel") || "";
    const type = el.getAttribute("data-type");
    if (type === "dir") {
      navigate(rel);
      return;
    }
    if (isSearching() && rel) {
      const parent = rel.includes("/") ? rel.slice(0, rel.lastIndexOf("/")) : "";
      const keep = rel;
      clearSearchUi(false);
      cwd = parent;
      selection = new Set([keep]);
      lastClickedRel = keep;
      refresh();
    }
  }

  function onItemKeyDown(ev) {
    const el = ev.currentTarget;
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      if (ev.key === "Enter" && el.getAttribute("data-type") === "dir") {
        navigate(el.getAttribute("data-rel") || "");
        return;
      }
      if (ev.key === "Enter" && isSearching() && el.getAttribute("data-type") === "file") {
        onItemDblClick(ev);
        return;
      }
      onItemClick(ev);
    } else if (ev.key === "Delete" || ev.key === "Backspace") {
      if (selection.size) openDeleteSheet();
    }
  }

  function selectedFilesOnly() {
    const pool =
      isSearching() && Array.isArray(searchHits) ? searchHits : files;
    return [...selection].filter((rel) =>
      pool.some((f) => f.rel_path === rel && f.type !== "dir")
    );
  }

  function onItemDragStart(ev) {
    hideTip();
    const el = ev.currentTarget;
    if (el.getAttribute("data-type") === "dir") {
      ev.preventDefault();
      return;
    }
    const rel = el.getAttribute("data-rel");
    let payload = selectedFilesOnly();
    if (!payload.includes(rel)) {
      selection.clear();
      selection.add(rel);
      payload = [rel];
      renderGrid();
    }
    dragRels = payload;
    ev.dataTransfer.setData(MIME, JSON.stringify(payload));
    ev.dataTransfer.effectAllowed = "move";
    el.classList.add("rom-x-item--dragging");
  }

  function onItemDragEnd(ev) {
    ev.currentTarget.classList.remove("rom-x-item--dragging");
    dragRels = null;
    clearDropHighlights();
  }

  function clearDropHighlights() {
    dropTargetRel = null;
    document
      .querySelectorAll(".rom-x-item--drop, .rom-x-tree-item--drop, .rom-x-main--drop")
      .forEach((n) => {
        n.classList.remove(
          "rom-x-item--drop",
          "rom-x-tree-item--drop",
          "rom-x-main--drop"
        );
      });
  }

  function onItemDragOver(ev) {
    const el = ev.currentTarget;
    if (el.getAttribute("data-type") !== "dir") return;
    if (!dragRels && !(ev.dataTransfer && ev.dataTransfer.types)) return;
    ev.preventDefault();
    ev.dataTransfer.dropEffect = dragRels ? "move" : "copy";
    el.classList.add("rom-x-item--drop");
  }

  function onItemDragLeave(ev) {
    ev.currentTarget.classList.remove("rom-x-item--drop");
  }

  async function onItemDrop(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const el = ev.currentTarget;
    el.classList.remove("rom-x-item--drop");
    if (el.getAttribute("data-type") !== "dir") return;
    const dest = el.getAttribute("data-rel") || "";
    await handleDropTo(dest, ev);
  }

  function onTreeDragOver(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    ev.currentTarget.classList.add("rom-x-tree-item--drop");
    ev.dataTransfer.dropEffect = dragRels ? "move" : "copy";
  }

  function onTreeDragLeave(ev) {
    ev.currentTarget.classList.remove("rom-x-tree-item--drop");
  }

  async function onTreeDrop(ev) {
    ev.preventDefault();
    ev.stopPropagation();
    const el = ev.currentTarget;
    el.classList.remove("rom-x-tree-item--drop");
    const dest = el.getAttribute("data-rel") || "";
    await handleDropTo(dest, ev);
  }

  function onDragOver(ev) {
    ev.preventDefault();
    const main = document.getElementById("rom-x-main");
    if (main) main.classList.add("rom-x-main--drop");
    ev.dataTransfer.dropEffect = dragRels ? "move" : "copy";
  }

  function onDragLeave(ev) {
    const main = document.getElementById("rom-x-main");
    if (main && !main.contains(ev.relatedTarget)) {
      main.classList.remove("rom-x-main--drop");
    }
  }

  async function onDrop(ev) {
    ev.preventDefault();
    const main = document.getElementById("rom-x-main");
    if (main) main.classList.remove("rom-x-main--drop");
    await handleDropTo(cwd, ev);
  }

  function parseInternalDrag(ev) {
    try {
      const raw = ev.dataTransfer.getData(MIME);
      if (raw) return JSON.parse(raw);
    } catch (_e) {
      /* ignore */
    }
    return dragRels;
  }

  async function handleDropTo(destRel, ev) {
    if (!mount()) {
      alert("Seleccione um cartão SD primeiro.");
      return;
    }
    const internal = parseInternalDrag(ev);
    if (internal && internal.length) {
      await moveSelection(internal, destRel);
      return;
    }
    // Drop do SO: File.path (pywebview) — vários ficheiros / arquivos de uma vez.
    if (ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files.length) {
      const paths = [];
      for (let i = 0; i < ev.dataTransfer.files.length; i++) {
        const f = ev.dataTransfer.files[i];
        if (f && typeof f.path === "string" && f.path) paths.push(f.path);
      }
      if (paths.length) {
        dropTargetRel = destRel;
        await onNativeDrop(paths);
      } else {
        appendLog(
          "Não foi possível ler os caminhos dos ficheiros arrastados. Use Adicionar.",
          "warn"
        );
      }
    }
  }

  async function moveSelection(rels, destRel) {
    if (busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    const filtered = rels.filter((r) => {
      const parent = r.includes("/") ? r.slice(0, r.lastIndexOf("/")) : "";
      return parent !== (destRel || "");
    });
    if (!filtered.length) return;

    setBusy(true);
    appendLog(
      `A mover ${filtered.length} item(ns) ➔ /roms/${destRel || ""}/…`,
      "info"
    );
    try {
      const api = getApi() || (await waitForApi());
      const result = await api.move_roms(mount(), filtered, destRel || "");
      if (result && result.success) {
        appendLog(result.message || "Movidos.", "success");
        selection.clear();
      } else {
        appendLog(
          `Erro: ${(result && result.error) || "falha ao mover"}`,
          "error"
        );
      }
    } catch (err) {
      appendLog(`Falha ao mover: ${err.message}`, "error");
    } finally {
      setBusy(false);
      invalidateCatalog();
      fetchDrives();
      await refresh();
    }
  }

  function closeOverlay(id) {
    const sheet = document.getElementById(id);
    if (sheet) {
      sheet.classList.add("hidden");
      sheet.setAttribute("aria-hidden", "true");
    }
  }

  function openOverlay(id) {
    const sheet = document.getElementById(id);
    if (sheet) {
      sheet.classList.remove("hidden");
      sheet.setAttribute("aria-hidden", "false");
    }
  }

  function askImportConflicts(conflicts) {
    return new Promise((resolve) => {
      const list = document.getElementById("rom-x-conflict-list");
      const count = document.getElementById("rom-x-conflict-count");
      const okBtn = document.getElementById("rom-x-conflict-ok");
      const cancelBtn = document.getElementById("rom-x-conflict-cancel");
      if (!list || !okBtn || !cancelBtn) {
        resolve(null);
        return;
      }
      if (count) {
        count.textContent = `${conflicts.length} jogo(s) já existem no cartão. Escolha o que fazer com cada um.`;
      }
      list.innerHTML = conflicts
        .map((c, i) => {
          const name = escapeHtml(c.display_name || c.src_name || "?");
          const src = escapeHtml(c.src_name || "");
          const existing = (c.existing || [])
            .map(
              (e) =>
                `<li><code>/roms/${escapeHtml(e.rel_path || "")}</code>` +
                (e.size_label
                  ? ` · ${escapeHtml(e.size_label)}`
                  : "") +
                `</li>`
            )
            .join("");
          return (
            `<div class="rom-x-dupe-group" data-idx="${i}">` +
            `<p class="rom-x-dupe-group-title">${name}</p>` +
            `<p class="rom-x-dupe-group-sub">A importar: ${src}</p>` +
            (existing
              ? `<ul class="text-[11px] text-fg-mute mb-2 list-disc pl-4">${existing}</ul>`
              : "") +
            `<div class="rom-x-dupe-choices">` +
            `<label><input type="radio" name="rom-x-cf-${i}" value="replace"> <span><span class="choice-title">Substituir</span> — apaga o(s) do cartão</span></label>` +
            `<label><input type="radio" name="rom-x-cf-${i}" value="keep_both" checked> <span><span class="choice-title">Manter ambos</span> — importa com nome único</span></label>` +
            `<label><input type="radio" name="rom-x-cf-${i}" value="skip"> <span><span class="choice-title">Não importar este</span></span></label>` +
            `</div></div>`
          );
        })
        .join("");

      const finish = (value) => {
        okBtn.removeEventListener("click", onOk);
        cancelBtn.removeEventListener("click", onCancel);
        closeOverlay("rom-x-conflict-sheet");
        resolve(value);
      };
      const onOk = () => {
        const map = {};
        conflicts.forEach((c, i) => {
          const cid = c.conflict_id;
          if (!cid) return;
          const sel = document.querySelector(
            `input[name="rom-x-cf-${i}"]:checked`
          );
          map[cid] = (sel && sel.value) || "keep_both";
        });
        finish(map);
      };
      const onCancel = () => finish(null);
      okBtn.addEventListener("click", onOk);
      cancelBtn.addEventListener("click", onCancel);
      openOverlay("rom-x-conflict-sheet");
    });
  }

  async function importPaths(paths, destRel) {
    if (!mount() || !paths || !paths.length) return;
    if (busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    const dest = destRel != null ? destRel : cwd;
    const layout = layoutChoice();
    const useDest = dest || "";
    const n = paths.length;
    const where = useDest
      ? `/roms/${useDest}/`
      : `layout «${layout}»`;
    if (
      !confirm(
        `Importar ${n} item(ns) (ROMs ou arquivos .zip/.7z/.rar) para ${where}?\n` +
          (useDest
            ? ""
            : "Sem pasta alvo: usa o layout em Conteúdo.\n") +
          `Continuar?`
      )
    ) {
      return;
    }
    setBusy(true, document.getElementById("rom-x-add"));
    appendLog(`A verificar duplicatas…`, "info");
    let resolutions = {};
    try {
      const api = getApi() || (await waitForApi());
      const check = await api.check_rom_import_conflicts(
        mount(),
        paths,
        layout,
        useDest
      );
      if (!check || !check.success) {
        appendLog(
          `Erro: ${(check && check.error) || "falha na verificação"}`,
          "error"
        );
        return;
      }
      if (check.conflicts && check.conflicts.length) {
        setBusy(false);
        const chosen = await askImportConflicts(check.conflicts);
        if (!chosen) {
          appendLog("Importação cancelada.", "warn");
          return;
        }
        resolutions = chosen;
        setBusy(true, document.getElementById("rom-x-add"));
      }
      appendLog(`A importar ${n} ROM(s)…`, "info");
      const result = await api.import_roms(
        mount(),
        paths,
        layout,
        useDest,
        resolutions
      );
      if (result && result.success) {
        appendLog(result.message || "Importação concluída.", "success");
      } else {
        appendLog(
          `Erro: ${(result && result.error) || "falha na importação"}`,
          "error"
        );
      }
    } catch (err) {
      appendLog(`Falha ao importar: ${err.message}`, "error");
    } finally {
      setBusy(false);
      fetchDrives();
      await refresh();
    }
  }

  async function openDupesSheet() {
    if (!mount()) {
      alert("Seleccione um cartão SD primeiro.");
      return;
    }
    if (busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    ensureSheetBindings();
    setBusy(true, document.getElementById("rom-x-dupes"));
    try {
      const api = getApi() || (await waitForApi());
      const data = await api.find_duplicate_roms(mount());
      if (!data || !data.success) {
        appendLog(
          `Erro: ${(data && data.error) || "falha ao procurar duplicatas"}`,
          "error"
        );
        return;
      }
      const groups = data.groups || [];
      if (!groups.length) {
        appendLog("Não há jogos duplicados em /roms/.", "info");
        alert("Não há jogos duplicados no cartão.");
        return;
      }
      const list = document.getElementById("rom-x-dupes-list");
      const count = document.getElementById("rom-x-dupes-count");
      if (count) {
        count.textContent = `${groups.length} grupo(s) — escolha qual manter ou manter ambos.`;
      }
      if (list) {
        list.innerHTML = groups
          .map((g, gi) => {
            const label = escapeHtml(g.label || g.key || "Grupo");
            const items = g.items || [];
            const radios = items
              .map((it, ii) => {
                const rel = escapeHtml(it.rel_path || "");
                const dn = escapeHtml(it.display_name || it.name || rel);
                const checked = ii === 0 ? " checked" : "";
                return (
                  `<label><input type="radio" name="rom-x-dupe-${gi}" value="${rel}"${checked}>` +
                  `<span>${dn}<br><code>/roms/${rel}</code>` +
                  (it.size_label
                    ? ` · ${escapeHtml(it.size_label)}`
                    : "") +
                  `</span></label>`
                );
              })
              .join("");
            return (
              `<div class="rom-x-dupe-group" data-idx="${gi}">` +
              `<p class="rom-x-dupe-group-title">${label}</p>` +
              `<div class="rom-x-dupe-choices">` +
              radios +
              `<label><input type="radio" name="rom-x-dupe-${gi}" value="__keep_both__">` +
              `<span><span class="choice-title">Manter ambos</span></span></label>` +
              `</div></div>`
            );
          })
          .join("");
      }
      openOverlay("rom-x-dupes-sheet");
    } catch (err) {
      appendLog(`Falha ao procurar duplicatas: ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  function closeDupesSheet() {
    closeOverlay("rom-x-dupes-sheet");
  }

  async function confirmDupes() {
    const list = document.getElementById("rom-x-dupes-list");
    if (!list || !mount()) {
      closeDupesSheet();
      return;
    }
    const groups = list.querySelectorAll(".rom-x-dupe-group");
    const toDelete = [];
    groups.forEach((group) => {
      const idx = group.getAttribute("data-idx");
      if (idx == null) return;
      const sel = group.querySelector(
        `input[name="rom-x-dupe-${idx}"]:checked`
      );
      const keep = sel && sel.value;
      if (!keep || keep === "__keep_both__") return;
      group.querySelectorAll(`input[name="rom-x-dupe-${idx}"]`).forEach((inp) => {
        if (inp.value && inp.value !== "__keep_both__" && inp.value !== keep) {
          toDelete.push(inp.value);
        }
      });
    });
    closeDupesSheet();
    if (!toDelete.length) {
      appendLog("Nenhuma duplicata removida (manteve ambos).", "info");
      return;
    }
    if (
      !confirm(
        `Apagar ${toDelete.length} ficheiro(s) duplicado(s) (e saves associados)?`
      )
    ) {
      return;
    }
    setBusy(true, document.getElementById("rom-x-dupes"));
    appendLog(`A remover ${toDelete.length} duplicata(s)…`, "info");
    try {
      const api = getApi() || (await waitForApi());
      const result = await api.delete_roms(
        mount(),
        toDelete,
        "delete",
        "",
        true
      );
      if (result && result.success) {
        appendLog(result.message || "Duplicatas removidas.", "success");
        selection.clear();
      } else {
        appendLog(
          `Erro: ${(result && result.error) || "falha na remoção"}`,
          "error"
        );
      }
    } catch (err) {
      appendLog(`Falha ao remover duplicatas: ${err.message}`, "error");
    } finally {
      setBusy(false);
      fetchDrives();
      invalidateCatalog();
      await refresh();
    }
  }

  async function onNativeDrop(paths) {
    if (!Array.isArray(paths) || !paths.length) return;
    const dest =
      dropTargetRel != null ? dropTargetRel : cwd;
    dropTargetRel = null;
    await importPaths(paths, dest);
  }

  async function addFiles() {
    if (!mount()) {
      alert("Seleccione um cartão SD primeiro.");
      return;
    }
    if (busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    try {
      const api = getApi() || (await waitForApi());
      const picked = await api.pick_rom_files();
      if (!picked || !picked.success) {
        appendLog(
          `Erro ao escolher ficheiros: ${(picked && picked.error) || "falha"}`,
          "error"
        );
        return;
      }
      if (picked.cancelled || !picked.paths || !picked.paths.length) return;
      await importPaths(picked.paths, cwd);
    } catch (err) {
      appendLog(`Falha ao adicionar: ${err.message}`, "error");
    }
  }

  async function mkdir() {
    if (!mount()) {
      alert("Seleccione um cartão SD primeiro.");
      return;
    }
    const name = prompt("Nome da nova pasta:");
    if (!name || !name.trim()) return;
    if (busy) return;
    setBusy(true);
    try {
      const api = getApi() || (await waitForApi());
      const result = await api.mkdir_rom_dir(mount(), cwd, name.trim());
      if (result && result.success) {
        appendLog(result.message || "Pasta criada.", "success");
      } else {
        appendLog(
          `Erro: ${(result && result.error) || "falha ao criar pasta"}`,
          "error"
        );
      }
    } catch (err) {
      appendLog(`Falha: ${err.message}`, "error");
    } finally {
      setBusy(false);
      await refresh();
    }
  }

  function ensureSheetBindings() {
    if (sheetBound) return;
    sheetBound = true;
    ensureGlobalBindings();
    const bindDismiss = (id, closer) => {
      const sheet = document.getElementById(id);
      if (!sheet) return;
      sheet.addEventListener("click", (ev) => {
        if (ev.target === sheet) closer();
      });
    };
    bindDismiss("rom-x-delete-sheet", closeDeleteSheet);
    bindDismiss("rom-x-conflict-sheet", () => closeOverlay("rom-x-conflict-sheet"));
    bindDismiss("rom-x-dupes-sheet", closeDupesSheet);
    const dupesOk = document.getElementById("rom-x-dupes-ok");
    const dupesCancel = document.getElementById("rom-x-dupes-cancel");
    if (dupesOk) dupesOk.addEventListener("click", () => confirmDupes());
    if (dupesCancel) dupesCancel.addEventListener("click", closeDupesSheet);
  }

  function openDeleteSheet() {
    ensureSheetBindings();
    const filesOnly = selectedFilesOnly();
    if (!filesOnly.length) {
      alert("Seleccione pelo menos um jogo (ficheiros, não pastas).");
      return;
    }
    const sheet = document.getElementById("rom-x-delete-sheet");
    const count = document.getElementById("rom-x-sheet-count");
    if (count) {
      count.textContent = `${filesOnly.length} ficheiro(s) serão removidos de /roms/.`;
    }
    if (sheet) {
      sheet.classList.remove("hidden");
      sheet.setAttribute("aria-hidden", "false");
      const focusBtn = sheet.querySelector(".rom-x-sheet-actions .btn-ghost");
      if (focusBtn) focusBtn.focus();
    }
  }

  function closeDeleteSheet() {
    const sheet = document.getElementById("rom-x-delete-sheet");
    if (sheet) {
      sheet.classList.add("hidden");
      sheet.setAttribute("aria-hidden", "true");
    }
  }

  async function confirmDelete() {
    const filesOnly = selectedFilesOnly();
    if (!filesOnly.length) {
      closeDeleteSheet();
      return;
    }
    const saveMode =
      document.querySelector('input[name="rom-x-save-mode"]:checked')?.value ||
      "delete";
    let backupDir = "";
    const api = getApi() || (await waitForApi());

    if (saveMode === "backup") {
      let defaultPath = "~/Desktop/Route1Kit_Saves";
      try {
        const d = await api.default_saves_backup_dir();
        if (d && d.success && d.path) defaultPath = d.path;
      } catch (_e) {
        /* ignore */
      }
      const useCustom = confirm(
        `Backup de saves\n\nOK = escolher pasta\nCancelar = pasta padrão:\n${defaultPath}`
      );
      if (useCustom) {
        const folder = await api.pick_folder();
        if (!folder || !folder.success || folder.cancelled || !folder.path) {
          return;
        }
        backupDir = folder.path;
      } else {
        backupDir = defaultPath;
      }
    }

    closeDeleteSheet();
    setBusy(true, document.getElementById("rom-x-remove"));
    appendLog(`A remover ${filesOnly.length} jogo(s)…`, "info");
    try {
      const result = await api.delete_roms(
        mount(),
        filesOnly,
        saveMode,
        backupDir,
        true
      );
      if (result && result.success) {
        appendLog(result.message || "Remoção concluída.", "success");
        selection.clear();
      } else {
        appendLog(
          `Erro: ${(result && result.error) || "falha na remoção"}`,
          "error"
        );
      }
    } catch (err) {
      appendLog(`Falha ao remover: ${err.message}`, "error");
    } finally {
      setBusy(false);
      fetchDrives();
      await refresh();
    }
  }

  return {
    refresh,
    navigate,
    goUp,
    addFiles,
    mkdir,
    openDeleteSheet,
    closeDeleteSheet,
    confirmDelete,
    openDupesSheet,
    closeDupesSheet,
    confirmDupes,
    onSearchInput,
    onSearchKeyDown,
    clearSearch,
    onItemClick,
    onItemDblClick,
    onItemKeyDown,
    onItemMouseEnter,
    onItemMouseLeave,
    onItemMouseMove,
    openDrawer,
    closeDrawer,
    batchArtwork,
    fetchArtwork,
    pickArtwork,
    onItemDragStart,
    onItemDragEnd,
    onItemDragOver,
    onItemDragLeave,
    onItemDrop,
    onTreeDragOver,
    onTreeDragLeave,
    onTreeDrop,
    onDragOver,
    onDragLeave,
    onDrop,
    onNativeDrop,
    updateRemoveBtn,
  };
})();
