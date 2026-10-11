/**
 * Área exclusiva DSPico — fontes só LNH-team.
 * Depende de getApi / selectedDrive / runMountOp / escapeHtml / setBusy (app.js).
 */
const Dspico = (() => {
  let section = "status";
  let gamesCwd = "";
  let selectedRels = new Set();
  let lastInspect = null;
  let renderGen = 0;
  let artRel = null;
  let artKind = "cover";
  let artGen = 0;
  let artEscBound = false;
  const SECTIONS = [
    "status",
    "setup",
    "games",
    "emulators",
    "emunand",
    "settings",
    "firmware",
  ];

  function mount() {
    return (typeof selectedDrive !== "undefined" && selectedDrive && selectedDrive.mount_path) || null;
  }

  function setSection(name) {
    if (typeof busy !== "undefined" && busy) {
      alert("Aguarde a operação em andamento terminar antes de mudar de secção.");
      return;
    }
    if (!SECTIONS.includes(name)) name = "status";
    section = name;
    for (const key of SECTIONS) {
      const el = document.getElementById(`dspico-section-${key}`);
      const tab = document.getElementById(`dspico-tab-${key}`);
      if (el) el.classList.toggle("hidden", section !== key);
      if (tab) {
        const on = section === key;
        tab.classList.toggle("adv-tab--active", on);
        tab.setAttribute("aria-selected", on ? "true" : "false");
      }
    }
    refresh();
  }

  function enter() {
    refresh();
  }

  async function refresh() {
    const gen = ++renderGen;
    await renderActive(gen);
  }

  async function renderActive(gen) {
    const m = mount();
    if (section === "status") await renderStatus(gen, m);
    else if (section === "setup") await renderSetup(gen, m);
    else if (section === "games") await renderGames(gen, m);
    else if (section === "emulators") await renderEmulators(gen, m);
    else if (section === "emunand") await renderEmunand(gen, m);
    else if (section === "settings") await renderSettings(gen, m);
    else if (section === "firmware") await renderFirmware(gen, m);
  }

  function needDriveHtml() {
    return `
      <section class="panel p-5">
        <p class="opt-does">Seleccione o <strong>microSD do cartucho DSPico</strong> acima.</p>
        <p class="opt-when mt-1">Não é o SD lateral do DSi — é o cartão dentro do cartucho Slot-1.</p>
      </section>`;
  }

  async function openOfficial(url) {
    try {
      const api = getApi() || (await waitForApi());
      const res = await api.open_external_url(url);
      if (!(res && res.success)) {
        alert((res && res.error) || "Não foi possível abrir o link.");
      }
    } catch (e) {
      alert(e.message || String(e));
    }
  }

  function linksHtml(links) {
    if (!links || typeof links !== "object") return "";
    const items = [
      ["dspico_user_manual", "Manual DSPico"],
      ["pico_launcher", "Pico Launcher"],
      ["pico_loader", "Pico Loader"],
      ["dspico_firmware", "Firmware"],
      ["dspico_guide", "GUIDE oficial"],
      ["dspico_hardware", "Hardware"],
      ["pico_launcher_usage", "Usage / settings"],
    ];
    return `<div class="flex flex-wrap gap-2 mt-3">${items
      .map(([k, label]) => {
        const u = links[k];
        if (!u) return "";
        return `<button type="button" class="btn-ghost !text-[11px]" data-url="${escapeHtml(
          u
        )}">${escapeHtml(label)}</button>`;
      })
      .join("")}</div>`;
  }

  function bindLinkButtons(root) {
    if (!root) return;
    root.querySelectorAll("button[data-url]").forEach((btn) => {
      btn.onclick = () => openOfficial(btn.getAttribute("data-url"));
    });
  }

  async function renderStatus(gen, m) {
    const el = document.getElementById("dspico-section-status");
    if (!el) return;
    if (!m) {
      el.innerHTML = needDriveHtml();
      return;
    }
    el.innerHTML = `<section class="panel p-5"><p class="text-fg-mute text-[12px]">A inspeccionar…</p></section>`;
    try {
      const api = getApi() || (await waitForApi());
      const data = await api.inspect_dspico(m);
      if (gen !== renderGen) return;
      if (!(data && data.success)) {
        el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
          (data && data.error) || "Falha ao inspeccionar."
        )}</p></section>`;
        return;
      }
      lastInspect = data;
      const checklist = data.checklist || [];
      const pkgs = data.packages || {};
      const launcher = pkgs.pico_launcher || {};
      const loader = pkgs.pico_loader_dspico || {};
      const fw = pkgs.dspico_firmware_uf2 || {};

      el.innerHTML = `
        <section class="panel p-5 space-y-4">
          <div class="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <h3 class="text-sm font-semibold text-fg">Estado do microSD</h3>
              <p class="text-[12px] text-fg-mute mt-1">
                Pacote: ${
                  data.markers_ok
                    ? '<span class="text-ok">mínimo OK</span>'
                    : '<span class="text-warn">incompleto</span>'
                }
                · Jogos em <code>Games/</code>: ${escapeHtml(String(data.games_count || 0))}
              </p>
            </div>
            <button type="button" class="btn-ghost !text-[11px]" id="dspico-refresh-status">Actualizar</button>
          </div>
          <ul class="space-y-2">
            ${checklist
              .map((c) => {
                const opt = c.optional ? ' <span class="text-fg-mute">(opcional)</span>' : "";
                const icon = c.ok ? "✅" : c.optional ? "○" : "○";
                const cls = c.ok ? "text-ok" : "text-fg-mute";
                return `<li class="text-[13px] ${cls}">${icon} ${escapeHtml(
                  c.label || c.id
                )}${opt}</li>`;
              })
              .join("")}
          </ul>
          <div class="note">
            <strong>Pacotes oficiais pinados</strong><br>
            Launcher ${escapeHtml(launcher.tag || "?")} · Loader ${escapeHtml(
        loader.tag || "?"
      )} · UF2 ${
        fw.ready
          ? "pronto para gravar"
          : "ainda sem asset nas releases LNH (compile via GUIDE)"
      }
          </div>
          ${linksHtml(data.official_links)}
        </section>`;
      bindLinkButtons(el);
      const btn = document.getElementById("dspico-refresh-status");
      if (btn) btn.onclick = () => refresh();
    } catch (e) {
      if (gen !== renderGen) return;
      el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
        e.message || String(e)
      )}</p></section>`;
    }
  }

  async function renderSetup(gen, m) {
    const el = document.getElementById("dspico-section-setup");
    if (!el) return;
    if (!m) {
      el.innerHTML = needDriveHtml();
      return;
    }
    let links = (lastInspect && lastInspect.official_links) || null;
    if (!links) {
      try {
        const api = getApi() || (await waitForApi());
        const res = await api.get_dspico_official_links();
        if (gen !== renderGen) return;
        links = (res && res.links) || {};
      } catch (_e) {
        links = {};
      }
    }
    el.innerHTML = `
      <section class="panel p-5 space-y-4">
        <div>
          <h3 class="text-sm font-semibold text-fg">Preparar microSD</h3>
          <p class="text-[12px] text-fg-mute mt-1 leading-relaxed">
            Descarrega e verifica (SHA-256) o <strong>Pico Launcher</strong> e o
            <strong>Pico Loader DSPICO</strong> oficiais e escreve
            <code>_picoboot.nds</code> + <code>_pico/</code> + <code>Games/</code>.
          </p>
        </div>
        <div class="note note--warn">
          Só assets de <code>github.com/LNH-team/</code>. Não há opção de pasta/kernel de terceiros.
        </div>
        <button type="button" class="btn-primary" id="dspico-btn-setup">Instalar / actualizar pacote oficial</button>
        ${linksHtml(links)}
      </section>`;
    bindLinkButtons(el);
    const btn = document.getElementById("dspico-btn-setup");
    if (btn) {
      btn.onclick = async () => {
        if (
          !confirm(
            "Escrever o pacote oficial DSPico neste microSD?\n\n" +
              "Serão actualizados _picoboot.nds e a pasta _pico/."
          )
        ) {
          return;
        }
        await runMountOp({ method: "setup_dspico" });
      };
    }
  }

  async function renderGames(gen, m) {
    const el = document.getElementById("dspico-section-games");
    if (!el) return;
    if (!m) {
      el.innerHTML = needDriveHtml();
      return;
    }
    el.innerHTML = `<section class="panel p-5"><p class="text-fg-mute text-[12px]">A listar Games/…</p></section>`;
    try {
      const api = getApi() || (await waitForApi());
      const data = await api.browse_dspico_games(m, gamesCwd);
      if (gen !== renderGen) return;
      if (!(data && data.success)) {
        el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
          (data && data.error) || "Falha."
        )}</p></section>`;
        return;
      }
      const dirs = data.dirs || [];
      const files = data.files || [];
      const crumb = gamesCwd
        ? gamesCwd
            .split("/")
            .filter(Boolean)
            .map((p, i, arr) => {
              const rel = arr.slice(0, i + 1).join("/");
              return `<button type="button" class="text-accent-fg" data-nav="${escapeHtml(
                rel
              )}">${escapeHtml(p)}</button>`;
            })
            .join(" <span class=\"text-fg-mute\">/</span> ")
        : "";

      el.innerHTML = `
        <section class="panel p-5 space-y-3">
          <div>
            <h3 class="text-sm font-semibold text-fg">Organizar pastas</h3>
            <p class="text-[12px] text-fg-mute mt-1 leading-relaxed">
              Remove conteúdo de outros sistemas (TWiLight, GEi, R4, hiya, …) e deixa
              só o necessário para o DSPico. Organiza os jogos conforme a opção abaixo.
            </p>
          </div>
          <div>
            <p class="text-[11px] font-medium text-fg-soft mb-2">Como organizar os jogos</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2" id="dspico-organize-layout-choices">
              <label class="choice">
                <input type="radio" name="dspico-organize-layout" value="franchise">
                <span>
                  <span class="choice-title">Por franquia</span>
                  <span class="choice-sub"><code>Games/Pokemon/</code>, <code>Games/Mario/</code>…</span>
                </span>
              </label>
              <label class="choice">
                <input type="radio" name="dspico-organize-layout" value="platform">
                <span>
                  <span class="choice-title">Por plataforma</span>
                  <span class="choice-sub"><code>Games/nds/</code> ou <code>Games/dsi/</code></span>
                </span>
              </label>
              <label class="choice">
                <input type="radio" name="dspico-organize-layout" value="games" checked>
                <span>
                  <span class="choice-title">Soltos em Games/</span>
                  <span class="choice-sub">Todos os jogos na pasta <code>Games/</code></span>
                </span>
              </label>
              <label class="choice">
                <input type="radio" name="dspico-organize-layout" value="root">
                <span>
                  <span class="choice-title">Soltos na raiz</span>
                  <span class="choice-sub">Ao lado de <code>_picoboot.nds</code></span>
                </span>
              </label>
            </div>
          </div>
          <button type="button" class="btn-primary" id="dspico-btn-organize">Organizar pastas</button>
          <p class="text-[11px] text-fg-mute">
            Esta acção apaga pastas de outros sistemas. Saves vão com cada jogo.
            O explorador abaixo lista só <code>Games/</code>.
          </p>
        </section>
        <section class="panel p-5 space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="text-[12px]">
              <button type="button" class="btn-ghost !px-2 !py-1" id="dspico-games-up" ${
                gamesCwd ? "" : "disabled"
              }>↑</button>
              <code>Games/</code>${crumb ? " / " + crumb : ""}
            </div>
            <div class="flex flex-wrap gap-2">
              <button type="button" class="btn-secondary !text-[11px]" id="dspico-games-batch-art">Buscar capas e ícones</button>
              <button type="button" class="btn-secondary !text-[11px]" id="dspico-games-add">Adicionar jogos</button>
              <button type="button" class="btn-ghost !text-[11px]" id="dspico-games-mkdir">Nova pasta</button>
              <button type="button" class="btn-ghost !text-[11px] text-danger" id="dspico-games-del" disabled>Remover</button>
            </div>
          </div>
          <p class="text-[11px] text-fg-mute">
            Arraste ficheiros .nds / .dsi / .ids para esta área ou use Adicionar.
            Clique num jogo para escolher capa e ícone (Pico Launcher).
            O lote grava a 1.ª capa/ícone encontrados; não sobrescreve arte existente.
          </p>
          <div id="dspico-batch-missing" class="hidden space-y-2"></div>
          <div id="dspico-games-drop" class="border border-dashed border-line rounded-lg p-3 min-h-[160px] space-y-1">
            ${
              dirs.length + files.length === 0
                ? '<p class="text-fg-mute text-[12px]">Pasta vazia — adicione jogos.</p>'
                : ""
            }
            ${dirs
              .map(
                (d) =>
                  `<div class="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-surface-2 cursor-pointer dspico-dir" data-rel="${escapeHtml(
                    d.rel_path
                  )}">
                    <span class="text-fg-mute">📁</span>
                    <span class="text-[13px] flex-1">${escapeHtml(d.name)}</span>
                    <span class="text-[11px] text-fg-mute">${escapeHtml(
                      String(d.item_count || 0)
                    )}</span>
                  </div>`
              )
              .join("")}
            ${files
              .map((f) => {
                const hasC = !!f.has_cover;
                const hasI = !!f.has_icon;
                const thumb = f.cover
                  ? `<img class="dspico-game-thumb" src="${f.cover}" alt="" draggable="false">`
                  : `<div class="dspico-game-thumb-ph">capa</div>`;
                return `<div class="dspico-game-row">
                    <input type="checkbox" class="dspico-game-cb shrink-0" value="${escapeHtml(
                      f.rel_path
                    )}" ${selectedRels.has(f.rel_path) ? "checked" : ""}>
                    <button type="button" class="dspico-game-open flex items-center gap-2 min-w-0 flex-1 text-left" data-rel="${escapeHtml(
                      f.rel_path
                    )}">
                      ${thumb}
                      <span class="text-[13px] flex-1 truncate">${escapeHtml(
                        f.display_name || f.name
                      )}</span>
                      <span class="dspico-game-badges">
                        <span class="dspico-game-badge ${
                          hasC ? "dspico-game-badge--ok" : ""
                        }">capa</span>
                        <span class="dspico-game-badge ${
                          hasI ? "dspico-game-badge--ok" : ""
                        }">ícone</span>
                      </span>
                      <span class="text-[11px] text-fg-mute shrink-0">${escapeHtml(
                        f.size_label || ""
                      )}</span>
                    </button>
                  </div>`;
              })
              .join("")}
          </div>
        </section>`;

      const up = document.getElementById("dspico-games-up");
      if (up) {
        up.onclick = () => {
          if (!gamesCwd) return;
          const parts = gamesCwd.split("/").filter(Boolean);
          parts.pop();
          gamesCwd = parts.join("/");
          selectedRels.clear();
          refresh();
        };
      }
      el.querySelectorAll("[data-nav]").forEach((b) => {
        b.onclick = () => {
          gamesCwd = b.getAttribute("data-nav") || "";
          selectedRels.clear();
          refresh();
        };
      });
      el.querySelectorAll(".dspico-dir").forEach((row) => {
        row.onclick = () => {
          gamesCwd = row.getAttribute("data-rel") || "";
          selectedRels.clear();
          refresh();
        };
      });
      const updateDel = () => {
        const del = document.getElementById("dspico-games-del");
        if (del) del.disabled = selectedRels.size === 0 || !!busy;
      };
      el.querySelectorAll(".dspico-game-cb").forEach((cb) => {
        cb.onchange = () => {
          if (cb.checked) selectedRels.add(cb.value);
          else selectedRels.delete(cb.value);
          updateDel();
        };
        cb.onclick = (ev) => ev.stopPropagation();
      });
      el.querySelectorAll(".dspico-game-open").forEach((btn) => {
        btn.onclick = () => {
          const rel = btn.getAttribute("data-rel");
          if (rel) openArtPanel(rel);
        };
      });
      updateDel();

      const orgBtn = document.getElementById("dspico-btn-organize");
      if (orgBtn) {
        orgBtn.onclick = async () => {
          const layout =
            document.querySelector(
              'input[name="dspico-organize-layout"]:checked'
            )?.value || "games";
          gamesCwd = "";
          selectedRels.clear();
          await runMountOp({
            method: "organize_dspico",
            layout,
            confirmOrganize: true,
            sourceBtn: orgBtn,
          });
        };
      }

      const batchArtBtn = document.getElementById("dspico-games-batch-art");
      if (batchArtBtn) {
        batchArtBtn.onclick = () => runDspicoArtworkBatch();
      }
      const addBtn = document.getElementById("dspico-games-add");
      if (addBtn) addBtn.onclick = () => addGames();
      const mkdirBtn = document.getElementById("dspico-games-mkdir");
      if (mkdirBtn) {
        mkdirBtn.onclick = async () => {
          const name = prompt("Nome da pasta em Games/:");
          if (!name) return;
          setBusy(true);
          try {
            const api2 = getApi() || (await waitForApi());
            const res = await api2.mkdir_dspico_games(m, gamesCwd, name);
            if (res && res.success) appendLog(res.message || "Pasta criada.", "success");
            else appendLog((res && res.error) || "Falha", "error");
          } finally {
            setBusy(false);
            refresh();
          }
        };
      }
      const delBtn = document.getElementById("dspico-games-del");
      if (delBtn) {
        delBtn.onclick = async () => {
          if (!selectedRels.size) return;
          if (!confirm(`Remover ${selectedRels.size} ficheiro(s) de Games/?`)) return;
          setBusy(true);
          try {
            const api2 = getApi() || (await waitForApi());
            const res = await api2.delete_dspico_games(m, Array.from(selectedRels));
            if (res && res.success) {
              appendLog(res.message || "Removido.", "success");
              selectedRels.clear();
            } else appendLog((res && res.error) || "Falha", "error");
          } finally {
            setBusy(false);
            refresh();
          }
        };
      }

      const drop = document.getElementById("dspico-games-drop");
      if (drop) {
        drop.ondragover = (e) => {
          e.preventDefault();
          drop.classList.add("ring-1", "ring-accent");
        };
        drop.ondragleave = () => drop.classList.remove("ring-1", "ring-accent");
        drop.ondrop = (e) => {
          e.preventDefault();
          drop.classList.remove("ring-1", "ring-accent");
        };
      }
    } catch (e) {
      if (gen !== renderGen) return;
      el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
        e.message || String(e)
      )}</p></section>`;
    }
  }

  async function addGames() {
    const m = mount();
    if (!m) {
      alert("Seleccione o microSD primeiro.");
      return;
    }
    try {
      const api = getApi() || (await waitForApi());
      const picked = await api.pick_dspico_rom_files();
      if (!(picked && picked.success) || picked.cancelled) return;
      const paths = picked.paths || [];
      if (!paths.length) return;
      await importPaths(paths);
    } catch (e) {
      appendLog(e.message || String(e), "error");
    }
  }

  function ensureArtEsc() {
    if (artEscBound) return;
    artEscBound = true;
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      const panel = document.getElementById("dspico-art-panel");
      if (panel && !panel.classList.contains("hidden")) {
        closeArtPanel();
      }
    });
  }

  function closeArtPanel() {
    artRel = null;
    artGen += 1;
    const panel = document.getElementById("dspico-art-panel");
    const backdrop = document.getElementById("dspico-art-backdrop");
    if (panel) {
      panel.classList.add("hidden");
      panel.setAttribute("aria-hidden", "true");
    }
    if (backdrop) backdrop.classList.add("hidden");
  }

  function renderArtBody(state) {
    const body = document.getElementById("dspico-art-body");
    if (!body) return;
    const kind = state.kind || artKind;
    const current = state.current;
    const candidates = Array.isArray(state.candidates) ? state.candidates : [];
    const hints = state.hints || {};
    const isIcon = kind === "icon";
    const currentHtml = current
      ? `<img src="${current}" alt="" draggable="false">`
      : `<div class="dspico-art-ph ${
          isIcon ? "dspico-art-ph--icon" : ""
        }">Sem ${isIcon ? "ícone" : "capa"}</div>`;

    const opts = candidates
      .map((c, i) => {
        // Prefere URL remota (sem download no Python); data: só para arte já no cartão.
        const src = escapeHtml(c.preview || c.url || "");
        return (
          `<button type="button" class="dspico-art-opt ${
            isIcon ? "dspico-art-opt--icon" : ""
          }" data-art-idx="${i}">
            <img src="${src}" alt="" draggable="false" loading="lazy" referrerpolicy="no-referrer"
                 onerror="this.classList.add('hidden'); this.insertAdjacentHTML('afterend','<div class=\\'dspico-art-ph${
                   isIcon ? " dspico-art-ph--icon" : ""
                 }\\'>—</div>');">
            <span class="dspico-art-opt-label">${escapeHtml(
              c.label || c.source || "opção"
            )}</span>
          </button>`
        );
      })
      .join("");

    body.innerHTML =
      `<div>
        <p class="text-[13px] font-medium text-fg">${escapeHtml(
          state.display_name || artRel || ""
        )}</p>
        <p class="text-[11px] text-fg-mute mt-0.5">Games/${escapeHtml(
          state.rel_path || artRel || ""
        )}${
          state.game_code
            ? " · " + escapeHtml(state.game_code)
            : ""
        }</p>
      </div>` +
      `<div class="dspico-art-tabs">
        <button type="button" class="dspico-art-tab ${
          kind === "cover" ? "dspico-art-tab--on" : ""
        }" data-art-kind="cover">Capa</button>
        <button type="button" class="dspico-art-tab ${
          kind === "icon" ? "dspico-art-tab--on" : ""
        }" data-art-kind="icon">Ícone</button>
      </div>` +
      `<div class="dspico-art-current ${
        isIcon ? "dspico-art-current--icon" : ""
      }">${currentHtml}
        <div class="min-w-0">
          <p class="text-[12px] text-fg-soft">Actual no cartão</p>
          <p class="text-[11px] text-fg-mute mt-1 leading-relaxed">${escapeHtml(
            hints[kind] || ""
          )}</p>
        </div>
      </div>` +
      `<div class="dspico-art-search">
        <input type="search" id="dspico-art-query" placeholder="Pesquisar por nome ou TID…" value="${escapeHtml(
          state.query || ""
        )}">
        <button type="button" class="btn-secondary !py-1.5 !px-3 text-[11px]" id="dspico-art-search-btn">Pesquisar</button>
      </div>` +
      `<div class="flex flex-wrap gap-2">
        <button type="button" class="btn-primary !py-1.5 !px-3 text-[11px]" id="dspico-art-auto">Buscar online</button>
        <button type="button" class="btn-secondary !py-1.5 !px-3 text-[11px]" id="dspico-art-manual">Escolher ficheiro…</button>
      </div>` +
      (state.searching
        ? `<p class="text-[12px] text-fg-mute">A procurar na Internet…</p>`
        : "") +
      (state.message
        ? `<p class="text-[12px] text-fg-soft">${escapeHtml(state.message)}</p>`
        : "") +
      (candidates.length
        ? `<div class="dspico-art-grid">${opts}</div>
           <p class="text-[11px] text-fg-mute">Clique numa opção para gravar no formato Pico Launcher (BMP).</p>`
        : !state.searching
          ? `<p class="text-[12px] text-fg-mute">Nenhuma opção ainda — use «Buscar online», pesquise outro nome ou escolha um ficheiro.</p>`
          : "");

    body.querySelectorAll("[data-art-kind]").forEach((tab) => {
      tab.onclick = () => {
        const k = tab.getAttribute("data-art-kind");
        if (k === "cover" || k === "icon") {
          artKind = k;
          runArtSearch("");
        }
      };
    });
    const searchBtn = document.getElementById("dspico-art-search-btn");
    const queryEl = document.getElementById("dspico-art-query");
    const doSearch = () => {
      const q = (queryEl && queryEl.value) || "";
      runArtSearch(q);
    };
    if (searchBtn) searchBtn.onclick = doSearch;
    if (queryEl) {
      queryEl.onkeydown = (ev) => {
        if (ev.key === "Enter") {
          ev.preventDefault();
          doSearch();
        }
      };
    }
    const autoBtn = document.getElementById("dspico-art-auto");
    if (autoBtn) autoBtn.onclick = () => runArtSearch("");
    const manBtn = document.getElementById("dspico-art-manual");
    if (manBtn) manBtn.onclick = () => pickArtFile();
    body.querySelectorAll("[data-art-idx]").forEach((btn) => {
      btn.onclick = () => {
        const idx = parseInt(btn.getAttribute("data-art-idx") || "-1", 10);
        const c = candidates[idx];
        if (c && c.url) applyArtUrl(c.url);
      };
    });
  }

  function renderBatchMissing(missing) {
    const el = document.getElementById("dspico-batch-missing");
    if (!el) return;
    const list = Array.isArray(missing) ? missing : [];
    if (!list.length) {
      el.classList.add("hidden");
      el.innerHTML = "";
      return;
    }
    el.classList.remove("hidden");
    const rows = list
      .map((item, idx) => {
        const name = escapeHtml(item.display_name || item.rel_path || "?");
        const bits = [];
        if (item.missing_cover) bits.push("capa");
        if (item.missing_icon) bits.push("ícone");
        const need = bits.length ? bits.join(" + ") : "arte";
        const rel = escapeHtml(item.rel_path || "");
        return `<div class="flex flex-wrap items-center justify-between gap-2 p-2 rounded border border-line text-[12px]" data-miss-idx="${idx}">
          <div>
            <div class="font-medium text-fg">${name}</div>
            <div class="text-[11px] text-fg-mute">Em falta: ${escapeHtml(need)}</div>
          </div>
          <div class="flex flex-wrap gap-1">
            <button type="button" class="btn-secondary !text-[11px] !py-1 !px-2" data-miss-search="${rel}">Pesquisar</button>
            <button type="button" class="btn-ghost !text-[11px] !py-1 !px-2" data-miss-file="${rel}" data-miss-kind="${
              item.missing_cover ? "cover" : "icon"
            }">Escolher ficheiro</button>
          </div>
        </div>`;
      })
      .join("");
    el.innerHTML = `
      <div class="rounded-lg border border-line p-3 space-y-2 bg-surface-2/40">
        <p class="text-[12px] font-semibold text-fg">Jogos sem capa/ícone após o lote</p>
        <p class="text-[11px] text-fg-mute">Pesquise online ou escolha um ficheiro. Só DSPico — não afecta TWiLight.</p>
        <div class="space-y-2 max-h-56 overflow-y-auto">${rows}</div>
      </div>`;
    el.querySelectorAll("[data-miss-search]").forEach((btn) => {
      btn.onclick = () => {
        const rel = btn.getAttribute("data-miss-search") || "";
        if (rel) openArtPanel(rel);
      };
    });
    el.querySelectorAll("[data-miss-file]").forEach((btn) => {
      btn.onclick = async () => {
        const rel = btn.getAttribute("data-miss-file") || "";
        const kind = btn.getAttribute("data-miss-kind") || "cover";
        if (!rel) return;
        artRel = rel;
        artKind = kind === "icon" ? "icon" : "cover";
        await pickArtFile();
      };
    });
  }

  async function runDspicoArtworkBatch() {
    const m = mount();
    if (!m) {
      alert("Seleccione um cartão.");
      return;
    }
    if (typeof busy !== "undefined" && busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    try {
      const api = getApi() || (await waitForApi());
      const fn =
        api &&
        (api.generate_dspico_artwork_batch || api.generate_dspico_covers_batch);
      if (!fn) {
        appendLog("API de lote DSPico indisponível.", "error");
        return;
      }
      setBusy(true);
      appendLog("A buscar capas e ícones DSPico em lote…", "info");
      const res = await fn.call(api, m);
      if (res && res.success) {
        appendLog(res.message || "Lote concluído.", "success");
        renderBatchMissing(res.missing || []);
        refresh();
      } else {
        appendLog((res && res.error) || "Falha no lote DSPico.", "error");
        renderBatchMissing([]);
      }
    } catch (e) {
      appendLog(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function openArtPanel(rel, keepKind) {
    if (!rel || !mount()) return;
    ensureArtEsc();
    const gen = ++artGen;
    const sameGame = artRel === rel;
    artRel = rel;
    if (!keepKind && !sameGame) artKind = "cover";
    const panel = document.getElementById("dspico-art-panel");
    const backdrop = document.getElementById("dspico-art-backdrop");
    const title = document.getElementById("dspico-art-title");
    if (title) title.textContent = "Arte do jogo";
    if (panel) {
      panel.classList.remove("hidden");
      panel.setAttribute("aria-hidden", "false");
    }
    if (backdrop) backdrop.classList.remove("hidden");
    renderArtBody({
      display_name: rel.split("/").pop(),
      rel_path: rel,
      kind: artKind,
      searching: true,
      message: "A carregar…",
      candidates: [],
    });
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.get_dspico_game_artwork !== "function") {
        if (gen !== artGen) return;
        renderArtBody({
          rel_path: rel,
          kind: artKind,
          message: "API de arte DSPico indisponível.",
          candidates: [],
        });
        return;
      }
      const meta = await api.get_dspico_game_artwork(mount(), rel);
      if (gen !== artGen) return;
      if (!(meta && meta.success)) {
        renderArtBody({
          rel_path: rel,
          kind: artKind,
          message: (meta && meta.error) || "Falha ao carregar.",
          candidates: [],
        });
        return;
      }
      renderArtBody({
        ...meta,
        kind: artKind,
        current: artKind === "icon" ? meta.icon : meta.cover,
        candidates: [],
        message: "A procurar opções online…",
        searching: true,
      });
      await runArtSearch("", gen);
    } catch (e) {
      if (gen !== artGen) return;
      renderArtBody({
        rel_path: rel,
        kind: artKind,
        message: e.message || String(e),
        candidates: [],
      });
    }
  }

  async function runArtSearch(query, expectedGen) {
    if (!artRel || !mount()) return;
    if (typeof busy !== "undefined" && busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    const gen = expectedGen != null ? expectedGen : ++artGen;
    const q = typeof query === "string" ? query : "";
    renderArtBody({
      rel_path: artRel,
      kind: artKind,
      query: q,
      searching: true,
      message: "A procurar na Internet…",
      candidates: [],
    });
    try {
      const api = getApi() || (await waitForApi());
      if (!api || typeof api.search_dspico_artwork !== "function") {
        if (gen !== artGen) return;
        appendLog("API de pesquisa de arte indisponível.", "error");
        return;
      }
      setBusy(true);
      const data = await api.search_dspico_artwork(
        mount(),
        artRel,
        artKind,
        q
      );
      if (gen !== artGen) return;
      if (!(data && data.success)) {
        renderArtBody({
          rel_path: artRel,
          kind: artKind,
          query: q,
          message: (data && data.error) || "Pesquisa falhou.",
          candidates: [],
        });
        return;
      }
      renderArtBody({ ...data, kind: artKind, searching: false });
    } catch (e) {
      if (gen !== artGen) return;
      renderArtBody({
        rel_path: artRel,
        kind: artKind,
        query: q,
        message: e.message || String(e),
        candidates: [],
      });
    } finally {
      setBusy(false);
    }
  }

  async function applyArtUrl(url) {
    if (!artRel || !mount() || !url) return;
    if (typeof busy !== "undefined" && busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    let ok = false;
    const rel = artRel;
    try {
      const api = getApi() || (await waitForApi());
      setBusy(true);
      appendLog(
        artKind === "icon" ? "A gravar ícone…" : "A gravar capa…",
        "info"
      );
      const res = await api.apply_dspico_artwork_url(
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
    } catch (e) {
      appendLog(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
    if (ok) {
      await openArtPanel(rel, true);
      refresh();
    }
  }

  async function pickArtFile() {
    if (!artRel || !mount()) return;
    if (typeof busy !== "undefined" && busy) {
      appendLog("Aguarde a operação em andamento terminar.", "warn");
      return;
    }
    let ok = false;
    const rel = artRel;
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
        artKind === "icon" ? "A gravar ícone…" : "A gravar capa…",
        "info"
      );
      const res = await api.set_dspico_artwork(
        mount(),
        rel,
        artKind,
        picked.path
      );
      if (res && res.success) {
        appendLog(res.message || "Arte gravada.", "success");
        ok = true;
      } else {
        appendLog((res && res.error) || "Falha ao gravar arte.", "error");
      }
    } catch (e) {
      appendLog(e.message || String(e), "error");
    } finally {
      setBusy(false);
    }
    if (ok) {
      await openArtPanel(rel, true);
      refresh();
    }
  }

  async function importPaths(paths) {
    const m = mount();
    if (!m || !paths || !paths.length) return;
    setBusy(true);
    try {
      const api = getApi() || (await waitForApi());
      const res = await api.import_dspico_games(m, paths, gamesCwd);
      if (res && res.success) appendLog(res.message || "Importado.", "success");
      else appendLog((res && res.error) || "Falha ao importar.", "error");
    } catch (e) {
      appendLog(e.message || String(e), "error");
    } finally {
      setBusy(false);
      refresh();
    }
  }

  function onNativeDrop(paths) {
    if (typeof appMode !== "undefined" && appMode !== "dspico") return;
    if (section !== "games") setSection("games");
    importPaths(paths);
  }

  async function renderEmulators(gen, m) {
    const el = document.getElementById("dspico-section-emulators");
    if (!el) return;
    if (!m) {
      el.innerHTML = needDriveHtml();
      return;
    }
    el.innerHTML = `<section class="panel p-5"><p class="text-fg-mute text-[12px]">A carregar catálogo…</p></section>`;
    try {
      const api = getApi() || (await waitForApi());
      const data = await api.list_dspico_emulators();
      if (gen !== renderGen) return;
      if (!(data && data.success)) {
        el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
          (data && data.error) || "Falha ao listar emuladores."
        )}</p></section>`;
        return;
      }
      const emus = data.emulators || [];
      const cats = data.categories || [];
      const available = emus.filter((e) => e && e.available);
      const byCat = {};
      for (const e of available) {
        const c = e.category || "misc";
        (byCat[c] = byCat[c] || []).push(e);
      }

      const catBlocks = cats
        .map((cat) => {
          const list = byCat[cat.id] || [];
          if (!list.length) return "";
          const rows = list
            .map((e) => {
              const modeBadge =
                e.install_mode === "manual"
                  ? `<span class="text-[10px] text-warn ml-1">manual</span>`
                  : `<span class="text-[10px] text-fg-mute ml-1">argv</span>`;
              const notes = e.bios_notes
                ? `<p class="text-[11px] text-fg-mute mt-0.5 leading-snug">${escapeHtml(
                    e.bios_notes
                  )}</p>`
                : "";
              return `
              <label class="flex gap-2 items-start py-1.5 px-2 rounded hover:bg-surface-2 cursor-pointer">
                <input type="checkbox" class="dspico-emu-cb mt-1" value="${escapeHtml(
                  e.id
                )}" data-popular="${e.popular ? "1" : "0"}">
                <span class="min-w-0">
                  <span class="text-[13px] text-fg font-medium">${escapeHtml(
                    e.label
                  )}</span>${modeBadge}
                  ${notes}
                </span>
              </label>`;
            })
            .join("");
          return `
            <div class="space-y-1">
              <h4 class="text-[12px] font-semibold text-fg-soft uppercase tracking-wide">${escapeHtml(
                cat.label
              )}</h4>
              <div class="border border-line rounded-lg divide-y divide-line/60">${rows}</div>
            </div>`;
        })
        .join("");

      el.innerHTML = `
        <section class="panel p-5 space-y-4">
          <div>
            <h3 class="text-sm font-semibold text-fg">Emuladores (Pico-Launcher)</h3>
            <p class="text-[12px] text-fg-mute mt-1 leading-relaxed">
              Copia NDS para <code>/_pico/emulators/</code> (ou <code>/Emulators/</code> se manual),
              cria <code>/ROMs/…</code> e configura <code>fileAssociations</code>.
              Jogos NDS/DSi ficam em <code>Games/</code>. BIOS proprietária não é descarregada.
              Se escolher GBARunner3 e 2, só o 3 fica associado a <code>.gba</code>.
            </p>
          </div>
          ${
            available.length
              ? catBlocks
              : `<div class="note note--warn">Nenhum emulador com pin disponível neste build.</div>`
          }
          <div class="flex flex-wrap gap-2">
            <button type="button" class="btn-ghost !text-[11px]" id="dspico-emu-popular">Seleccionar populares</button>
            <button type="button" class="btn-ghost !text-[11px]" id="dspico-emu-clear">Limpar</button>
            <button type="button" class="btn-primary" id="dspico-emu-install" ${
              available.length ? "" : "disabled"
            }>Instalar seleccionados</button>
          </div>
          <div id="dspico-emu-result" class="text-[12px] text-fg-mute hidden"></div>
        </section>`;

      const popularBtn = document.getElementById("dspico-emu-popular");
      const clearBtn = document.getElementById("dspico-emu-clear");
      const installBtn = document.getElementById("dspico-emu-install");

      if (popularBtn) {
        popularBtn.onclick = () => {
          el.querySelectorAll(".dspico-emu-cb").forEach((cb) => {
            cb.checked = cb.getAttribute("data-popular") === "1";
          });
        };
      }
      if (clearBtn) {
        clearBtn.onclick = () => {
          el.querySelectorAll(".dspico-emu-cb").forEach((cb) => {
            cb.checked = false;
          });
        };
      }
      if (installBtn) {
        installBtn.onclick = async () => {
          const ids = Array.from(
            el.querySelectorAll(".dspico-emu-cb:checked")
          ).map((c) => c.value);
          if (!ids.length) {
            alert("Seleccione pelo menos um emulador.");
            return;
          }
          if (
            !confirm(
              `Instalar ${ids.length} emulador(es) no microSD?\n\n` +
                "Download com SHA-256 e criação de pastas /ROMs/."
            )
          ) {
            return;
          }
          setBusy(true);
          const resultEl = document.getElementById("dspico-emu-result");
          try {
            const res = await api.install_dspico_emulators(m, ids);
            if (gen !== renderGen) return;
            if (res && res.success) {
              appendLog(res.message || "Emuladores instalados.", "success");
              const hints = (res.bios_hints || []).join("\n");
              if (resultEl) {
                resultEl.classList.remove("hidden");
                resultEl.innerHTML = `<div class="note note--ok space-y-1">
                  <p>${escapeHtml(res.message || "OK")}</p>
                  ${
                    hints
                      ? `<p class="text-[11px] whitespace-pre-wrap">${escapeHtml(
                          hints
                        )}</p>`
                      : ""
                  }
                </div>`;
              }
            } else {
              appendLog((res && res.error) || "Falha", "error");
              if (resultEl) {
                resultEl.classList.remove("hidden");
                resultEl.innerHTML = `<div class="note note--warn">${escapeHtml(
                  (res && res.error) || "Falha"
                )}</div>`;
              }
            }
          } catch (e) {
            appendLog(e.message || String(e), "error");
          } finally {
            setBusy(false);
          }
        };
      }
    } catch (e) {
      if (gen !== renderGen) return;
      el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
        e.message || String(e)
      )}</p></section>`;
    }
  }

  async function renderEmunand(gen, m) {
    const el = document.getElementById("dspico-section-emunand");
    if (!el) return;
    if (!m) {
      el.innerHTML = needDriveHtml();
      return;
    }
    let data = lastInspect;
    try {
      const api = getApi() || (await waitForApi());
      data = await api.inspect_dspico(m);
      if (gen !== renderGen) return;
      if (data && data.success) lastInspect = data;
    } catch (_e) {
      /* use last */
    }
    const files = (data && data.files) || {};
    const emu = (data && data.emunand) || {};
    el.innerHTML = `
      <section class="panel p-5 space-y-4">
        <div>
          <h3 class="text-sm font-semibold text-fg">Emunand / DSiWare</h3>
          <p class="text-[12px] text-fg-mute mt-1 leading-relaxed">
            Conforme o README do Pico Loader: DSiWare e ROMs com secure area encriptada
            precisam de <code>/_pico/biosnds7.rom</code> (BIOS ARM7 de <strong>DS</strong>, não DSi)
            e pastas NAND no cartão. Importe apenas dumps <em>seus</em> — o app não descarrega BIOS/NAND.
          </p>
        </div>
        <ul class="text-[12px] space-y-1">
          <li>${files.biosnds7 ? "✅" : "○"} <code>_pico/biosnds7.rom</code></li>
          <li>${files.twl_font ? "✅" : "○"} <code>sys/TWLFontTable.dat</code></li>
          <li>${emu.photo ? "✅" : "○"} <code>photo/</code></li>
          <li>${emu.shared1 ? "✅" : "○"} <code>shared1/</code></li>
          <li>${emu.shared2_0000 ? "✅" : "○"} <code>shared2/0000/</code></li>
          <li>${emu.sys ? "✅" : "○"} <code>sys/</code></li>
        </ul>
        <div class="flex flex-col sm:flex-row gap-2 flex-wrap">
          <button type="button" class="btn-secondary" id="dspico-emunand-skel">Criar pastas emunand</button>
          <button type="button" class="btn-ghost" id="dspico-import-bios">Importar biosnds7.rom…</button>
          <button type="button" class="btn-ghost" id="dspico-import-font">Importar TWLFontTable.dat…</button>
        </div>
        <div class="note note--warn">
          Não use dumps de terceiros. Obtenha o BIOS/font a partir da sua consola.
        </div>
      </section>`;
    document.getElementById("dspico-emunand-skel").onclick = async () => {
      await runMountOp({ method: "ensure_dspico_emunand" });
    };
    document.getElementById("dspico-import-bios").onclick = async () => {
      const api = getApi() || (await waitForApi());
      const picked = await api.pick_dspico_bios_file();
      if (!(picked && picked.success) || picked.cancelled || !picked.path) return;
      setBusy(true);
      try {
        const res = await api.import_dspico_bios(m, picked.path);
        if (res && res.success) appendLog(res.message, "success");
        else appendLog((res && res.error) || "Falha", "error");
      } finally {
        setBusy(false);
        refresh();
      }
    };
    document.getElementById("dspico-import-font").onclick = async () => {
      const api = getApi() || (await waitForApi());
      const picked = await api.pick_dspico_font_file();
      if (!(picked && picked.success) || picked.cancelled || !picked.path) return;
      setBusy(true);
      try {
        const res = await api.import_dspico_twl_font(m, picked.path);
        if (res && res.success) appendLog(res.message, "success");
        else appendLog((res && res.error) || "Falha", "error");
      } finally {
        setBusy(false);
        refresh();
      }
    };
  }

  async function renderSettings(gen, m) {
    const el = document.getElementById("dspico-section-settings");
    if (!el) return;
    if (!m) {
      el.innerHTML = needDriveHtml();
      return;
    }
    el.innerHTML = `<section class="panel p-5"><p class="text-fg-mute text-[12px]">A ler settings…</p></section>`;
    try {
      const api = getApi() || (await waitForApi());
      const data = await api.get_dspico_settings(m);
      if (gen !== renderGen) return;
      if (!(data && data.success)) {
        el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
          (data && data.error) || "Falha"
        )}</p></section>`;
        return;
      }
      const s = data.settings || {};
      const layouts = data.layouts || [
        "Horizontal",
        "Vertical",
        "BannerList",
        "Coverflow",
      ];
      const sorts = data.sort_modes || ["NameAscending", "NameDescending"];
      el.innerHTML = `
        <section class="panel p-5 space-y-4">
          <div>
            <h3 class="text-sm font-semibold text-fg">Pico Launcher — settings.json</h3>
            <p class="text-[12px] text-fg-mute mt-1">Ficheiro <code>/_pico/settings.json</code> (chaves documentadas no Usage oficial).</p>
          </div>
          <label class="block text-[12px]">
            <span class="text-fg-mute">Tema (pasta em _pico/themes/)</span>
            <input id="dspico-set-theme" class="field-select w-full mt-1" value="${escapeHtml(
              s.theme || ""
            )}" placeholder="ex.: raspberry">
          </label>
          <label class="block text-[12px]">
            <span class="text-fg-mute">Layout do browser</span>
            <select id="dspico-set-layout" class="field-select w-full mt-1">
              ${layouts
                .map(
                  (l) =>
                    `<option value="${escapeHtml(l)}" ${
                      s.romBrowserLayout === l ? "selected" : ""
                    }>${escapeHtml(l)}</option>`
                )
                .join("")}
            </select>
          </label>
          <label class="block text-[12px]">
            <span class="text-fg-mute">Ordenação</span>
            <select id="dspico-set-sort" class="field-select w-full mt-1">
              ${sorts
                .map(
                  (l) =>
                    `<option value="${escapeHtml(l)}" ${
                      s.romBrowserSortMode === l ? "selected" : ""
                    }>${escapeHtml(l)}</option>`
                )
                .join("")}
            </select>
          </label>
          <label class="block text-[12px]">
            <span class="text-fg-mute">Idioma</span>
            <input id="dspico-set-lang" class="field-select w-full mt-1" value="${escapeHtml(
              s.language || "english"
            )}">
          </label>
          <button type="button" class="btn-primary" id="dspico-save-settings">Guardar definições</button>
        </section>`;
      document.getElementById("dspico-save-settings").onclick = async () => {
        const patch = {
          theme: document.getElementById("dspico-set-theme").value.trim(),
          romBrowserLayout: document.getElementById("dspico-set-layout").value,
          romBrowserSortMode: document.getElementById("dspico-set-sort").value,
          language: document.getElementById("dspico-set-lang").value.trim() || "english",
        };
        setBusy(true);
        try {
          const res = await api.set_dspico_settings(m, patch);
          if (res && res.success) appendLog(res.message, "success");
          else appendLog((res && res.error) || "Falha", "error");
        } finally {
          setBusy(false);
          refresh();
        }
      };
    } catch (e) {
      if (gen !== renderGen) return;
      el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
        e.message || String(e)
      )}</p></section>`;
    }
  }

  async function renderFirmware(gen, m) {
    const el = document.getElementById("dspico-section-firmware");
    if (!el) return;
    // Firmware não precisa do SD seleccionado, mas mostramos contexto
    el.innerHTML = `<section class="panel p-5"><p class="text-fg-mute text-[12px]">A procurar RPI-RP2…</p></section>`;
    try {
      const api = getApi() || (await waitForApi());
      const data = await api.list_rp2_volumes();
      if (gen !== renderGen) return;
      const ready = !!(data && data.firmware_uf2_ready);
      const vols = (data && data.volumes) || [];
      let links = {};
      try {
        const lr = await api.get_dspico_official_links();
        links = (lr && lr.links) || {};
      } catch (_e) {
        /* ignore */
      }

      const volOptions = vols.length
        ? vols
            .map(
              (v) =>
                `<option value="${escapeHtml(v.mount_path)}">${escapeHtml(
                  v.name
                )} — ${escapeHtml(v.mount_path)}</option>`
            )
            .join("")
        : '<option value="">Nenhum volume RPI-RP2 detectado</option>';

      el.innerHTML = `
        <section class="panel p-5 space-y-4">
          <div>
            <h3 class="text-sm font-semibold text-fg">Firmware do cartucho (RP2040)</h3>
            <p class="text-[12px] text-fg-mute mt-1 leading-relaxed">
              O firmware <strong>não</strong> vai no microSD. Em BOOTSEL aparece o volume
              <code>RPI-RP2</code>. Só gravamos o <code>.uf2</code> oficial pinado de
              <code>LNH-team/dspico-firmware</code> — sem ficheiros de terceiros.
            </p>
          </div>
          <ol class="guide-list list-decimal text-[12px] text-fg-soft space-y-1">
            <li>Retire o microSD do cartucho (ou use BOOTSEL se o firmware já estiver instalado).</li>
            <li>Ligue o DSPico ao PC por USB até aparecer <code>RPI-RP2</code>.</li>
            <li>Actualize a lista abaixo e grave o UF2 oficial (quando disponível nas releases LNH).</li>
          </ol>
          <div class="note ${ready ? "note--ok" : "note--warn"}">
            ${
              ready
                ? "Asset .uf2 oficial pinado — pode gravar."
                : "As releases LNH actuais <strong>não publicam</strong> DSpico.uf2 (é preciso compilar via GUIDE). O botão de gravação fica desactivado até existir pin oficial — builds community/hybrid são rejeitados."
            }
          </div>
          <div class="flex flex-col sm:flex-row gap-2 items-stretch sm:items-end">
            <label class="flex-1 text-[12px]">
              <span class="text-fg-mute">Volume RPI-RP2</span>
              <select id="dspico-rp2-select" class="field-select w-full mt-1">${volOptions}</select>
            </label>
            <button type="button" class="btn-ghost" id="dspico-rp2-refresh">Procurar RPI-RP2</button>
          </div>
          <button type="button" class="btn-primary" id="dspico-flash-uf2" ${
            ready && vols.length ? "" : "disabled"
          }>Descarregar e gravar UF2 oficial</button>
          ${linksHtml(links)}
        </section>`;
      bindLinkButtons(el);
      document.getElementById("dspico-rp2-refresh").onclick = () => refresh();
      const flash = document.getElementById("dspico-flash-uf2");
      if (flash) {
        flash.onclick = async () => {
          const sel = document.getElementById("dspico-rp2-select");
          const path = sel && sel.value;
          if (!path) {
            alert("Nenhum volume RPI-RP2 seleccionado.");
            return;
          }
          if (
            !confirm(
              "Gravar o firmware DSPico oficial no cartucho?\n\n" +
                "Só o asset pinado de LNH-team/dspico-firmware será usado."
            )
          ) {
            return;
          }
          setBusy(true);
          try {
            const res = await api.flash_dspico_firmware(path);
            if (res && res.success) appendLog(res.message, "success");
            else appendLog((res && res.error) || "Falha", "error");
          } finally {
            setBusy(false);
            refresh();
          }
        };
      }
    } catch (e) {
      if (gen !== renderGen) return;
      el.innerHTML = `<section class="panel p-5"><p class="text-danger text-[12px]">${escapeHtml(
        e.message || String(e)
      )}</p></section>`;
    }
  }

  return {
    enter,
    refresh,
    setSection,
    onNativeDrop,
    addGames,
    importPaths,
    openArtPanel,
    closeArtPanel,
    runDspicoArtworkBatch,
  };
})();
