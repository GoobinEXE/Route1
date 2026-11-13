/**
 * Router da shell — menu de console.
 *
 * O Início é um menu de blocos; cada bloco abre uma tela (vista + aba) com
 * Voltar. Há histórico (hash), setas para mover entre blocos, Enter para abrir
 * e Esc / Backspace para voltar. Mount preguiçoso por vista/aba, como antes.
 * API pública mantida: navigate, go, setToolsSection, toggleActivity, current,
 * driveRoleLabel, refreshRoleBadge, updateHomeDrive.
 */
(function () {
  const STORAGE_KEY = "route_pico_view_v4";
  const VIEWS = ["home", "dspico", "tools", "settings"];
  const TOOLS_SECTIONS = ["softmod", "flashcards", "twilight", "homebrew", "card"];
  const DSPICO_SECTIONS = ["cartao", "games", "routedex", "launcher", "extras", "avancado"];
  // Vistas e modos antigos (sessão anterior) → vista/aba atual.
  const LEGACY_VIEWS = {
    softmod: ["tools", "softmod"],
    card: ["tools", "twilight"],
    others: ["tools", "flashcards"],
    utilidades: ["dspico", "extras"],
  };

  /** Título, texto e ícone de cada tela (o mesmo texto dos blocos do Início). */
  const SCREENS = {
    "dspico:cartao": ["Cartão", "Estado do microSD, pacote oficial e atualizações", "i-card", 3],
    "dspico:games": ["Jogos", "Importar jogos, organizar pastas e capas", "i-games", 1],
    "dspico:routedex": ["RouteDex", "Favoritos, tempo de jogo e saúde do cartão", "i-dex", 5],
    "dspico:launcher": ["Launcher", "settings.json, temas e fundos noturnos", "i-launcher", 7],
    "dspico:extras": ["Emuladores e apps", "Emuladores do Pico Launcher e apps USB", "i-extras", 2],
    "dspico:avancado": ["Avançado", "Emunand, BIOS e firmware do cartucho", "i-chip", 4],
    "tools:softmod": ["Softmod DSi", "Assistente: exploit, backup da NAND e Unlaunch", "i-handheld", 3],
    "tools:flashcards": ["Flashcards R4/GEi", "Kernel e TWiLight para cartuchos R4 e GEi", "i-flash", 6],
    "tools:twilight": ["Biblioteca TWiLight", "ROMs em /roms/, capas e cheats", "i-moon", 7],
    "tools:homebrew": ["Apps homebrew", "Catálogo de apps para instalar no cartão", "i-flask", 2],
    "tools:card": ["Manutenção", "Formatar, backup, limpeza e relatório do cartão", "i-wrench", 4],
    settings: ["Configurações", "SteamGridDB, aparência e sobre o app", "i-gear", 0],
  };

  let current = "home";
  let toolsSection = "softmod";
  let dspicoSection = "cartao";
  let activityOpen = false;
  let lastTile = null;
  let depth = 0; // entradas empilhadas desde o Início (Voltar usa o histórico)
  const mounted = Object.create(null);
  const toolsMounted = Object.create(null);

  function $(id) {
    return document.getElementById(id);
  }

  function hardBusy() {
    return typeof isHardBusy === "function" ? isHardBusy() : typeof busy !== "undefined" && busy;
  }

  function screenKey() {
    if (current === "dspico") return `dspico:${dspicoSection}`;
    if (current === "tools") return `tools:${toolsSection}`;
    return current;
  }

  /* ------------------------------------------------------------ cabeçalho */

  function syncScreen() {
    const key = screenKey();
    const head = $("screen-head");
    const meta = SCREENS[key];
    document.documentElement.setAttribute("data-screen", current);
    if (head) head.classList.toggle("hidden", current === "home" || !meta);
    const where = $("status-where");
    if (where) where.textContent = meta ? meta[0] : "Início";
    if (meta) {
      const [title, sub, icon, hue] = meta;
      if ($("screen-title")) $("screen-title").textContent = title;
      if ($("screen-sub")) $("screen-sub").textContent = sub;
      const ic = $("screen-icon");
      if (ic) {
        ic.setAttribute("data-hue", String(hue));
        const use = ic.querySelector("use");
        if (use) use.setAttribute("href", `#${icon}`);
      }
    }
    document.querySelectorAll(".dock-btn[data-dock]").forEach((btn) => {
      const target = btn.getAttribute("data-dock");
      const on = target === current;
      btn.classList.toggle("dock-btn--active", on);
      if (target === "home" || target === "settings") {
        if (on) btn.setAttribute("aria-current", "page");
        else btn.removeAttribute("aria-current");
      }
    });
    setHint(current === "home" ? captionText() : meta ? meta[0] : "");
  }

  function showPane(view) {
    document.querySelectorAll("[data-view-pane]").forEach((pane) => {
      pane.classList.toggle("hidden", pane.getAttribute("data-view-pane") !== view);
    });
  }

  /* ------------------------------------------------------------ vistas */

  function mountToolsSection(name) {
    if (name === "softmod" && typeof Wizard !== "undefined" && Wizard.render && !toolsMounted.softmod) {
      Wizard.render();
    }
    if (name === "twilight" && typeof RomExplorer !== "undefined" && RomExplorer.refresh) {
      RomExplorer.refresh();
    }
    if (name === "homebrew" && typeof loadHomebrewCatalog === "function") {
      loadHomebrewCatalog();
    }
    toolsMounted[name] = true;
  }

  function setToolsSection(name, { silent } = {}) {
    if (hardBusy() && !silent) {
      alert("Aguarde a operação em andamento terminar antes de mudar de seção.");
      return;
    }
    if (!TOOLS_SECTIONS.includes(name)) name = "softmod";
    toolsSection = name;
    for (const key of TOOLS_SECTIONS) {
      const pane = $(`tools-pane-${key}`);
      const tab = $(`tools-tab-${key}`);
      const on = key === name;
      if (pane) pane.classList.toggle("hidden", !on);
      if (tab) {
        tab.classList.toggle("adv-tab--active", on);
        tab.setAttribute("aria-selected", on ? "true" : "false");
        tab.tabIndex = on ? 0 : -1;
      }
    }
    if (current === "tools") {
      mountToolsSection(name);
      syncScreen();
      pushRoute(false);
    }
    persist();
  }

  /** Chamado pelo dspico.js quando a aba DSPico muda. */
  function onDspicoSection(name) {
    if (!DSPICO_SECTIONS.includes(name)) return;
    dspicoSection = name;
    if (current === "dspico") {
      syncScreen();
      pushRoute(false);
    }
    persist();
  }

  function mount(view) {
    // DSPico: re-entrar sempre (poll USB MSC + refresh).
    if (view === "dspico" && typeof Dspico !== "undefined" && Dspico.enter) {
      Dspico.enter();
      return;
    }
    if (view === "settings") {
      if (typeof loadAboutPage === "function") loadAboutPage();
      if (typeof Theme !== "undefined" && Theme.renderList) Theme.renderList($("settings-theme-host"));
      loadSteamGridDbPrefs();
      return;
    }
    if (view === "tools") {
      mountToolsSection(toolsSection);
      return;
    }
    if (mounted[view]) return;
    mounted[view] = true;
    if (view === "home") updateHomeDrive();
  }

  /* ------------------------------------------------------------ cartão */

  function driveUsage() {
    const d = typeof selectedDrive !== "undefined" ? selectedDrive : null;
    if (!d) return null;
    const total = Number(d.total_size_gb);
    const free = Number(d.free_size_gb);
    if (!(total > 0) || !(free >= 0)) return { d, used: null };
    return { d, total, free, used: Math.max(0, Math.min(100, Math.round(((total - free) / total) * 100))) };
  }

  function updateHomeDrive() {
    const info = driveUsage();
    const el = $("home-drive-summary");
    const usage = $("home-drive-usage");
    const homeEl = $("view-home");
    if (homeEl) homeEl.classList.toggle("home--nodrive", !info);
    updateStatusMeter(info);
    if (!el) return;
    if (!info) {
      el.textContent = "Nenhum microSD escolhido. Conecte o cartão e escolha-o na barra de cima.";
      if (usage) usage.classList.add("hidden");
      return;
    }
    const d = info.d;
    el.textContent = `${driveRoleLabel()} · ${d.name || d.mount_path} · ${d.fs_type || "formato desconhecido"}`;
    if (!usage || info.used === null) {
      if (usage) usage.classList.add("hidden");
      return;
    }
    usage.classList.remove("hidden");
    const fill = $("home-usage-fill");
    if (fill) fill.style.width = `${info.used}%`;
    const meter = usage.querySelector('[role="meter"]');
    if (meter) meter.setAttribute("aria-valuenow", String(info.used));
    const text = $("home-usage-text");
    if (text) text.textContent = `${info.free.toFixed(1)} GB livres de ${info.total.toFixed(1)} GB · ${info.used}% usado`;
  }

  function updateStatusMeter(info) {
    const meter = $("status-meter");
    const fill = $("status-meter-fill");
    if (!meter || !fill) return;
    if (!info || info.used === null) {
      fill.style.width = "0%";
      meter.classList.add("status-meter--empty");
      meter.setAttribute("aria-label", "Espaço usado no cartão: sem cartão");
      meter.title = "Sem cartão escolhido";
      return;
    }
    meter.classList.remove("status-meter--empty");
    meter.classList.toggle("status-meter--full", info.used >= 90);
    fill.style.width = `${info.used}%`;
    const label = `${info.free.toFixed(1)} GB livres (${info.used}% usado)`;
    meter.setAttribute("aria-label", `Espaço usado no cartão: ${label}`);
    meter.title = label;
  }

  function driveRoleLabel() {
    const d = typeof selectedDrive !== "undefined" ? selectedDrive : null;
    if (!d) return "Sem volume";
    const name = String(d.name || "").toUpperCase();
    const path = String(d.mount_path || "").toUpperCase();
    if (name.includes("RPI-RP2") || path.includes("RPI-RP2")) return "RPI-RP2";
    if (d.dspico_likely || current === "dspico") return "microSD DSPico";
    if (name.includes("GEI") || name.includes("R4")) return "GEi-R4";
    return "SD do DSi";
  }

  function refreshRoleBadge() {
    const badge = $("drive-role-badge");
    if (!badge) return;
    badge.textContent = driveRoleLabel();
    badge.className = "chip " + (selectedDrive ? "chip--ok" : "chip--idle");
    updateHomeDrive();
  }

  /* ------------------------------------------------------------ rotas */

  function persist() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ view: current, tools: toolsSection, dspico: dspicoSection }));
    } catch (e) {
      /* ignore */
    }
  }

  function routeHash() {
    if (current === "dspico") return `#dspico/${dspicoSection}`;
    if (current === "tools") return `#tools/${toolsSection}`;
    return `#${current}`;
  }

  /** Grava a tela no histórico; replace quando só muda a aba dentro da tela. */
  function pushRoute(push) {
    const hash = routeHash();
    if (location.hash === hash) return;
    try {
      const state = { r1k: true, view: current, sec: current === "tools" ? toolsSection : dspicoSection };
      if (push) history.pushState(state, "", hash);
      else history.replaceState(state, "", hash);
    } catch (e) {
      /* file:// sem histórico: ignorar */
    }
  }

  function navigate(view, { silent, fromHistory } = {}) {
    if (hardBusy() && !silent) {
      alert("Aguarde a operação em andamento terminar antes de mudar de tela.");
      if (fromHistory) pushRoute(true);
      return;
    }
    if (LEGACY_VIEWS[view]) {
      const [v, sec] = LEGACY_VIEWS[view];
      go(v, sec, { silent });
      return;
    }
    if (!VIEWS.includes(view)) view = "home";
    const changed = view !== current;
    if (current === "dspico" && view !== "dspico" && typeof Dspico !== "undefined" && Dspico.leave) {
      Dspico.leave();
    }
    current = view;
    persist();
    showPane(view);
    mount(view);
    refreshRoleBadge();
    syncScreen();
    if (fromHistory) {
      depth = view === "home" ? 0 : Math.max(depth, 1);
    } else if (view === "home") {
      depth = 0;
      pushRoute(false);
    } else if (changed && depth === 0) {
      depth = 1;
      pushRoute(true);
    } else {
      pushRoute(false);
    }
    const content = $("app-content");
    if (content && changed) content.scrollTop = 0;
    if (changed) focusAfterNavigate(view);
  }

  function focusAfterNavigate(view) {
    // Leva o foco para onde o usuário continua: o bloco de onde veio, ou o Voltar.
    requestAnimationFrame(() => {
      if (view === "home") {
        const t = lastTile && document.contains(lastTile) ? lastTile : document.querySelector(".tile");
        if (t && document.activeElement && document.activeElement !== document.body) t.focus({ preventScroll: true });
        return;
      }
      const back = document.querySelector(".screen-back");
      if (back && document.activeElement && document.activeElement.closest && document.activeElement.closest(".home-menu, .dock-bar")) {
        back.focus({ preventScroll: true });
      }
    });
  }

  /** Atalho: vista + aba (DSPico ou Mais ferramentas). */
  function go(view, section, opts) {
    if (view === "tools" && section) {
      toolsSection = TOOLS_SECTIONS.includes(section) ? section : toolsSection;
      setToolsSection(toolsSection, { silent: true });
    }
    if (view === "dspico" && section) {
      if (DSPICO_SECTIONS.includes(section)) dspicoSection = section;
      if (typeof Dspico !== "undefined" && Dspico.selectSection) Dspico.selectSection(section);
    }
    navigate(view, opts);
  }

  function back() {
    if (current === "home") return;
    if (hardBusy()) {
      alert("Aguarde a operação em andamento terminar antes de voltar.");
      return;
    }
    if (depth > 0) {
      try {
        history.back();
        return;
      } catch (e) {
        /* sem histórico: navegar direto */
      }
    }
    navigate("home");
  }

  function onPopState() {
    const raw = (location.hash || "#home").slice(1).split("/");
    const view = VIEWS.includes(raw[0]) ? raw[0] : "home";
    const sec = raw[1];
    if (view === "tools" && sec && TOOLS_SECTIONS.includes(sec)) setToolsSection(sec, { silent: true });
    if (view === "dspico" && sec && DSPICO_SECTIONS.includes(sec)) {
      dspicoSection = sec;
      if (typeof Dspico !== "undefined" && Dspico.selectSection) Dspico.selectSection(sec);
    }
    navigate(view, { fromHistory: true });
  }

  /* ------------------------------------------------------------ menu */

  function captionText() {
    const t = lastTile || document.querySelector(".tile");
    if (!t) return "";
    const label = t.querySelector(".tile-label");
    return label ? label.textContent : "";
  }

  function setCaption(tile) {
    if (!tile) return;
    lastTile = tile;
    document.querySelectorAll(".tile--current").forEach((t) => t !== tile && t.classList.remove("tile--current"));
    tile.classList.add("tile--current");
    const label = tile.querySelector(".tile-label");
    const desc = tile.querySelector(".tile-desc");
    if ($("home-caption-title")) $("home-caption-title").textContent = label ? label.textContent : "";
    if ($("home-caption-text")) $("home-caption-text").textContent = desc ? desc.textContent : "";
    const cap = $("home-caption");
    if (cap) cap.setAttribute("data-hue", tile.getAttribute("data-hue") || "0");
    if (current === "home") setHint(label ? label.textContent : "");
    // Fileiras horizontais (Câmera Dupla, Híbrido): manter o bloco à vista.
    const row = [tile.closest(".home-tiles"), tile.closest(".home-menu")].find(
      (el) => el && el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).display !== "contents"
    );
    if (row) {
      const r = tile.getBoundingClientRect();
      const rr = row.getBoundingClientRect();
      if (r.left < rr.left + 24 || r.right > rr.right - 24) {
        const target = row.scrollLeft + (r.left - rr.left) - row.clientWidth / 2 + r.width / 2;
        row.scrollTo({ left: target, behavior: reducedMotion() ? "auto" : "smooth" });
      }
    }
  }

  function setHint(text) {
    const el = $("hint-context");
    if (el) el.textContent = text || "Pronto";
  }

  function reducedMotion() {
    return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function openTile(tile) {
    const target = tile.getAttribute("data-go") || "";
    lastTile = tile;
    const [view, sec] = target.split(":");
    if (sec) go(view, sec);
    else navigate(view);
  }

  /** Barra de rolagem da fileira (Câmera Dupla): marcador, clique e setas. */
  function bindScrub() {
    const menu = document.querySelector(".home-menu");
    const track = $("scrub-track");
    const thumb = $("scrub-thumb");
    if (!menu || !track || !thumb) return;
    const sync = () => {
      const max = menu.scrollWidth - menu.clientWidth;
      const ratio = menu.scrollWidth > 0 ? menu.clientWidth / menu.scrollWidth : 1;
      const w = Math.max(12, Math.min(100, ratio * 100));
      thumb.style.width = `${w}%`;
      thumb.style.left = max > 0 ? `${(menu.scrollLeft / max) * (100 - w)}%` : "0%";
    };
    menu.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync);
    track.addEventListener("click", (ev) => {
      const r = track.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
      menu.scrollTo({ left: f * (menu.scrollWidth - menu.clientWidth), behavior: reducedMotion() ? "auto" : "smooth" });
    });
    document.querySelectorAll("[data-scrub]").forEach((btn) =>
      btn.addEventListener("click", () => {
        const step = Number(btn.getAttribute("data-scrub")) * menu.clientWidth * 0.6;
        menu.scrollBy({ left: step, behavior: reducedMotion() ? "auto" : "smooth" });
      })
    );
    sync();
    document.addEventListener("r1k-theme", sync);
    setTimeout(sync, 300);
  }

  function bindMenu() {
    document.querySelectorAll(".tile").forEach((tile) => {
      tile.addEventListener("click", () => openTile(tile));
      tile.addEventListener("focus", () => setCaption(tile));
      tile.addEventListener("mouseenter", () => setCaption(tile));
    });
    const first = document.querySelector(".tile");
    if (first) setCaption(first);
  }

  /** Setas no Início: move para o vizinho mais próximo naquela direção. */
  function spatialMove(ev) {
    if (current !== "home") return false;
    const from = ev.target;
    if (!from || !from.closest || !from.closest(".home-menu, .dock-bar")) return false;
    const dirs = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    const d = dirs[ev.key];
    if (!d) return false;
    const items = Array.from(document.querySelectorAll(".home-menu .tile, .dock-bar .dock-btn")).filter(
      (el) => el.offsetParent !== null
    );
    const a = from.getBoundingClientRect();
    const ax = a.left + a.width / 2;
    const ay = a.top + a.height / 2;
    let best = null;
    let bestScore = Infinity;
    for (const el of items) {
      if (el === from) continue;
      const b = el.getBoundingClientRect();
      const dx = b.left + b.width / 2 - ax;
      const dy = b.top + b.height / 2 - ay;
      const along = dx * d[0] + dy * d[1];
      if (along <= 4) continue;
      const across = Math.abs(dx * d[1]) + Math.abs(dy * d[0]);
      const score = along + across * 2.2;
      if (score < bestScore) {
        bestScore = score;
        best = el;
      }
    }
    if (!best) return false;
    ev.preventDefault();
    best.focus();
    return true;
  }

  /* ------------------------------------------------------------ atividade */

  function toggleActivity(force) {
    activityOpen = typeof force === "boolean" ? force : !activityOpen;
    const drawer = $("activity-drawer");
    if (drawer) {
      drawer.classList.toggle("activity-drawer--open", activityOpen);
      drawer.setAttribute("aria-hidden", activityOpen ? "false" : "true");
    }
    const btn = $("btn-activity-toggle");
    if (btn) {
      btn.setAttribute("aria-expanded", activityOpen ? "true" : "false");
      btn.classList.toggle("dock-btn--active", activityOpen);
    }
  }

  /* ------------------------------------------------------------ teclado */

  function onTabKeys(ev) {
    const list = ev.target.closest && ev.target.closest('[role="tablist"]');
    if (!list || !ev.target.matches('[role="tab"]')) return;
    const tabs = Array.from(list.querySelectorAll('[role="tab"]')).filter((t) => !t.hidden);
    const i = tabs.indexOf(ev.target);
    let next = -1;
    if (ev.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (ev.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    else if (ev.key === "Home") next = 0;
    else if (ev.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    ev.preventDefault();
    tabs[next].focus();
    tabs[next].click();
  }

  function typingTarget(el) {
    if (!el) return false;
    const tag = (el.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable;
  }

  function anyOverlayOpen() {
    const art = $("dspico-art-panel");
    if (art && !art.classList.contains("hidden")) return true;
    const menu = $("theme-menu");
    return !!(menu && !menu.classList.contains("hidden"));
  }

  function onGlobalKeys(ev) {
    if (ev.altKey && !ev.ctrlKey && !ev.metaKey && /^[1-4]$/.test(ev.key)) {
      ev.preventDefault();
      const n = Number(ev.key);
      if (n === 2) go("dspico", "cartao");
      else if (n === 3) go("tools", toolsSection);
      else navigate(n === 1 ? "home" : "settings");
      return;
    }
    if (ev.defaultPrevented) return;
    if (spatialMove(ev)) return;
    if (ev.key === "Escape") {
      if (activityOpen) {
        toggleActivity(false);
        const b = $("btn-activity-toggle");
        if (b) b.focus();
        return;
      }
      if (anyOverlayOpen()) return;
      if (current !== "home" && !typingTarget(ev.target)) {
        ev.preventDefault();
        back();
      }
      return;
    }
    if (ev.key === "Backspace" && current !== "home" && !typingTarget(ev.target) && !anyOverlayOpen()) {
      ev.preventDefault();
      back();
    }
  }

  /* ------------------------------------------------------------ relógio */

  const WEEK = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
  let clockTimer = null;

  function tickClock() {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, "0");
    const mm = String(now.getMinutes()).padStart(2, "0");
    const date = `${WEEK[now.getDay()]} ${String(now.getDate()).padStart(2, "0")}/${String(now.getMonth() + 1).padStart(2, "0")}`;
    document.querySelectorAll('[data-clock="time"]').forEach((el) => (el.textContent = `${hh}:${mm}`));
    document.querySelectorAll('[data-clock="date"]').forEach((el) => (el.textContent = date));
    // Um disparo por minuto, alinhado à virada do minuto (sem polling do backend).
    clearTimeout(clockTimer);
    clockTimer = setTimeout(tickClock, 60000 - (now.getSeconds() * 1000 + now.getMilliseconds()) + 50);
  }

  /* ------------------------------------------------------------ SteamGridDB */

  function setSgdbStatus(text, ok) {
    const el = $("sgdb-api-status");
    if (!el) return;
    el.textContent = text || "";
    el.className = "text-[12px] " + (ok ? "text-ok" : "text-fg-mute");
  }

  async function loadSteamGridDbPrefs() {
    const input = $("sgdb-api-key");
    const saveBtn = $("sgdb-api-save");
    const clearBtn = $("sgdb-api-clear");
    if (!input || !saveBtn || !clearBtn) return;

    if (!input.dataset.bound) {
      input.dataset.bound = "1";
      saveBtn.addEventListener("click", async () => {
        const api = typeof getApi === "function" ? getApi() : null;
        if (!api || typeof api.set_prefs !== "function") {
          setSgdbStatus("API indisponível.", false);
          return;
        }
        const raw = String(input.value || "").trim();
        if (!raw) {
          setSgdbStatus("Cole uma chave ou use «Remover chave».", false);
          return;
        }
        try {
          const res = await api.set_prefs({ steamgriddb_api_key: raw });
          if (res && res.success) {
            input.value = "";
            input.placeholder = "Chave salva — cole outra para substituir";
            setSgdbStatus("Chave SteamGridDB salva. Capas/ícones a usam como fonte principal.", true);
          } else {
            setSgdbStatus((res && res.error) || "Não foi possível salvar a chave.", false);
          }
        } catch (e) {
          setSgdbStatus("Falha ao salvar a chave.", false);
        }
      });
      clearBtn.addEventListener("click", async () => {
        const api = typeof getApi === "function" ? getApi() : null;
        if (!api || typeof api.set_prefs !== "function") {
          setSgdbStatus("API indisponível.", false);
          return;
        }
        try {
          const res = await api.set_prefs({ steamgriddb_api_key: "" });
          if (res && res.success) {
            input.value = "";
            input.placeholder = "Cole a chave aqui";
            setSgdbStatus("Chave removida. Fallback: GameTDB + Libretro.", true);
          } else {
            setSgdbStatus((res && res.error) || "Não foi possível remover a chave.", false);
          }
        } catch (e) {
          setSgdbStatus("Falha ao remover a chave.", false);
        }
      });
    }

    const api = typeof getApi === "function" ? getApi() : null;
    if (!api || typeof api.get_prefs !== "function") {
      setSgdbStatus("API indisponível.", false);
      return;
    }
    try {
      const res = await api.get_prefs();
      const configured = res && res.success && res.prefs && res.prefs.steamgriddb_configured === true;
      if (configured) {
        input.placeholder = "Chave salva — cole outra para substituir";
        setSgdbStatus("SteamGridDB ativo (fonte principal de capas/ícones).", true);
      } else {
        input.placeholder = "Cole a chave aqui";
        setSgdbStatus("Sem chave — capas usam GameTDB (NDS) e Libretro.", false);
      }
    } catch (e) {
      setSgdbStatus("Não foi possível ler as preferências.", false);
    }
  }

  /* ------------------------------------------------------------ arranque */

  function init() {
    let initial = "home";
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      const saved = raw ? JSON.parse(raw) : null;
      if (saved && VIEWS.includes(saved.view)) initial = saved.view;
      if (saved && TOOLS_SECTIONS.includes(saved.tools)) toolsSection = saved.tools;
      if (saved && DSPICO_SECTIONS.includes(saved.dspico)) dspicoSection = saved.dspico;
    } catch (e) {
      /* ignore */
    }
    const fromHash = (location.hash || "").slice(1).split("/");
    if (VIEWS.includes(fromHash[0])) {
      initial = fromHash[0];
      if (initial === "tools" && TOOLS_SECTIONS.includes(fromHash[1])) toolsSection = fromHash[1];
      if (initial === "dspico" && DSPICO_SECTIONS.includes(fromHash[1])) dspicoSection = fromHash[1];
    }
    bindMenu();
    bindScrub();
    setToolsSection(toolsSection, { silent: true });
    if (typeof Dspico !== "undefined" && Dspico.selectSection) Dspico.selectSection(dspicoSection);
    // A primeira tela substitui a entrada do histórico (Voltar leva ao Início).
    if (initial !== "home") {
      try {
        history.replaceState({ r1k: true, view: "home" }, "", "#home");
      } catch (e) {
        /* ignore */
      }
      current = "home";
      showPane("home");
      navigate(initial, { silent: true });
    } else {
      current = "__boot__";
      navigate("home", { silent: true, fromHistory: true });
      pushRoute(false);
    }
    tickClock();

    document.addEventListener("keydown", onTabKeys);
    document.addEventListener("keydown", onGlobalKeys);
    window.addEventListener("popstate", onPopState);

    if (window.R1K.events) {
      R1K.events.on("busy", (p) => {
        const badge = $("activity-badge");
        if (badge) badge.classList.toggle("hidden", !(p && p.busy));
        if (p && p.busy) toggleActivity(true);
      });
    }
  }

  window.R1K = window.R1K || {};
  window.R1K.shell = {
    navigate,
    go,
    back,
    setToolsSection,
    onDspicoSection,
    toggleActivity,
    init,
    current: () => current,
    driveRoleLabel,
    refreshRoleBadge,
    updateHomeDrive,
  };

  document.addEventListener("DOMContentLoaded", () => {
    // Depois do boot de app.js (shell carrega antes de app.js).
    setTimeout(init, 0);
  });
})();
