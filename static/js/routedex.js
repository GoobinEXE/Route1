/**
 * RouteDex — biblioteca nativa do Route Pico para o Pico Launcher.
 * Baseado no PicoDex de rasalopa (MIT): https://github.com/rasalopa/picodex
 * Depende de getApi / waitForApi / escapeHtml / setBusy / isHardBusy / appendLog (app.js).
 */
const RouteDex = (() => {
  const TABS = [
    ["library", "Biblioteca"],
    ["health", "Saúde do cartão"],
    ["shots", "Capturas"],
    ["folders", "Pastas"],
    ["night", "Fundos noturnos"],
    ["cheats", "Cheats"],
  ];
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

  const esc = (s) => escapeHtml(String(s == null ? "" : s));

  async function api() {
    return getApi() || (await waitForApi());
  }

  function hardBusy() {
    return typeof isHardBusy === "function" ? isHardBusy() : !!(typeof busy !== "undefined" && busy);
  }

  /** Corre uma escrita no SD com a UI bloqueada; devolve a resposta ou null. */
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
        <div class="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h3 class="text-sm font-semibold text-fg">RouteDex</h3>
            <p class="text-[12px] text-fg-mute mt-1">A sua biblioteca do Pico Launcher, lida e escrita direto no microSD.</p>
          </div>
          <button type="button" class="btn-ghost !text-[11px]" id="routedex-reload">Actualizar</button>
        </div>
        <div class="routedex-tabs" role="tablist">${tabs}</div>
        <div id="routedex-body"></div>
        ${creditHtml()}
      </section>`;
    host.querySelectorAll(".routedex-tab").forEach((b) => {
      b.onclick = () => {
        if (hardBusy()) return;
        tab = b.getAttribute("data-tab");
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
    if (b) b.innerHTML = `<p class="text-[12px] text-fg-mute">${esc(msg || "A ler o cartão…")}</p>`;
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
    }
    if (tab === "library") await drawLibrary(my);
    else if (tab === "health") await drawHealth(my);
    else if (tab === "shots") await drawShots(my);
    else if (tab === "folders") await drawFolders(my);
    else if (tab === "night") await drawNight(my);
    else if (tab === "cheats") await drawCheats(my);
  }

  // ------------------------------------------------------------------ Biblioteca

  function enhancedNotice(ov) {
    const l = (ov && ov.launcher) || {};
    if (!l.present) {
      return `<div class="note note--warn">Este cartão não tem <code>_picoboot.nds</code>. Prepare o SD primeiro.</div>`;
    }
    if (ov.enhanced) {
      return `<div class="note note--ok"><strong>Pico Launcher Enhanced ${esc(
        l.version || ""
      )}</strong> no cartão: o próprio console grava favoritos, concluídos e tempo de jogo em <code>/_pico/gamedata.json</code>. As alterações feitas aqui aparecem no DS.</div>`;
    }
    return `<div class="note">
      <strong>O launcher oficial não usa estes dados.</strong> Favoritos, concluídos e estatísticas são do
      Pico Launcher Enhanced. Pode marcá-los já aqui; passam a aparecer no DS quando instalar a variante Enhanced
      em <button type="button" class="routedex-link" id="routedex-go-updates">Verificar Atualizações</button>.
    </div>`;
  }

  function statTile(label, value) {
    return `<div class="routedex-stat"><span class="stat-label">${esc(label)}</span><span class="stat-value">${esc(value)}</span></div>`;
  }

  function libraryRow(g) {
    const fav = g.favorite ? " routedex-flag--on" : "";
    const done = g.completed ? " routedex-flag--on" : "";
    const meta = [];
    if (g.launchCount) meta.push(`${g.launchCount}×`);
    if (g.playMinutes) meta.push(fmtMinutes(g.playMinutes));
    if (g.lastPlayed) meta.push(fmtDate(g.lastPlayed));
    const div = document.createElement("div");
    div.className = "routedex-row";
    div.innerHTML = `
      <button type="button" class="routedex-flag routedex-flag--fav${fav}" data-act="favorite" title="Favorito" aria-pressed="${!!g.favorite}">♥</button>
      <button type="button" class="routedex-flag routedex-flag--done${done}" data-act="completed" title="Concluído" aria-pressed="${!!g.completed}">✓</button>
      <span class="routedex-name" title="${esc(g.rel)}">${esc(g.name)}</span>
      <span class="routedex-sys">${esc(g.system === "retro" ? (g.name.split(".").pop() || "").toUpperCase() : g.system.toUpperCase())}</span>
      <span class="routedex-meta">${esc(meta.join(" · "))}</span>
      <button type="button" class="btn-ghost !text-[11px]" data-act="stats">Editar</button>`;
    div.querySelectorAll("[data-act]").forEach((b) => {
      b.onclick = () => onRowAction(g, b.getAttribute("data-act"));
    });
    return div;
  }

  async function onRowAction(g, act) {
    if (act === "favorite" || act === "completed") {
      const res = await write("toggle_routedex_flag", [g.rel, act]);
      if (res && res.entry) {
        Object.assign(g, res.entry);
        refreshLibraryList();
        refreshTotals();
      }
      return;
    }
    if (act === "stats") {
      const lc = prompt(`Número de vezes jogado — ${g.name}`, String(g.launchCount || 0));
      if (lc === null) return;
      const pm = prompt(`Tempo de jogo em minutos — ${g.name}`, String(g.playMinutes || 0));
      if (pm === null) return;
      const res = await write("set_routedex_stats", [g.rel, lc.trim(), pm.trim()], "Estatísticas corrigidas.");
      if (res && res.entry) {
        Object.assign(g, res.entry);
        refreshLibraryList();
        refreshTotals();
      }
    }
  }

  function filteredLibrary() {
    const lib = (overview && overview.library) || [];
    const q = query.trim().toLowerCase();
    return lib.filter((g) => {
      if (filter === "fav" && !g.favorite) return false;
      if (filter === "done" && !g.completed) return false;
      if (filter === "played" && !g.launchCount) return false;
      if (q && !g.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }

  function refreshLibraryList() {
    const list = host && host.querySelector("#routedex-list");
    if (!list) return;
    const items = filteredLibrary();
    const count = host.querySelector("#routedex-count");
    if (count) count.textContent = `${items.length} de ${(overview.library || []).length}`;
    if (items.length > 200 && window.R1K && R1K.virtual) {
      if (!vlist) vlist = R1K.virtual.createVirtualList(list, items, { rowHeight: 44, renderRow: (g) => libraryRow(g) });
      else vlist.setItems(items);
      return;
    }
    if (vlist && vlist.destroy) vlist.destroy();
    vlist = null;
    list.classList.remove("vgrid");
    list.innerHTML = "";
    if (!items.length) {
      list.innerHTML = `<p class="text-[12px] text-fg-mute p-3">Nenhum jogo com este filtro.</p>`;
      return;
    }
    const frag = document.createDocumentFragment();
    items.forEach((g) => frag.appendChild(libraryRow(g)));
    list.appendChild(frag);
  }

  function refreshTotals() {
    const lib = (overview && overview.library) || [];
    const t = { favorites: 0, completed: 0, played: 0, launches: 0, minutes: 0 };
    lib.forEach((g) => {
      t.favorites += g.favorite ? 1 : 0;
      t.completed += g.completed ? 1 : 0;
      if (g.launchCount) {
        t.played += 1;
        t.launches += g.launchCount;
        t.minutes += g.playMinutes || 0;
      }
    });
    const el = host && host.querySelector("#routedex-totals");
    if (el) {
      el.innerHTML =
        statTile("Jogos", lib.length) +
        statTile("Jogados", t.played) +
        statTile("Favoritos", t.favorites) +
        statTile("Concluídos", t.completed) +
        statTile("Partidas", t.launches) +
        statTile("Tempo total", fmtMinutes(t.minutes));
    }
  }

  async function drawLibrary(my) {
    loading();
    let ov;
    try {
      ov = overview || (await (await api()).get_routedex_overview(mountPath));
    } catch (e) {
      ov = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(ov && ov.success)) {
      b.innerHTML = errorHtml(ov && ov.error);
      return;
    }
    overview = ov;
    const recent = (ov.recent || [])
      .slice(0, 6)
      .map((e) => `<li><span class="truncate">${esc(e.fileName)}</span><span class="text-fg-mute">${esc(fmtDate(e.lastPlayed))}</span></li>`)
      .join("");
    const top = (ov.top || [])
      .slice(0, 6)
      .map((e) => `<li><span class="truncate">${esc(e.fileName)}</span><span class="text-fg-mute">${esc(e.launchCount)}× · ${esc(fmtMinutes(e.playMinutes))}</span></li>`)
      .join("");
    const stale = ov.stale || [];
    b.innerHTML = `
      ${ov.parse_error ? `<div class="note note--warn"><strong>gamedata.json não foi lido.</strong> ${esc(ov.parse_error)}</div>` : ""}
      ${enhancedNotice(ov)}
      <div class="routedex-stats" id="routedex-totals"></div>
      ${
        recent || top
          ? `<div class="routedex-cols">
              <div><h4 class="routedex-h">Jogados recentemente</h4><ul class="routedex-mini">${recent || "<li class='text-fg-mute'>—</li>"}</ul></div>
              <div><h4 class="routedex-h">Mais jogados</h4><ul class="routedex-mini">${top || "<li class='text-fg-mute'>—</li>"}</ul></div>
            </div>`
          : ""
      }
      <div class="routedex-toolbar">
        <input type="search" id="routedex-q" class="field-select routedex-input" placeholder="Procurar jogo…" value="${esc(query)}" aria-label="Procurar jogo">
        <select id="routedex-filter" class="field-select" aria-label="Filtro">
          <option value="all"${filter === "all" ? " selected" : ""}>Todos</option>
          <option value="fav"${filter === "fav" ? " selected" : ""}>Favoritos</option>
          <option value="done"${filter === "done" ? " selected" : ""}>Concluídos</option>
          <option value="played"${filter === "played" ? " selected" : ""}>Já jogados</option>
        </select>
        <span class="text-[11px] text-fg-mute" id="routedex-count"></span>
      </div>
      <div id="routedex-list" class="routedex-list"></div>
      ${
        stale.length
          ? `<div class="note mt-3"><strong>${stale.length} entrada(s) de jogos que já não estão no cartão.</strong>
              <span class="text-fg-mute">${esc(stale.slice(0, 5).map((e) => e.fileName).join(", "))}${stale.length > 5 ? "…" : ""}</span>
              <div class="mt-2"><button type="button" class="btn-ghost !text-[11px]" id="routedex-prune">Remover entradas órfãs</button></div></div>`
          : ""
      }`;
    refreshTotals();
    refreshLibraryList();
    const q = b.querySelector("#routedex-q");
    if (q)
      q.oninput = () => {
        query = q.value;
        refreshLibraryList();
      };
    const f = b.querySelector("#routedex-filter");
    if (f)
      f.onchange = () => {
        filter = f.value;
        refreshLibraryList();
      };
    const go = b.querySelector("#routedex-go-updates");
    if (go) go.onclick = () => window.R1K && R1K.updates && R1K.updates.check();
    const prune = b.querySelector("#routedex-prune");
    if (prune)
      prune.onclick = async () => {
        if (!confirm(`Remover ${stale.length} entrada(s) do gamedata.json?\n\nUma cópia do ficheiro fica no computador.`)) return;
        const res = await write("prune_routedex_entries", [stale.map((e) => e.fileName)], "Entradas órfãs removidas.");
        if (res) draw(true);
      };
  }

  // ------------------------------------------------------------------ Saúde

  function loaderLine(ld) {
    if (!ld) return "";
    const s = ld.status;
    const variant = ld.variant === "enhanced" ? ` + Loader Enhanced ${esc(ld.enhanced_version || "")}` : "";
    if (s === "no-loader") return `<span class="text-danger">Sem Pico Loader em /_pico.</span>`;
    if (s === "mixed")
      return `<span class="text-warn">Ficheiros de releases diferentes (mais próximo: ${esc(
        ld.mismatch && ld.mismatch.best_fit
      )}; fora: ${esc(((ld.mismatch && ld.mismatch.odd_ones_out) || []).join(", "))}).</span>`;
    if (s === "unrecognised") return `<span class="text-warn">Versão não reconhecida (build própria ou release mais nova que esta app).</span>`;
    const cands = ld.candidates || [];
    const ver = cands.length ? cands[cands.length - 1] : "";
    const behind = ld.releases_behind ? ` · ${ld.releases_behind} release(s) atrás de ${esc(ld.latest_known)}` : " · em dia";
    const builds = (ld.builds || []).length ? ` · build ${esc(ld.builds.join("/"))}` : "";
    return `<span class="text-ok">Pico Loader ${esc(ver)}</span>${variant}<span class="text-fg-mute">${cands.length ? behind : ""}${builds}</span>`;
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
    loading("A verificar o cartão…");
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
    healthSel = new Set([...healthSel].filter((r) => h.junk.includes(r) || h.orphan_saves.includes(r) || h.orphan_art.includes(r)));
    const problems = (h.problems || []).map((p) => `<li>${esc(p)}</li>`).join("");
    const dups = (h.duplicate_saves || [])
      .map((d) => `<li><code>${esc(d.beside)}</code> e <code>${esc(d.in_folder)}</code></li>`)
      .join("");
    const removable = h.junk.length + h.orphan_saves.length + h.orphan_art.length;
    b.innerHTML = `
      <div class="routedex-kv">
        <div><span class="stat-label">Launcher</span><span>${launcherLine(h.launcher)}</span></div>
        <div><span class="stat-label">Loader</span><span>${loaderLine(h.loader)}</span></div>
        <div><span class="stat-label">Biblioteca</span><span>${esc(h.games_count)} jogo(s) · ${esc(h.saves_count)} save(s)</span></div>
        ${
          h.missing_optional.length
            ? `<div><span class="stat-label">Opcionais em falta</span><span class="text-fg-mute">${esc(h.missing_optional.join(", "))}</span></div>`
            : ""
        }
      </div>
      ${problems ? `<div class="note note--warn"><strong>A corrigir</strong><ul class="routedex-ul">${problems}</ul></div>` : `<div class="note note--ok">Nenhum problema que impeça o arranque.</div>`}
      ${
        dups
          ? `<div class="note"><strong>Saves em duplicado</strong> (ao lado da ROM e em <code>saves/</code>). Com <code>"saveLocation": "saves"</code> o launcher usa o da pasta <code>saves/</code>; confira qual é o mais recente antes de apagar o outro.<ul class="routedex-ul">${dups}</ul></div>`
          : ""
      }
      ${checkList("Lixo do macOS", h.junk, "junk")}
      ${checkList("Saves sem jogo", h.orphan_saves, "saves")}
      ${checkList("Capas/ícones sem jogo", h.orphan_art, "art")}
      ${
        removable
          ? `<div class="flex items-center gap-3 flex-wrap mt-2">
              <button type="button" class="btn-primary" id="routedex-remove">Remover selecionados</button>
              <span class="text-[11px] text-fg-mute">Cada ficheiro é copiado para o computador antes de sair do cartão.</span>
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
    b.querySelectorAll("[data-selall]").forEach((btn) => {
      btn.onclick = () => {
        const box = b.querySelector(`.routedex-checks[data-kind="${btn.getAttribute("data-selall")}"]`);
        box.querySelectorAll("input[type=checkbox]").forEach((cb) => {
          cb.checked = true;
          healthSel.add(cb.getAttribute("data-rel"));
        });
      };
    });
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
      <p class="text-[12px] text-fg-mute">${shots.length} captura(s). As duas telas aparecem empilhadas numa só imagem.</p>
      <div class="routedex-shots">${shots
        .map(
          (s) => `<figure class="routedex-shot" data-id="${esc(s.id)}">
            <div class="routedex-shot-img"><span class="text-[11px] text-fg-mute">a carregar…</span></div>
            <figcaption>
              <span>${s.number != null ? `#${esc(s.number)}` : esc(s.id)}</span>
              <span class="flex gap-1">
                <button type="button" class="btn-ghost !text-[11px]" data-act="save">Guardar PNG</button>
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
        if (res && res.success && !res.cancelled) appendLog(`Captura guardada em ${res.path}`, "ok");
        else if (res && !res.success) alert(res.error || "Falha ao guardar.");
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
    box.innerHTML = `<p class="text-[12px] text-fg-mute">A ler a pasta…</p>`;
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
          <label class="text-[12px] text-fg-mute" for="routedex-title">Nome mostrado no launcher</label>
          <input id="routedex-title" class="field-select routedex-input" maxlength="127" value="${esc(bn ? bn.title : name)}">
          <label class="text-[12px] text-fg-mute" for="routedex-iconrom">Ícone a partir de</label>
          <select id="routedex-iconrom" class="field-select">
            ${(st.roms || []).map((r) => `<option value="rom:${esc(r)}">${esc(r)}</option>`).join("")}
            <option value="image">Imagem do computador (PNG ou BMP)…</option>
          </select>
          <div class="flex gap-2 flex-wrap">
            <button type="button" class="btn-primary" id="routedex-banner-save">Gravar banner</button>
            <button type="button" class="btn-ghost" id="routedex-cover-save">Escolher capa da pasta…</button>
            ${bn ? `<button type="button" class="btn-ghost btn-ghost--muted" data-rm="banner">Remover banner</button>` : ""}
            ${st.cover ? `<button type="button" class="btn-ghost btn-ghost--muted" data-rm="cover">Remover capa</button>` : ""}
          </div>
        </div>
      </div>`;
    box.querySelector("#routedex-banner-save").onclick = async () => {
      const title = box.querySelector("#routedex-title").value.trim();
      if (!title) {
        alert("Indique o nome a mostrar.");
        return;
      }
      const src = box.querySelector("#routedex-iconrom").value;
      let rom = "";
      let image = "";
      if (src === "image") {
        const p = await a.pick_image_file();
        if (!p || !p.success || p.cancelled) return;
        image = p.path;
      } else {
        rom = src.slice(4);
      }
      const res = await write("write_routedex_folder_banner", [folderSel, title, rom, image], `Banner gravado em ${folderSel}.`);
      if (res) drawFolderDetail(gen);
    };
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

  async function drawNight(my) {
    loading();
    const a = await api();
    let r;
    try {
      r = await a.list_routedex_night_themes(mountPath);
    } catch (e) {
      r = { success: false, error: e.message || String(e) };
    }
    if (my !== gen) return;
    const b = body();
    if (!(r && r.success)) {
      b.innerHTML = errorHtml(r && r.error);
      return;
    }
    const enhanced = overview ? overview.enhanced : null;
    const themes = r.themes || [];
    b.innerHTML = `
      <div class="note">O Pico Launcher Enhanced usa <code>topbg_night.bin</code> e <code>bottombg_night.bin</code> de um tema das 20:00 às 6:59, conferido ao arrancar. As cores são escurecidas e arrefecidas com a mesma fórmula do <code>make_night_bg.py</code> do Enhanced.${
        enhanced === false ? " <strong>O launcher oficial ignora estes ficheiros.</strong>" : ""
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
      }`;
    b.querySelectorAll("[data-gen]").forEach((btn) => {
      btn.onclick = async () => {
        const t = btn.getAttribute("data-gen");
        const res = await write("generate_routedex_night_backgrounds", [t], `Fundos noturnos gerados: ${t}.`);
        if (res) draw();
      };
    });
    b.querySelectorAll("[data-rm]").forEach((btn) => {
      btn.onclick = async () => {
        const res = await write("remove_routedex_night_backgrounds", [btn.getAttribute("data-rm")], "Fundos noturnos removidos.");
        if (res) draw();
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
      Não existe uma fonte oficial com versão fixa para esta base, por isso o Route Pico não a descarrega: escolha um
      <code>usrcheat.dat</code> que já tenha. O ficheiro é validado (cabeçalho <code>R4 CheatCode</code>) antes de ir para o cartão,
      e o anterior fica guardado no computador.</p>
      <button type="button" class="btn-primary" id="routedex-cheats-import">Importar usrcheat.dat…</button>`;
    b.querySelector("#routedex-cheats-import").onclick = async () => {
      const p = await a.pick_usrcheat_file();
      if (!p || !p.success || p.cancelled) return;
      const res = await write("import_routedex_cheats", [p.path], "Base de cheats instalada.");
      if (res) draw();
    };
  }

  // ------------------------------------------------------------------ API pública

  async function render(_gen, m, el) {
    host = el;
    if (m !== mountPath) {
      overview = null;
      health = null;
      healthSel = new Set();
      folderSel = "";
    }
    mountPath = m;
    await draw();
  }

  return { render, credits: creditHtml };
})();
