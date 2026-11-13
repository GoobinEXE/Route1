/**
 * Router da shell — quatro vistas (Início, DSPico, Mais ferramentas, Definições),
 * abas por vista e navegação por teclado. Mount preguiçoso por vista/aba.
 */
(function () {
  const STORAGE_KEY = "route_pico_view_v3";
  const VIEWS = ["home", "dspico", "tools", "settings"];
  const TOOLS_SECTIONS = ["softmod", "flashcards", "twilight", "homebrew", "card"];
  // Vistas e modos antigos (sessão anterior) → vista/aba atual.
  const LEGACY_VIEWS = {
    softmod: ["tools", "softmod"],
    card: ["tools", "twilight"],
    others: ["tools", "flashcards"],
    utilidades: ["dspico", "extras"],
  };

  let current = "home";
  let toolsSection = "softmod";
  let activityOpen = false;
  const mounted = Object.create(null);
  const toolsMounted = Object.create(null);

  function $(id) {
    return document.getElementById(id);
  }

  function hardBusy() {
    return typeof isHardBusy === "function" ? isHardBusy() : typeof busy !== "undefined" && busy;
  }

  function syncNav() {
    document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
      const on = btn.getAttribute("data-view") === current;
      btn.classList.toggle("nav-item--active", on);
      if (on) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    });
  }

  function showPane(view) {
    document.querySelectorAll("[data-view-pane]").forEach((pane) => {
      pane.classList.toggle("hidden", pane.getAttribute("data-view-pane") !== view);
    });
  }

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
      alert("Aguarde a operação em andamento terminar antes de mudar de secção.");
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
    if (current === "tools") mountToolsSection(name);
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

  function updateHomeDrive() {
    const el = $("home-drive-summary");
    if (!el) return;
    if (typeof selectedDrive !== "undefined" && selectedDrive) {
      const role = driveRoleLabel();
      const size = selectedDrive.total_size_gb != null ? `${selectedDrive.total_size_gb} GB` : "?";
      el.textContent = `${role}: ${selectedDrive.name || selectedDrive.mount_path} · ${selectedDrive.fs_type || "?"} · ${size}`;
    } else {
      el.textContent = "Nenhuma unidade seleccionada. Ligue o microSD e escolha-o na barra de cima.";
    }
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
  }

  function persist() {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ view: current, tools: toolsSection }));
    } catch (e) {
      /* ignore */
    }
  }

  function navigate(view, { silent } = {}) {
    if (hardBusy() && !silent) {
      alert("Aguarde a operação em andamento terminar antes de mudar de ecrã.");
      return;
    }
    if (LEGACY_VIEWS[view]) {
      const [v, sec] = LEGACY_VIEWS[view];
      go(v, sec, { silent });
      return;
    }
    if (!VIEWS.includes(view)) view = "home";
    if (current === "dspico" && view !== "dspico" && typeof Dspico !== "undefined" && Dspico.leave) {
      Dspico.leave();
    }
    current = view;
    persist();
    showPane(view);
    syncNav();
    mount(view);
    refreshRoleBadge();
    updateHomeDrive();
  }

  /** Atalho: vista + aba (DSPico ou Mais ferramentas). */
  function go(view, section, opts) {
    if (view === "tools" && section) toolsSection = TOOLS_SECTIONS.includes(section) ? section : toolsSection;
    if (view === "tools" && section) setToolsSection(toolsSection, { silent: true });
    if (view === "dspico" && section && typeof Dspico !== "undefined" && Dspico.selectSection) {
      Dspico.selectSection(section);
    }
    navigate(view, opts);
  }

  function toggleActivity(force) {
    activityOpen = typeof force === "boolean" ? force : !activityOpen;
    const drawer = $("activity-drawer");
    if (drawer) drawer.classList.toggle("activity-drawer--open", activityOpen);
  }

  // --- Navegação por teclado (D-pad): setas entre abas, Alt+1..4 entre vistas ---
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

  function onGlobalKeys(ev) {
    if (ev.altKey && !ev.ctrlKey && !ev.metaKey && /^[1-4]$/.test(ev.key)) {
      ev.preventDefault();
      navigate(VIEWS[Number(ev.key) - 1]);
      return;
    }
    if (ev.key === "Escape" && activityOpen) {
      toggleActivity(false);
    }
  }

  function setSgdbStatus(text, ok) {
    const el = $("sgdb-api-status");
    if (!el) return;
    el.textContent = text || "";
    el.className =
      "text-[12px] " + (ok ? "text-ok" : text ? "text-fg-mute" : "text-fg-mute");
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
            input.placeholder = "Chave guardada — cole outra para substituir";
            setSgdbStatus(
              "Chave SteamGridDB guardada. Capas/ícones usam-na como fonte principal.",
              true
            );
          } else {
            setSgdbStatus(
              (res && res.error) || "Não foi possível guardar a chave.",
              false
            );
          }
        } catch (e) {
          setSgdbStatus("Falha ao guardar a chave.", false);
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
            setSgdbStatus(
              "Chave removida. Fallback: GameTDB + Libretro.",
              true
            );
          } else {
            setSgdbStatus(
              (res && res.error) || "Não foi possível remover a chave.",
              false
            );
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
      const configured =
        res &&
        res.success &&
        res.prefs &&
        res.prefs.steamgriddb_configured === true;
      if (configured) {
        input.placeholder = "Chave guardada — cole outra para substituir";
        setSgdbStatus("SteamGridDB activo (fonte principal de capas/ícones).", true);
      } else {
        input.placeholder = "Cole a chave aqui";
        setSgdbStatus(
          "Sem chave — capas usam GameTDB (NDS) e Libretro.",
          false
        );
      }
    } catch (e) {
      setSgdbStatus("Não foi possível ler as preferências.", false);
    }
  }

  function init() {
    let initial = "home";
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      const saved = raw ? JSON.parse(raw) : null;
      if (saved && VIEWS.includes(saved.view)) initial = saved.view;
      if (saved && TOOLS_SECTIONS.includes(saved.tools)) toolsSection = saved.tools;
    } catch (e) {
      /* ignore */
    }
    setToolsSection(toolsSection, { silent: true });
    navigate(initial, { silent: true });

    document.addEventListener("keydown", onTabKeys);
    document.addEventListener("keydown", onGlobalKeys);

    if (window.R1K.events) {
      R1K.events.on("busy", (p) => {
        if (p && p.busy) toggleActivity(true);
      });
    }
  }

  window.R1K = window.R1K || {};
  window.R1K.shell = {
    navigate,
    go,
    setToolsSection,
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
