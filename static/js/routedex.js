/**
 * RouteDex — biblioteca nativa do Route Pico para o Pico Launcher.
 * Baseado no PicoDex de rasalopa (MIT): https://github.com/rasalopa/picodex
 * Depende de getApi / waitForApi / escapeHtml / setBusy / isHardBusy / appendLog (app.js).
 */
const RouteDex = (() => {
  // Mesmas abas e na mesma ordem da PicoDex (Library, Covers, Pico Enhanced,
  // Associations, Screenshots, Health), mais Pastas e Cheats do Route Pico.
  const ALL_TABS = [
    ["library", "Biblioteca"],
    ["covers", "Capas"],
    ["stats", "Estatísticas"],
    ["assoc", "Associações"],
    ["shots", "Capturas"],
    ["health", "Saúde do cartão"],
    ["folders", "Pastas"],
    ["cheats", "Cheats"],
  ];
  // Cada tela mostra só as abas dela: a saúde do cartão vive na tela Cartão.
  let TABS = ALL_TABS;
  let view = { title: "RouteDex", intro: "Tudo o que a PicoDex faz, direto no microSD: capas, biblioteca, estatísticas, associações, capturas e saúde do cartão." };
  let tab = "library";
  let filter = "all";
  let query = "";
  let gen = 0;
  let host = null;
  let mountPath = null;
  let overview = null;
  let health = null;
  let healthSel = new Set();
  let folderSel = "";
  let vlist = null;
  // Galeria por sistema (PicoDex SystemGallery) e capas que faltam (CoversView).
  let gallerySystem = null;
  let gallery = null;
  let galleryQuery = "";
  let galleryFilter = { fav: false, done: false };
  let galleryCovers = {};
  let coverSel = new Set();

  const esc = (s) => escapeHtml(String(s == null ? "" : s));

  async function api() {
    return getApi() || (await waitForApi());
  }

  function hardBusy() {
    return typeof isHardBusy === "function" ? isHardBusy() : !!(typeof busy !== "undefined" && busy);
  }

  /** Roda uma escrita no SD com a UI bloqueada; devolve a resposta ou null. */
  async function write(method, args, okMsg) {
    if (hardBusy()) {
      alert("Aguarde a operação em andamento terminar.");
      return null;
    }
    try {
      setBusy(true, null, { op: method, label: "RouteDex…" });
      const a = await api();
      if (!a || typeof a[method] !== "function") {
        alert("Função indisponível nesta build.");
        return null;
      }
      const res = await a[method](mountPath, ...args);
      if (res && res.success) {
        if (okMsg) appendLog(okMsg, "ok");
        return res;
      }
      alert((res && res.error) || "A operação falhou.");
      return res || null;
    } catch (e) {
      alert(e.message || String(e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  function fmtMinutes(min) {
    const m = Number(min) || 0;
    if (m < 60) return `${m} min`;
    const h = Math.floor(m / 60);
    return `${h} h ${String(m % 60).padStart(2, "0")}`;
  }

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    return d.toLocaleString("pt-PT", { dateStyle: "short", timeStyle: "short" });
  }

  function creditHtml() {
    return `<p class="routedex-credit">
      RouteDex é baseado no
      <button type="button" class="routedex-link" data-url="https://github.com/rasalopa/picodex">PicoDex</button>
      de rasalopa (licença MIT). Favoritos, estatísticas e capturas vêm do
      <button type="button" class="routedex-link" data-url="https://github.com/rasalopa/pico-launcher-enhanced">Pico Launcher Enhanced</button>,
      fork do Pico Launcher do LNH team.
    </p>`;
  }

  function bindLinks(root) {
    root.querySelectorAll("[data-url]").forEach((b) => {
      b.onclick = async () => {
        const a = await api();
        const r = a && (await a.open_external_url(b.getAttribute("data-url")));
        if (!(r && r.success)) alert((r && r.error) || "Não foi possível abrir o link.");
      };
    });
  }

  function shell() {
    const tabs = TABS.map(
      ([id, label]) =>
        `<button type="button" class="routedex-tab${tab === id ? " routedex-tab--active" : ""}" data-tab="${id}" role="tab" aria-selected="${
          tab === id
        }">${label}</button>`
    ).join("");
    host.innerHTML = `
      <section class="panel p-5 space-y-4">
        ${
          view.bare
            ? `<div class="flex justify-end"><button type="button" class="btn-ghost !text-[11px]" id="routedex-reload">Ler de novo</button></div>`
            : `<div class="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h3 class="section-label">${esc(view.title)}</h3>
            <p class="text-[12px] text-fg-mute mt-1">${esc(view.intro)}</p>
          </div>
          <button type="button" class="btn-ghost !text-[11px]" id="routedex-reload">Atualizar</button>
        </div>`
        }
        ${TABS.length > 1 ? `<div class="routedex-tabs" role="tablist">${tabs}</div>` : ""}
        <div id="routedex-body"></div>
        ${creditHtml()}
      </section>`;
    host.querySelectorAll(".routedex-tab").forEach((b) => {
      b.onclick = () => {
        if (hardBusy()) return;
        tab = b.getAttribute("data-tab");
        // Como na PicoDex: a aba Biblioteca sempre volta à visão por sistema.
        if (tab === "library") gallerySystem = null;
        draw();
      };
    });
    const reload = host.querySelector("#routedex-reload");
    if (reload) reload.onclick = () => draw(true);
    bindLinks(host);
  }

  function body() {
    return host && host.querySelector("#routedex-body");
  }

  function loading(msg) {
    const b = body();
    if (b) b.innerHTML = `<p class="text-[12px] text-fg-mute">${esc(msg || "Lendo o cartão…")}</p>`;
  }

  function errorHtml(msg) {
    return `<p class="text-[12px] text-danger">${esc(msg || "Falha ao ler o cartão.")}</p>`;
  }

  async function draw(force) {
    const my = ++gen;
    shell();
    if (vlist && vlist.destroy) vlist.destroy();
    vlist = null;
    if (force) {
      overview = null;
      health = null;
      galleryCovers = {};
    }
    if (tab === "library") await drawLibrary(my);
    else if (tab === "covers") await drawCovers(my);
    else if (tab === "stats") await drawStats(my);
    else if (tab === "assoc") await drawAssoc(my);
    else if (tab === "health") await drawHealth(my);
    else if (tab === "shots") await drawShots(my);
    else if (tab === "folders") await drawFolders(my);
    else if (tab === "cheats") await drawCheats(my);
  }

  // ------------------------------------------------------------------ Biblioteca (PicoDex LibraryView + SystemGallery)

  function enhancedNotice(ov) {
    const l = (ov && ov.launcher) || {};
    if (!l.present) {
      return `<div class="note note--warn">Este cartão não tem <code>_picoboot.nds</code>. Prepare o SD primeiro.</div>`;
    }
    if (ov.enhanced) return "";
    return `<div class="note">
      <strong>O launcher oficial não usa favoritos nem estatísticas.</strong> Eles são do
      Pico Launcher Enhanced. Pode marcá-los já aqui; passam a aparecer no DS quando instalar a variante Enhanced
      em <button type="button" class="routedex-link" id="routedex-go-updates">Verificar atualizações</button>.
    </div>`;
  }

  function bindGoUpdates(root) {
    const go = root.querySelector("#routedex-go-updates");
    if (go)
      go.onclick = () => {
        if (!(window.R1K && R1K.shell && R1K.updates)) return;
        R1K.shell.go("dspico", "cartao");
        R1K.updates.check();
      };
  }

  function statTile(label, value) {
    return `<div class="routedex-stat"><span class="stat-label">${esc(label)}</span><span class="stat-value">${esc(value)}</span></div>`;
  }

  const CAP_LABELS = { game_loading: "abre jogos", return_to_launcher: "volta ao launcher", cheats: "cheats" };

  function componentsHtml(lib) {
    const l = lib.launcher || {};
    const ld = lib.loader || {};
    const when = l.updated ? ` · atualizado em ${new Date(l.updated * 1000).toLocaleDateString("pt-BR")}` : "";
    const lname = !l.present ? `<span class="text-danger">Não encontrado</span>` : `${l.variant === "enhanced" ? "Pico Launcher Enhanced" : l.variant === "official" ? "Pico Launcher" : "Launcher não reconhecido"} ${esc(l.version || "")}${l.variant === "enhanced" ? ` <span class="pdx-pill pdx-pill--soft">Enhanced</span>` : ""}<span class="text-fg-mute">${esc(when)}</span>`;
    let lo = `<span class="text-danger">Não encontrado</span>`;
    if (ld.status && ld.status !== "no-loader") {
      const ver = ld.variant === "enhanced" ? `Loader Enhanced ${esc(ld.enhanced_version || "")}` : (ld.candidates || []).length ? esc(ld.candidates[ld.candidates.length - 1]) : "versão não identificada";
      const api = ld.api_version ? ` · instalado (API v${esc(ld.api_version)})` : "";
      const caps = (ld.capabilities || []).map((c) => `<span class="pdx-pill pdx-pill--soft">${esc(CAP_LABELS[c] || c)}</span>`).join(" ");
      lo = `${ver}<span class="text-fg-mute">${api}</span> ${caps}`;
    }
    return `<div class="routedex-kv" aria-label="Componentes do cartão">
      <div><span class="stat-label">Launcher</span><span>${lname}</span></div>
      <div><span class="stat-label">Pico Loader</span><span>${lo}</span></div>
    </div>`;
  }

  async function drawLibrary(my) {
    if (gallerySystem) return drawGallery(my);
    loading("Lendo a biblioteca…");
    let lib;
    try {
      lib = await (await api()).get_routedex_library(mountPath);
    } catch (e) {
      lib = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(lib && lib.success)) {
      b.innerHTML = errorHtml(lib && lib.error);
      return;
    }
    const t = lib.totals || {};
    const cards = (lib.systems || [])
      .map((s) => {
        const pct = s.count ? Math.round((s.covered / s.count) * 100) : 0;
        const shared = (s.shares_folder_with || []).length;
        return `<article class="pdx-sys">
          <header class="pdx-sys-head">
            <h4 class="pdx-sys-name">${esc(s.label)}</h4>
            ${
              s.folder
                ? `<button type="button" class="btn-ghost !px-2 !py-1 pdx-sys-banner" data-banner="${esc(s.folder)}" title="Editar o banner da pasta ${esc(s.folder)} (ícone e nome no launcher)" aria-label="Editar o banner de ${esc(s.label)}"><svg class="ico" aria-hidden="true"><use href="#i-edit"/></svg></button>`
                : ""
            }
          </header>
          <p class="pdx-sys-count">${s.count === 1 ? "1 jogo" : `${s.count} jogos`}${s.has_banner ? ` · <span class="text-fg-mute">com banner</span>` : ""}${shared ? ` · <span class="text-fg-mute">divide a pasta com ${esc(s.shares_folder_with.join(", "))}</span>` : ""}</p>
          <div class="pdx-meter" role="img" aria-label="${s.covered} de ${s.count} com capa"><span style="width:${pct}%"></span></div>
          <p class="pdx-sys-covers">${s.covered}/${s.count} capas</p>
          <button type="button" class="btn-secondary btn-sm" data-system="${esc(s.id)}">Ver jogos</button>
        </article>`;
      })
      .join("");
    b.innerHTML = `
      ${lib.gamedata_problem ? `<div class="note note--warn"><strong>gamedata.json não foi lido.</strong> ${esc(lib.gamedata_problem)}</div>` : ""}
      <div class="routedex-stats">
        ${statTile("Jogos", t.games || 0)}${statTile("Sistemas", t.systems || 0)}${statTile("Favoritos", t.favorites || 0)}${statTile("Tempo de jogo", fmtMinutes(t.minutes || 0))}
      </div>
      ${
        cards
          ? `<div class="pdx-sys-grid">${cards}</div>`
          : `<div class="note">Nenhum jogo no cartão. O Route Pico procura em todas as pastas, exceto <code>/_pico</code>: os jogos podem estar em <code>Games/nds</code>, numa pasta própria ou em qualquer outro lugar. Copie os jogos para o cartão e toque em Atualizar.</div>`
      }
      ${componentsHtml(lib)}`;
    b.querySelectorAll("[data-system]").forEach((btn) => {
      btn.onclick = () => {
        gallerySystem = btn.getAttribute("data-system");
        galleryQuery = "";
        galleryFilter = { fav: false, done: false };
        draw();
      };
    });
    b.querySelectorAll("[data-banner]").forEach((btn) => {
      btn.onclick = () => R1K.picodex.openBannerEditor(mountPath, btn.getAttribute("data-banner"), { onSaved: () => draw(true) });
    });
  }

  function normalize(s) {
    return String(s || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase();
  }

  function galleryItems() {
    const q = normalize(galleryQuery.trim());
    return ((gallery && gallery.games) || []).filter((g) => {
      if (galleryFilter.fav && !g.favorite) return false;
      if (galleryFilter.done && !g.completed) return false;
      if (q && !normalize(g.title).includes(q)) return false;
      return true;
    });
  }

  function cardHtml(g, isNds) {
    const cover = galleryCovers[g.rel];
    const play = g.launchCount || g.playMinutes ? `${g.launchCount}× · ${fmtMinutes(g.playMinutes)}` : "Editar";
    return `<article class="pdx-card" data-rel="${esc(g.rel)}">
      <button type="button" class="pdx-card-cover" data-act="cover" aria-label="Trocar a capa de ${esc(g.title)}" title="Escolher a capa certa">
        ${typeof cover === "string" && cover.startsWith("data:image/") ? `<img src="${cover}" alt="Capa de ${esc(g.title)}" loading="lazy">` : `<span class="pdx-card-empty">${esc(g.title)}</span>`}
        <span class="pdx-card-edit" aria-hidden="true"><svg class="ico"><use href="#i-edit"/></svg></span>
      </button>
      <div class="pdx-card-body">
        <span class="pdx-card-title" title="${esc(g.name)}">${esc(g.title)}</span>
        <div class="pdx-card-actions">
          <button type="button" class="routedex-flag routedex-flag--fav${g.favorite ? " routedex-flag--on" : ""}" data-act="favorite" aria-pressed="${!!g.favorite}" aria-label="Favorito: ${esc(g.title)}" title="${g.favorite ? "Tirar dos favoritos" : "Marcar como favorito"}"><svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M8 13.5S2 10 2 5.9A3 3 0 0 1 8 4.5a3 3 0 0 1 6 1.4C14 10 8 13.5 8 13.5z"/></svg></button>
          <button type="button" class="routedex-flag routedex-flag--done${g.completed ? " routedex-flag--on" : ""}" data-act="completed" aria-pressed="${!!g.completed}" aria-label="Concluído: ${esc(g.title)}" title="${g.completed ? "Desmarcar como concluído" : "Marcar como concluído"}"><svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 4.8"/></svg></button>
          <button type="button" class="pdx-play" data-act="stats" title="Corrigir partidas e tempo de jogo" aria-label="Estatísticas de ${esc(g.title)}">${esc(play)}</button>
          ${isNds ? `<button type="button" class="pdx-play" data-act="compat" title="O que o loader faz com este jogo" aria-label="Compatibilidade de ${esc(g.title)}">Loader</button>` : ""}
        </div>
      </div>
    </article>`;
  }

  function refreshGalleryGrid() {
    const grid = host && host.querySelector("#pdx-gallery");
    if (!grid) return;
    const items = galleryItems();
    const total = ((gallery && gallery.games) || []).length;
    const count = host.querySelector("#pdx-gallery-count");
    if (count) count.textContent = `${items.length} de ${total}`;
    if (!total) {
      grid.innerHTML = `<p class="text-[12px] text-fg-mute">Nenhum jogo de ${esc(gallery.system.label)} neste cartão.</p>`;
      return;
    }
    if (!items.length) {
      grid.innerHTML = `<p class="text-[12px] text-fg-mute">Nenhum jogo corresponde à busca.</p>`;
      return;
    }
    grid.innerHTML = items.map((g) => cardHtml(g, gallery.system.is_nds)).join("");
    grid.querySelectorAll(".pdx-card").forEach((card) => {
      const g = items.find((x) => x.rel === card.getAttribute("data-rel"));
      card.querySelectorAll("[data-act]").forEach((btn) => {
        btn.onclick = () => onCardAction(g, btn.getAttribute("data-act"));
      });
    });
  }

  async function onCardAction(g, act) {
    if (!g) return;
    if (act === "favorite" || act === "completed") {
      const res = await write("toggle_routedex_flag", [g.rel, act]);
      if (res && res.entry) {
        g.favorite = !!res.entry.favorite;
        g.completed = !!res.entry.completed;
        refreshGalleryGrid();
      }
    } else if (act === "stats") {
      R1K.picodex.openStatsEditor(mountPath, g, {
        onSaved: (e) => {
          g.launchCount = Number(e.launchCount) || 0;
          g.playMinutes = Number(e.playMinutes) || 0;
          refreshGalleryGrid();
        },
      });
    } else if (act === "compat") {
      R1K.picodex.openCompat(mountPath, g.rel, g.title);
    } else if (act === "cover") {
      R1K.picodex.openCoverPicker(mountPath, g.rel, {
        onSaved: async () => {
          const r = await (await api()).get_routedex_gallery_covers(mountPath, [g.rel]);
          if (r && r.success) Object.assign(galleryCovers, r.covers || {});
          g.has_cover = !!galleryCovers[g.rel];
          refreshGalleryGrid();
        },
      });
    }
  }

  async function drawGallery(my) {
    loading("Lendo os jogos…");
    const a = await api();
    let gl;
    try {
      gl = await a.get_routedex_gallery(mountPath, gallerySystem);
    } catch (e) {
      gl = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(gl && gl.success)) {
      b.innerHTML = errorHtml(gl && gl.error);
      return;
    }
    gallery = gl;
    const label = gl.system.label;
    b.innerHTML = `
      <div class="pdx-gallery-head">
        <button type="button" class="btn-ghost btn-sm" id="pdx-back">← Biblioteca</button>
        <h4 class="pdx-sys-name">${esc(label)}</h4>
        <span class="text-[11px] text-fg-mute" id="pdx-gallery-count"></span>
      </div>
      <div class="routedex-toolbar">
        <input type="search" id="pdx-gq" class="field-select routedex-input" placeholder="Procurar em ${esc(label)}…" value="${esc(galleryQuery)}" aria-label="Procurar jogos de ${esc(label)}">
        <label class="pdx-radio"><input type="checkbox" id="pdx-gf-fav"${galleryFilter.fav ? " checked" : ""}> Favoritos</label>
        <label class="pdx-radio"><input type="checkbox" id="pdx-gf-done"${galleryFilter.done ? " checked" : ""}> Concluídos</label>
      </div>
      <p class="text-[11px] text-fg-mute" id="pdx-gallery-loading" role="status"></p>
      <div id="pdx-gallery" class="pdx-gallery"></div>`;
    b.querySelector("#pdx-back").onclick = () => {
      gallerySystem = null;
      draw();
    };
    const q = b.querySelector("#pdx-gq");
    q.oninput = () => {
      galleryQuery = q.value;
      refreshGalleryGrid();
    };
    b.querySelector("#pdx-gf-fav").onchange = (e) => {
      galleryFilter.fav = e.target.checked;
      refreshGalleryGrid();
    };
    b.querySelector("#pdx-gf-done").onchange = (e) => {
      galleryFilter.done = e.target.checked;
      refreshGalleryGrid();
    };
    refreshGalleryGrid();
    // Capas em lotes (o cartão pode ter centenas de jogos).
    const want = gl.games.filter((g) => g.has_cover && !(g.rel in galleryCovers)).map((g) => g.rel);
    const status = b.querySelector("#pdx-gallery-loading");
    for (let i = 0; i < want.length; i += 40) {
      if (my !== gen) return;
      if (status) status.textContent = `Carregando capas ${Math.min(i + 40, want.length)}/${want.length}…`;
      const r = await a.get_routedex_gallery_covers(mountPath, want.slice(i, i + 40));
      if (my !== gen) return;
      if (r && r.success) Object.assign(galleryCovers, r.covers || {});
      refreshGalleryGrid();
    }
    if (status) status.textContent = "";
  }

  // ------------------------------------------------------------------ Capas que faltam (CoversView)

  async function drawCovers(my) {
    loading("Procurando jogos sem capa…");
    let r;
    try {
      r = await (await api()).get_missing_covers(mountPath);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(r && r.success)) {
      b.innerHTML = errorHtml(r && r.error);
      return;
    }
    const intro = `<p class="text-[12px] text-fg-mute">Encontra os jogos do cartão sem capa e baixa as capas do catálogo libretro-thumbnails. Só entra a capa certa do jogo: quando não há um par exato, o jogo fica sem capa em vez de ganhar a de outro. As capas vão direto para o cartão, prontas para o launcher. Ícones não são trocados.</p>`;
    if (!r.total) {
      b.innerHTML = intro + `<div class="note">Nenhum jogo neste cartão.</div>`;
      return;
    }
    if (!r.missing.length) {
      b.innerHTML = intro + `<div class="note note--ok">${r.total === 1 ? "O seu jogo já tem capa." : `Todos os ${r.total} jogos já têm capa.`}</div>`;
      return;
    }
    coverSel = new Set(r.missing.map((m) => m.rel));
    const rows = r.missing
      .map(
        (m) => `<label class="pdx-miss">
          <input type="checkbox" data-rel="${esc(m.rel)}" checked>
          <span class="pdx-miss-name" title="${esc(m.rel)}">${esc(m.title)}</span>
          <span class="routedex-sys">${esc(m.system_label)}</span>
          ${m.no_gamecode ? `<span class="pdx-hint" title="Sem código de jogo, a capa vai pelo nome do arquivo: renomear o arquivo perde a capa.">sem código</span>` : ""}
          <span class="pdx-miss-status" data-status="${esc(m.rel)}"></span>
        </label>`
      )
      .join("");
    b.innerHTML = `${intro}
      <div class="routedex-toolbar">
        <strong class="text-[13px]">Faltam capas</strong>
        <button type="button" class="btn-ghost btn-sm" id="pdx-sel-all">Selecionar todos</button>
        <button type="button" class="btn-ghost btn-sm" id="pdx-sel-none">Nenhum</button>
        <span class="flex-1"></span>
        <button type="button" class="btn-primary" id="pdx-fetch"></button>
      </div>
      <p class="text-[12px] text-fg-mute" id="pdx-fetch-msg" role="status" aria-live="polite"></p>
      <div class="pdx-miss-list">${rows}</div>
      <p class="pdx-hint">Para um jogo que ficou sem capa, escolha uma à mão pelo lápis na capa, em Biblioteca.</p>`;
    const btn = b.querySelector("#pdx-fetch");
    const label = () => {
      btn.textContent = coverSel.size === 1 ? "Buscar 1 capa" : `Buscar ${coverSel.size} capas`;
      btn.disabled = !coverSel.size;
    };
    label();
    b.querySelectorAll(".pdx-miss input").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) coverSel.add(cb.dataset.rel);
        else coverSel.delete(cb.dataset.rel);
        label();
      };
    });
    const setAll = (on) => {
      b.querySelectorAll(".pdx-miss input").forEach((cb) => {
        cb.checked = on;
        if (on) coverSel.add(cb.dataset.rel);
        else coverSel.delete(cb.dataset.rel);
      });
      label();
    };
    b.querySelector("#pdx-sel-all").onclick = () => setAll(true);
    b.querySelector("#pdx-sel-none").onclick = () => setAll(false);
    btn.onclick = async () => {
      const rels = [...coverSel];
      b.querySelector("#pdx-fetch-msg").textContent = `Buscando capas para ${rels.length} jogo(s)…`;
      const res = await write("fetch_missing_covers", [rels]);
      if (!res) return;
      const LABEL = { written: "Gravada", "no-match": "Sem par no catálogo", error: "Falhou" };
      (res.results || []).forEach((x) => {
        const cell = b.querySelector(`[data-status="${CSS.escape(x.rel)}"]`);
        if (!cell) return;
        cell.innerHTML = `${x.preview ? `<img class="pdx-miss-thumb" src="${x.preview}" alt="Capa gravada">` : ""}<span class="${x.status === "written" ? "text-ok" : x.status === "error" ? "text-danger" : "text-fg-mute"}">${esc(LABEL[x.status] || x.status)}${x.via_banner ? " · pelo nome gravado no jogo" : ""}${x.error ? ` (${esc(x.error)})` : ""}</span>`;
      });
      b.querySelector("#pdx-fetch-msg").textContent = res.cancelled
        ? `Cancelado: ${res.written} gravada(s).`
        : `Pronto: ${res.written} gravada(s) · ${res.no_match} sem par · ${res.failed} com falha.`;
      galleryCovers = {};
    };
  }

  // ------------------------------------------------------------------ Associações (AssociationsView)

  async function drawAssoc(my) {
    loading("Lendo o settings.json…");
    if (!(window.R1K && R1K.picodex)) return;
    const el = body();
    if (my !== gen || !el) return;
    await R1K.picodex.renderAssociations(el, mountPath, { bare: true });
  }

  // ------------------------------------------------------------------ Estatísticas (StatsView)

  async function drawStats(my) {
    loading();
    const a = await api();
    let st;
    try {
      st = await a.get_routedex_stats(mountPath);
    } catch (e) {
      st = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(st && st.success)) {
      b.innerHTML = errorHtml(st && st.error);
      return;
    }
    const t = st.totals || {};
    const thumb = (name) => `<span class="pdx-stat-thumb" data-cover="${esc(name)}"></span>`;
    const table = (rows, cols) =>
      rows.length
        ? `<table class="pdx-table"><thead><tr><th>Jogo</th>${cols.map((c) => `<th class="text-right">${c[0]}</th>`).join("")}</tr></thead><tbody>${rows
            .map((e) => `<tr><td><span class="pdx-stat-game">${thumb(e.fileName)}<span>${esc(e.fileName.replace(/\.[^.]+$/, ""))}</span></span></td>${cols.map((c) => `<td class="text-right text-fg-mute">${esc(c[1](e))}</td>`).join("")}</tr>`)
            .join("")}</tbody></table>`
        : `<p class="text-[12px] text-fg-mute">Nenhum jogo foi aberto ainda.</p>`;
    const favs = st.favorites || [];
    b.innerHTML = `
      ${st.parse_error ? `<div class="note note--warn"><strong>gamedata.json não foi lido.</strong> ${esc(st.parse_error)}</div>` : ""}
      ${enhancedNotice(st)}
      ${
        !t.launches && !favs.length
          ? `<div class="note"><strong>Ainda não há estatísticas.</strong> O Pico Launcher Enhanced registra as partidas, o tempo de jogo e os favoritos de cada jogo. Abra algo pelo launcher e ele aparece aqui.</div>`
          : ""
      }
      <div class="routedex-stats">
        ${statTile("Jogos jogados", t.played || 0)}${statTile("Favoritos", t.favorites || 0)}${statTile("Concluídos", t.completed || 0)}${statTile("Partidas", t.launches || 0)}${statTile("Tempo total", fmtMinutes(t.minutes || 0))}
      </div>
      <div class="routedex-cols">
        <div><h4 class="routedex-h">Mais jogados</h4>${table(st.top || [], [["Partidas", (e) => `${e.launchCount}×`], ["Tempo", (e) => fmtMinutes(e.playMinutes)]])}</div>
        <div><h4 class="routedex-h">Jogados recentemente</h4>${table(st.recent || [], [["Quando", (e) => fmtDate(e.lastPlayed)]])}</div>
      </div>
      <h4 class="routedex-h">Favoritos</h4>
      ${
        favs.length
          ? `<div class="pdx-fav-row">${favs.map((f) => `<div class="pdx-fav">${thumb(f.fileName)}<span>${esc(f.fileName.replace(/\.[^.]+$/, ""))}</span></div>`).join("")}</div>`
          : `<p class="text-[12px] text-fg-mute">Ainda não há favoritos. No launcher, aperte X num jogo para marcar.</p>`
      }
      <div id="pdx-stale"></div>`;
    bindGoUpdates(b);
    const names = [...new Set([...(st.top || []), ...(st.recent || []), ...favs].map((e) => e.fileName))];
    if (names.length) {
      const r = await a.get_routedex_covers_by_name(mountPath, names);
      if (my !== gen) return;
      const covers = (r && r.covers) || {};
      b.querySelectorAll("[data-cover]").forEach((el) => {
        const u = covers[el.getAttribute("data-cover")];
        if (typeof u === "string" && u.startsWith("data:image/")) el.innerHTML = `<img src="${u}" alt="">`;
      });
    }
    // Entradas de jogos que saíram do cartão (limpeza do gamedata.json).
    let ov = null;
    try {
      ov = await a.get_routedex_overview(mountPath);
    } catch (_e) {
      ov = null;
    }
    if (my !== gen || !(ov && ov.success)) return;
    const stale = ov.stale || [];
    const box = b.querySelector("#pdx-stale");
    if (stale.length && box) {
      box.innerHTML = `<div class="note mt-3"><strong>${stale.length} entrada(s) de jogos que não estão mais no cartão.</strong>
        <span class="text-fg-mute">${esc(stale.slice(0, 5).map((e) => e.fileName).join(", "))}${stale.length > 5 ? "…" : ""}</span>
        <div class="mt-2"><button type="button" class="btn-ghost btn-sm" id="routedex-prune">Remover entradas órfãs</button></div></div>`;
      box.querySelector("#routedex-prune").onclick = async () => {
        if (!confirm(`Remover ${stale.length} entrada(s) do gamedata.json?\n\nUma cópia do arquivo fica no computador.`)) return;
        const res = await write("prune_routedex_entries", [stale.map((e) => e.fileName)], "Entradas órfãs removidas.");
        if (res) draw(true);
      };
    }
  }

  // ------------------------------------------------------------------ Saúde

  function loaderLine(ld) {
    if (!ld) return "";
    const s = ld.status;
    const variant = ld.variant === "enhanced" ? ` + Loader Enhanced ${esc(ld.enhanced_version || "")}` : "";
    if (s === "no-loader") return `<span class="text-danger">Sem Pico Loader em /_pico.</span>`;
    if (s === "mixed")
      return `<span class="text-warn">Arquivos de releases diferentes (mais próximo: ${esc(
        ld.mismatch && ld.mismatch.best_fit
      )}; fora: ${esc(((ld.mismatch && ld.mismatch.odd_ones_out) || []).join(", "))}).</span>`;
    if (s === "unrecognised") return `<span class="text-warn">Versão não reconhecida (build própria ou release mais nova que esta app).</span>`;
    const cands = ld.candidates || [];
    const ver = cands.length ? cands[cands.length - 1] : "";
    // Com o Loader Enhanced, a versão oficial identificada é a base do fork, não algo a atualizar.
    const behind =
      ld.variant === "enhanced"
        ? " · base oficial do fork"
        : ld.releases_behind
          ? ` · ${ld.releases_behind} release(s) atrás de ${esc(ld.latest_known)}`
          : " · em dia";
    const builds = (ld.builds || []).length ? ` · build ${esc(ld.builds.join("/"))}` : "";
    const src = ld.source && ld.source.tag ? ` · dados PicoDex ${esc(ld.source.tag)}` : "";
    const api = ld.api_version ? ` · API v${esc(ld.api_version)} (${(ld.capabilities || []).map((c) => CAP_LABELS[c] || c).join(", ")})` : "";
    return `<span class="text-ok">Pico Loader ${esc(ver)}</span>${variant}<span class="text-fg-mute">${cands.length ? behind : ""}${builds}${api}${src}</span>`;
  }

  function launcherLine(l) {
    if (!l || !l.present) return `<span class="text-danger">Sem /_picoboot.nds.</span>`;
    const name = l.variant === "enhanced" ? "Pico Launcher Enhanced" : l.variant === "official" ? "Pico Launcher (oficial)" : "Launcher não reconhecido";
    return `<span class="${l.variant === "unknown" ? "text-warn" : "text-ok"}">${name}</span> <span class="text-fg-mute">${esc(l.version || "")}</span>`;
  }

  function checkList(title, items, kind) {
    if (!items.length) return "";
    const rows = items
      .map(
        (rel) =>
          `<label class="routedex-check"><input type="checkbox" data-rel="${esc(rel)}" ${healthSel.has(rel) ? "checked" : ""}><span class="truncate">${esc(
            rel
          )}</span></label>`
      )
      .join("");
    return `<div class="routedex-group"><h4 class="routedex-h">${esc(title)} <span class="text-fg-mute">(${items.length})</span>
      <button type="button" class="btn-ghost !text-[11px]" data-selall="${kind}">Selecionar todos</button></h4>
      <div class="routedex-checks" data-kind="${kind}">${rows}</div></div>`;
  }

  async function drawHealth(my) {
    loading("Verificando o cartão…");
    let h;
    try {
      h = await (await api()).check_routedex_health(mountPath);
    } catch (e) {
      h = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(h && h.success)) {
      b.innerHTML = errorHtml(h && h.error);
      return;
    }
    health = h;
    // Como a PicoDex: só ._* e .DS_Store são lixo a limpar; as pastas que o
    // macOS recria (.Trashes, .Spotlight-V100, .fseventsd) aparecem como aviso.
    healthSel = new Set([...healthSel].filter((r) => h.orphan_saves.includes(r) || h.orphan_art.includes(r)));
    const problems = (h.problems || []).map((p) => `<li>${esc(p)}</li>`).join("");
    const dups = (h.duplicate_saves || [])
      .map((d) => `<li><code>${esc(d.beside)}</code> e <code>${esc(d.in_folder)}</code></li>`)
      .join("");
    const removable = h.orphan_saves.length + h.orphan_art.length;
    const macDirs = (h.macos_dirs || []).filter((d) => !d.kept).map((d) => d.rel);
    const keptFsevents = (h.macos_dirs || []).some((d) => d.kept);
    const badArt = [...(h.cover_problems || []).map((x) => ({ ...x, kind: "Capa" })), ...(h.icon_problems || []).map((x) => ({ ...x, kind: "Ícone" }))];
    b.innerHTML = `
      <div class="routedex-kv">
        <div><span class="stat-label">Launcher</span><span>${launcherLine(h.launcher)}</span></div>
        <div><span class="stat-label">Loader</span><span>${loaderLine(h.loader)}</span></div>
        <div><span class="stat-label">Biblioteca</span><span>${esc(h.games_count)} jogo(s) · ${esc(h.saves_count)} save(s)</span></div>
        ${
          h.missing_optional.length
            ? `<div><span class="stat-label">Opcionais ausentes</span><span class="text-fg-mute">${esc(h.missing_optional.join(", "))}</span></div>`
            : ""
        }
      </div>
      ${problems ? `<div class="note note--warn"><strong>Para corrigir</strong><ul class="routedex-ul">${problems}</ul></div>` : `<div class="note note--ok">Nenhum problema que impeça a inicialização.</div>`}
      ${
        dups
          ? `<div class="note"><strong>Saves duplicados</strong> (ao lado da ROM e em <code>saves/</code>). Com <code>"saveLocation": "saves"</code> o launcher usa o da pasta <code>saves/</code>; confira qual é o mais recente antes de apagar o outro.<ul class="routedex-ul">${dups}</ul></div>`
          : ""
      }
      ${
        h.junk.length
          ? `<div class="note flex flex-wrap items-center justify-between gap-2"><span>${h.junk.length === 1 ? "1 arquivo deixado" : `${h.junk.length} arquivos deixados`} pelo macOS (<code>._*</code> e <code>.DS_Store</code>). Podem ser apagados sem problema: aparecem no launcher como jogos quebrados.</span><button type="button" class="btn-ghost btn-sm" id="routedex-clean-junk">Limpar ${h.junk.length === 1 ? "1 arquivo" : `${h.junk.length} arquivos`}</button></div>`
          : `<div class="note note--ok">Nenhum arquivo de lixo do macOS.</div>`
      }
      ${
        macDirs.length
          ? `<p class="text-[11px] text-fg-mute">O macOS mantém ${macDirs.map((d) => `<code>${esc(d)}</code>`).join(", ")} no cartão e recria essas pastas toda vez que o cartão é ligado num Mac. Elas não atrapalham o launcher, então podem ficar. (A <code>.Trashes</code> é a lixeira do cartão e pode guardar arquivos apagados.)</p>`
          : ""
      }
      ${keptFsevents ? `<p class="text-[11px] text-fg-mute"><code>.fseventsd</code> só tem um arquivo <code>no_log</code>, que impede o macOS de registrar as mudanças no cartão. Deixe como está.</p>` : ""}
      ${
        badArt.length
          ? `<div class="note note--warn"><strong>${badArt.length === 1 ? "1 imagem que o launcher não mostra" : `${badArt.length} imagens que o launcher não mostra`}</strong>
              <p class="text-[12px] mt-1">${badArt.length === 1 ? "Ela não está" : "Elas não estão"} no formato que o launcher lê: no console, uma capa assim aparece como ruído ou some, e um ícone aparece em branco. Isso costuma vir de salvar a imagem num editor. Abra o jogo em RouteDex → Biblioteca e salve a capa de novo: o Route Pico grava no formato certo.</p>
              <ul class="routedex-ul">${badArt.map((x) => `<li>${esc(x.kind)} <code>${esc(x.rel)}</code> <span class="text-fg-mute">${esc(x.reason)}</span></li>`).join("")}</ul></div>`
          : ""
      }
      ${checkList("Saves sem jogo", h.orphan_saves, "saves")}
      ${checkList("Capas/ícones sem jogo", h.orphan_art, "art")}
      ${
        removable
          ? `<div class="flex items-center gap-3 flex-wrap mt-2">
              <button type="button" class="btn-primary" id="routedex-remove">Remover selecionados</button>
              <span class="text-[11px] text-fg-mute">Cada arquivo é copiado para o computador antes de sair do cartão.</span>
            </div>`
          : ""
      }`;
    b.querySelectorAll(".routedex-checks input[type=checkbox]").forEach((cb) => {
      cb.onchange = () => {
        const rel = cb.getAttribute("data-rel");
        if (cb.checked) healthSel.add(rel);
        else healthSel.delete(rel);
      };
    });
    b.querySelectorAll("[data-goto]").forEach((btn) => {
      btn.onclick = () => {
        const [v, sec] = btn.getAttribute("data-goto").split(":");
        if (window.R1K && R1K.shell) R1K.shell.go(v, sec);
      };
    });
    b.querySelectorAll("[data-selall]").forEach((btn) => {
      btn.onclick = () => {
        const box = b.querySelector(`.routedex-checks[data-kind="${btn.getAttribute("data-selall")}"]`);
        box.querySelectorAll("input[type=checkbox]").forEach((cb) => {
          cb.checked = true;
          healthSel.add(cb.getAttribute("data-rel"));
        });
      };
    });
    const cj = b.querySelector("#routedex-clean-junk");
    if (cj)
      cj.onclick = async () => {
        if (!confirm(`Apagar ${h.junk.length} arquivo(s) ._* e .DS_Store do cartão?\n\nFica uma cópia no computador.`)) return;
        const res = await write("remove_routedex_items", [h.junk], "Lixo do macOS removido.");
        if (res) draw();
      };
    const rm = b.querySelector("#routedex-remove");
    if (rm)
      rm.onclick = async () => {
        const rels = [...healthSel];
        if (!rels.length) {
          alert("Selecione os itens a remover.");
          return;
        }
        const saves = rels.filter((r) => h.orphan_saves.includes(r)).length;
        const warn = saves ? `\n\n${saves} save(s) sem jogo: confirme que não são de um jogo que vai voltar a copiar.` : "";
        if (!confirm(`Remover ${rels.length} item(ns) do cartão?${warn}\n\nFica uma cópia no computador.`)) return;
        const res = await write("remove_routedex_items", [rels], "Itens removidos do cartão.");
        if (res) {
          healthSel.clear();
          overview = null;
          draw();
        }
      };
  }

  // ------------------------------------------------------------------ Capturas

  async function drawShots(my) {
    loading();
    let r;
    try {
      r = await (await api()).list_routedex_screenshots(mountPath);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(r && r.success)) {
      b.innerHTML = errorHtml(r && r.error);
      return;
    }
    const shots = r.shots || [];
    if (!shots.length) {
      b.innerHTML = `<div class="note">Sem capturas em <code>/_pico/screenshots</code>. No Pico Launcher Enhanced, segure START durante meio segundo para gravar as duas telas.</div>`;
      return;
    }
    b.innerHTML = `
      <p class="text-[12px] text-fg-mute">${shots.length} captura(s). As duas telas aparecem empilhadas em uma só imagem.</p>
      <div class="routedex-shots">${shots
        .map(
          (s) => `<figure class="routedex-shot" data-id="${esc(s.id)}">
            <div class="routedex-shot-img"><span class="text-[11px] text-fg-mute">carregando…</span></div>
            <figcaption>
              <span>${s.number != null ? `#${esc(s.number)}` : esc(s.id)}</span>
              <span class="flex gap-1">
                <button type="button" class="btn-ghost !text-[11px]" data-act="save">Salvar PNG</button>
                <button type="button" class="btn-ghost btn-ghost--muted !text-[11px]" data-act="del">Apagar</button>
              </span>
            </figcaption>
          </figure>`
        )
        .join("")}</div>`;
    const a = await api();
    for (const fig of b.querySelectorAll(".routedex-shot")) {
      const id = fig.getAttribute("data-id");
      fig.querySelector('[data-act="save"]').onclick = async () => {
        const res = await a.export_routedex_screenshot(mountPath, id);
        if (res && res.success && !res.cancelled) appendLog(`Captura salva em ${res.path}`, "ok");
        else if (res && !res.success) alert(res.error || "Falha ao salvar.");
      };
      fig.querySelector('[data-act="del"]').onclick = async () => {
        if (!confirm("Apagar esta captura do cartão? Fica uma cópia no computador.")) return;
        const res = await write("delete_routedex_screenshot", [id], "Captura apagada.");
        if (res) draw();
      };
    }
    // Pré-visualizações em série: não ocupa o cartão com leituras paralelas.
    for (const fig of b.querySelectorAll(".routedex-shot")) {
      if (my !== gen) return;
      const res = await a.get_routedex_screenshot(mountPath, fig.getAttribute("data-id"));
      const box = fig.querySelector(".routedex-shot-img");
      if (res && res.success && typeof res.image === "string" && res.image.startsWith("data:image/png;base64,")) {
        const img = document.createElement("img");
        img.src = res.image;
        img.alt = "Captura do DS";
        img.loading = "lazy";
        box.innerHTML = "";
        box.appendChild(img);
      } else {
        box.innerHTML = `<span class="text-[11px] text-danger">não foi possível ler</span>`;
      }
    }
  }

  // ------------------------------------------------------------------ Pastas

  function folderOptions() {
    const dirs = new Set();
    ((overview && overview.library) || []).forEach((g) => {
      let d = g.dir;
      while (d) {
        dirs.add(d);
        const i = d.lastIndexOf("/");
        d = i > 0 ? d.slice(0, i) : "";
      }
    });
    return [...dirs].sort((x, y) => x.localeCompare(y, "pt"));
  }

  async function drawFolders(my) {
    loading();
    if (!overview) {
      try {
        const ov = await (await api()).get_routedex_overview(mountPath);
        if (ov && ov.success) overview = ov;
      } catch (_e) {
        /* sem lista: mostra erro abaixo */
      }
    }
    if (my !== gen) return;
    const b = body();
    const dirs = folderOptions();
    if (!dirs.length) {
      b.innerHTML = `<div class="note">Nenhuma pasta com jogos no cartão.</div>`;
      return;
    }
    if (!dirs.includes(folderSel)) folderSel = dirs[0];
    b.innerHTML = `
      <p class="text-[12px] text-fg-mute">Cada pasta pode ter um <code>banner.bnr</code> (ícone e nome mostrado no launcher), um <code>icon.bmp</code> e uma <code>cover.bmp</code>. O nome real da pasta no cartão não muda.</p>
      <div class="routedex-toolbar">
        <select id="routedex-folder" class="field-select" aria-label="Pasta">${dirs
          .map((d) => `<option value="${esc(d)}"${d === folderSel ? " selected" : ""}>${esc(d)}</option>`)
          .join("")}</select>
      </div>
      <div id="routedex-folder-detail"></div>`;
    b.querySelector("#routedex-folder").onchange = (ev) => {
      folderSel = ev.target.value;
      drawFolderDetail(my);
    };
    await drawFolderDetail(my);
  }

  async function drawFolderDetail(my) {
    const box = host.querySelector("#routedex-folder-detail");
    if (!box) return;
    box.innerHTML = `<p class="text-[12px] text-fg-mute">Lendo a pasta…</p>`;
    const a = await api();
    const st = await a.get_routedex_folder_art(mountPath, folderSel);
    if (my !== gen) return;
    if (!(st && st.success)) {
      box.innerHTML = errorHtml(st && st.error);
      return;
    }
    const name = folderSel.split("/").pop();
    const bn = st.banner;
    const icon = bn && typeof bn.icon === "string" && bn.icon.startsWith("data:image/png") ? `<img class="routedex-icon" src="${bn.icon}" alt="">` : `<div class="routedex-icon routedex-icon--empty"></div>`;
    const cover = typeof st.cover === "string" && st.cover.startsWith("data:image/png") ? `<img class="routedex-cover" src="${st.cover}" alt="">` : `<div class="routedex-cover routedex-cover--empty">sem capa</div>`;
    box.innerHTML = `
      <div class="routedex-folder">
        <div class="routedex-folder-preview">${icon}<div>
          <div class="text-[13px] text-fg">${esc(bn ? bn.title : name)}</div>
          <div class="text-[11px] text-fg-mute">${bn ? (bn.crc_ok ? "banner.bnr" : "banner.bnr com CRC inválido") : "sem banner"}${st.icon ? " · icon.bmp" : ""}</div>
        </div>${cover}</div>
        <div class="routedex-form">
          <p class="text-[12px] text-fg-mute">O banner troca o ícone e o nome que o launcher mostra para a pasta; o nome real da pasta no cartão não muda. Precisa de um Pico Launcher mais novo que a v1.3.0.</p>
          <div class="flex gap-2 flex-wrap">
            <button type="button" class="btn-primary" id="routedex-banner-edit">${bn ? "Editar banner" : "Criar banner"}</button>
            <button type="button" class="btn-ghost" id="routedex-cover-save">Escolher capa da pasta…</button>
            ${st.cover ? `<button type="button" class="btn-ghost btn-ghost--muted" data-rm="cover">Remover capa</button>` : ""}
          </div>
        </div>
      </div>`;
    box.querySelector("#routedex-banner-edit").onclick = () =>
      R1K.picodex.openBannerEditor(mountPath, folderSel, { onSaved: () => drawFolderDetail(gen) });
    box.querySelector("#routedex-cover-save").onclick = async () => {
      const p = await a.pick_image_file();
      if (!p || !p.success || p.cancelled) return;
      const res = await write("write_routedex_folder_cover", [folderSel, p.path], `Capa gravada em ${folderSel}.`);
      if (res) drawFolderDetail(gen);
    };
    box.querySelectorAll("[data-rm]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Remover do cartão? Fica uma cópia no computador.")) return;
        const res = await write("remove_routedex_folder_art", [folderSel, btn.getAttribute("data-rm")]);
        if (res) drawFolderDetail(gen);
      };
    });
  }

  // ------------------------------------------------------------------ Fundos noturnos

  /** Fundos noturnos (*_night.bin), mostrados em DSPico → Launcher. */
  async function renderNight(m, el) {
    if (!el) return;
    const card = (inner) => `<section class="panel p-5 space-y-3"><h3 class="section-label">Fundos noturnos</h3>${inner}</section>`;
    el.innerHTML = card('<p class="text-[12px] text-fg-mute">Lendo temas…</p>');
    const a = await api();
    let r;
    try {
      r = await a.list_routedex_night_themes(m);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (!(r && r.success)) {
      el.innerHTML = card(errorHtml(r && r.error));
      return;
    }
    const prevMount = mountPath;
    mountPath = m;
    const enhanced = overview && prevMount === m ? overview.enhanced : null;
    const themes = r.themes || [];
    const b = el;
    b.innerHTML = card(`
      <div class="note">O Pico Launcher Enhanced usa <code>topbg_night.bin</code> e <code>bottombg_night.bin</code> de um tema das 20:00 às 6:59, conferido ao iniciar. As cores são escurecidas e arrefecidas com a mesma fórmula do <code>make_night_bg.py</code> do Enhanced.${
        enhanced === false ? " <strong>O launcher oficial ignora estes arquivos.</strong>" : ""
      }</div>
      ${
        themes.length
          ? `<div class="routedex-list">${themes
              .map((t) => {
                const has = t.night.topbg || t.night.bottombg;
                return `<div class="routedex-row">
                  <span class="routedex-name">${esc(t.folder)}${t.builtin ? ' <span class="text-fg-mute">(incluído no launcher)</span>' : ""}</span>
                  <span class="routedex-meta">${has ? "versão noturna presente" : "sem versão noturna"}</span>
                  <button type="button" class="btn-ghost !text-[11px]" data-gen="${esc(t.folder)}">${has ? "Regerar" : "Gerar"}</button>
                  ${has ? `<button type="button" class="btn-ghost btn-ghost--muted !text-[11px]" data-rm="${esc(t.folder)}">Remover</button>` : ""}
                </div>`;
              })
              .join("")}</div>`
          : `<p class="text-[12px] text-fg-mute">Nenhum tema com <code>topbg.bin</code>/<code>bottombg.bin</code> em <code>/_pico/themes</code>.</p>`
      }`);
    b.querySelectorAll("[data-gen]").forEach((btn) => {
      btn.onclick = async () => {
        const t = btn.getAttribute("data-gen");
        const res = await write("generate_routedex_night_backgrounds", [t], `Fundos noturnos gerados: ${t}.`);
        if (res) renderNight(m, el);
      };
    });
    b.querySelectorAll("[data-rm]").forEach((btn) => {
      btn.onclick = async () => {
        const res = await write("remove_routedex_night_backgrounds", [btn.getAttribute("data-rm")], "Fundos noturnos removidos.");
        if (res) renderNight(m, el);
      };
    });
  }

  // ------------------------------------------------------------------ Cheats

  async function drawCheats(my) {
    loading();
    const a = await api();
    let r;
    try {
      r = await a.get_routedex_cheats(mountPath);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(r && r.success)) {
      b.innerHTML = errorHtml(r && r.error);
      return;
    }
    let state;
    if (!r.present) state = `<div class="note">Sem <code>/_pico/usrcheat.dat</code> no cartão.</div>`;
    else if (!r.valid) state = `<div class="note note--warn"><strong>usrcheat.dat inválido.</strong> ${esc(r.error)}</div>`;
    else
      state = `<div class="note note--ok"><strong>${esc(r.name || "Base de cheats")}</strong> · ${esc(r.games)} jogos na base ·
        ${esc(r.card_games_with_cheats)} de ${esc(r.card_nds_games)} jogos DS deste cartão têm cheats.</div>`;
    b.innerHTML = `
      ${state}
      <p class="text-[12px] text-fg-mute leading-relaxed">O Pico Launcher lê os cheats de <code>/_pico/usrcheat.dat</code> (no DS: Y sobre um jogo).
      Não existe uma fonte oficial com versão fixa para esta base, por isso o Route Pico não a baixa: escolha um
      <code>usrcheat.dat</code> que já tenha. O arquivo é validado (cabeçalho <code>R4 CheatCode</code>) antes de ir para o cartão,
      e o anterior fica salvo no computador.</p>
      <button type="button" class="btn-primary" id="routedex-cheats-import">Importar usrcheat.dat…</button>`;
    b.querySelector("#routedex-cheats-import").onclick = async () => {
      const p = await a.pick_usrcheat_file();
      if (!p || !p.success || p.cancelled) return;
      const res = await write("import_routedex_cheats", [p.path], "Base de cheats instalada.");
      if (res) draw();
    };
  }

  // ------------------------------------------------------------------ API pública

  /**
   * opts.only: ids das abas desta tela (padrão: todas); opts.title / opts.intro: cabeçalho.
   */
  async function render(_gen, m, el, opts) {
    const o = opts || {};
    TABS = Array.isArray(o.only) && o.only.length ? ALL_TABS.filter(([id]) => o.only.includes(id)) : ALL_TABS;
    view = {
      bare: !!o.bare,
      title: o.title || "RouteDex",
      intro: o.intro || "Tudo o que a PicoDex faz, direto no microSD: capas, biblioteca, estatísticas, associações, capturas e saúde do cartão.",
    };
    if (!TABS.some(([id]) => id === tab)) tab = TABS[0][0];
    host = el;
    if (m !== mountPath) {
      overview = null;
      health = null;
      healthSel = new Set();
      folderSel = "";
      gallerySystem = null;
      galleryCovers = {};
    }
    mountPath = m;
    await draw();
  }

  /** Abre a próxima renderização numa aba (ex.: "covers" a partir de Jogos). */
  function showTab(id) {
    if (ALL_TABS.some(([t]) => t === id)) {
      tab = id;
      gallerySystem = null;
    }
  }

  return { render, renderNight, showTab, credits: creditHtml };
})();
