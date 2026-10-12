/**
 * Router da shell v2 — vistas por data-view, mount preguiçoso.
 */
(function () {
  const STORAGE_KEY = "route_1_kit_view_v2";
  const VIEWS = ["home", "dspico", "softmod", "utilidades", "card", "others", "settings"];

  let current = "home";
  let activityOpen = false;
  let relocated = false;
  const mounted = Object.create(null);

  function $(id) {
    return document.getElementById(id);
  }

  function relocateLegacyPanels() {
    if (relocated) return;
    relocated = true;
    const cardHost = $("card-host");
    const othersHost = $("others-host");
    const utilApps = $("util-apps-host");
    const softExtras = $("softmod-extras-host");

    const cardSec = $("adv-section-card");
    if (cardHost && cardSec) {
      cardSec.classList.remove("hidden");
      cardHost.appendChild(cardSec);
    }

    const prep = $("adv-section-prepare");
    if (prep && othersHost) {
      // Move flashcard block (Slot-1) + keep softmod prepare for softmod extras
      prep.classList.remove("hidden");
      // Clone structure: put whole prepare in others for GEi/R4 access; softmod uses wizard
      othersHost.appendChild(prep);
    }

    const apps = $("adv-section-apps");
    if (apps && utilApps) {
      apps.classList.remove("hidden");
      utilApps.appendChild(apps);
    }

    const guide = $("id-guide-panel");
    if (guide && softExtras) {
      softExtras.appendChild(guide);
    }

    // Hide legacy adv tabs chrome if present
    document.querySelectorAll("#view-advanced .adv-tabs").forEach((el) => {
      el.classList.add("hidden");
    });
  }

  function syncNav() {
    document.querySelectorAll(".nav-item[data-view]").forEach((btn) => {
      const on = btn.getAttribute("data-view") === current;
      btn.classList.toggle("nav-item--active", on);
      btn.setAttribute("aria-current", on ? "page" : "false");
    });
  }

  function showPane(view) {
    document.querySelectorAll("[data-view-pane]").forEach((pane) => {
      const on = pane.getAttribute("data-view-pane") === view;
      pane.classList.toggle("hidden", !on);
    });
  }

  function ensureSgdbPanel() {
    /** Garante o painel SteamGridDB no DOM (HTML em cache / markup em falta). */
    const pane = $("view-settings");
    if (!pane) return false;
    if ($("sgdb-api-key")) return false;
    const existing = $("sgdb-settings-panel");
    if (existing) existing.remove();
    const section = document.createElement("section");
    section.id = "sgdb-settings-panel";
    section.className = "panel p-5 space-y-3 mb-5";
    section.innerHTML =
      '<h3 class="section-label">SteamGridDB — chave API</h3>' +
      '<p class="text-[12px] text-fg-mute leading-relaxed">' +
      "Necessária para capas/ícones de jogos retro (GBA, GBC, SNES, etc.). " +
      "Crie uma chave em steamgriddb.com → Preferences → API, cole e guarde." +
      "</p>" +
      '<label class="block text-[12px] text-fg-mute" for="sgdb-api-key">Chave API</label>' +
      '<input id="sgdb-api-key" type="password" autocomplete="off" spellcheck="false" ' +
      'class="w-full max-w-xl rounded-md border border-line bg-surface-2 px-3 py-2 text-[13px] text-fg" ' +
      'placeholder="Cole a chave aqui" />' +
      '<p id="sgdb-api-status" class="text-[12px] text-fg-mute"></p>' +
      '<div class="flex flex-wrap gap-2">' +
      '<button type="button" class="btn-primary" id="sgdb-api-save">Guardar chave</button>' +
      '<button type="button" class="btn-ghost" id="sgdb-api-clear">Remover chave</button>' +
      "</div>";
    const head = pane.querySelector(".page-head");
    if (head && head.nextSibling) {
      pane.insertBefore(section, head.nextSibling);
    } else {
      pane.insertBefore(section, pane.firstChild);
    }
    return true;
  }

  function mount(view) {
    // DSPico: re-entrar sempre (poll USB MSC + refresh) sem depender de mounted[].
    if (view === "dspico" && typeof Dspico !== "undefined" && Dspico.enter) {
      Dspico.enter();
      mounted[view] = true;
      return;
    }
    // Definições: re-montar sempre (painel SGDB + prefs).
    if (view === "settings") {
      mounted[view] = true;
      if (typeof loadAboutPage === "function") loadAboutPage();
      const host = $("settings-theme-host");
      if (host && typeof Theme !== "undefined" && Theme.list && !host.dataset.themesFilled) {
        host.dataset.themesFilled = "1";
        host.innerHTML = "";
        const themes = Theme.list();
        for (const t of themes) {
          const b = document.createElement("button");
          b.type = "button";
          b.className = "btn-ghost";
          b.textContent = t.label || t.id;
          b.onclick = () => Theme.set(t.id);
          host.appendChild(b);
        }
      }
      ensureSgdbPanel();
      loadSteamGridDbPrefs();
      return;
    }
    if (mounted[view]) return;
    mounted[view] = true;
    if (view === "softmod" && typeof Wizard !== "undefined" && Wizard.render) {
      Wizard.render();
    }
    if (view === "card" && typeof RomExplorer !== "undefined" && RomExplorer.refresh) {
      RomExplorer.refresh();
    }
    if (view === "utilidades" && window.R1K.utilidades && R1K.utilidades.ensure) {
      R1K.utilidades.ensure();
    }
    if (view === "home") {
      updateHomeDrive();
    }
  }

  function updateHomeDrive() {
    const el = $("home-drive-summary");
    if (!el) return;
    if (typeof selectedDrive !== "undefined" && selectedDrive) {
      const role = (window.R1K.shell && R1K.shell.driveRoleLabel()) || "Volume";
      el.textContent = `${role}: ${selectedDrive.name || selectedDrive.mount_path} · ${selectedDrive.fs_type || "?"} · ${selectedDrive.total_size_gb != null ? selectedDrive.total_size_gb + " GB" : "?"}`;
    } else {
      el.textContent = "Nenhuma unidade seleccionada.";
    }
  }

  function driveRoleLabel() {
    const d = typeof selectedDrive !== "undefined" ? selectedDrive : null;
    if (!d) return "Sem volume";
    const name = String(d.name || "").toUpperCase();
    const path = String(d.mount_path || "").toUpperCase();
    if (name.includes("RPI-RP2") || path.includes("RPI-RP2")) return "RPI-RP2";
    if (typeof appMode !== "undefined" && appMode === "dspico") return "microSD DSPico";
    if (current === "dspico") return "microSD DSPico";
    if (name.includes("GEI") || name.includes("R4")) return "GEi-R4";
    return "SD do DSi";
  }

  function refreshRoleBadge() {
    const badge = $("drive-role-badge");
    if (!badge) return;
    badge.textContent = driveRoleLabel();
    badge.className = "chip " + (selectedDrive ? "chip--ok" : "chip--idle");
  }

  function navigate(view, { silent } = {}) {
    const hard =
      typeof isHardBusy === "function"
        ? isHardBusy()
        : typeof busy !== "undefined" && busy;
    if (hard && !silent) {
      alert("Aguarde a operação em andamento terminar antes de mudar de ecrã.");
      return;
    }
    if (!VIEWS.includes(view)) view = "home";
    relocateLegacyPanels();
    const prev = current;
    if (
      prev === "dspico" &&
      view !== "dspico" &&
      typeof Dspico !== "undefined" &&
      Dspico.leave
    ) {
      Dspico.leave();
    }
    current = view;
    try {
      sessionStorage.setItem(STORAGE_KEY, current);
    } catch (e) {
      /* ignore */
    }

    // Compat com app.js / dspico / wizard
    if (typeof appMode !== "undefined") {
      if (view === "dspico") appMode = "dspico";
      else if (view === "softmod") appMode = "wizard";
      else if (view === "settings") appMode = "about";
      else if (view === "card" || view === "others" || view === "utilidades") appMode = "advanced";
      else appMode = "wizard";
    }

    showPane(view);
    syncNav();
    mount(view);
    refreshRoleBadge();
    updateHomeDrive();
  }

  function toggleActivity(force) {
    activityOpen = typeof force === "boolean" ? force : !activityOpen;
    const drawer = $("activity-drawer");
    if (drawer) drawer.classList.toggle("activity-drawer--open", activityOpen);
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
    relocateLegacyPanels();
    let initial = "home";
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (VIEWS.includes(saved)) initial = saved;
    } catch (e) {
      /* ignore */
    }
    // Migração a partir do modo antigo
    try {
      const old = sessionStorage.getItem("route_1_kit_mode");
      if (old === "dspico") initial = "dspico";
      else if (old === "wizard") initial = "softmod";
      else if (old === "about") initial = "settings";
      else if (old === "advanced") initial = "card";
    } catch (e) {
      /* ignore */
    }
    navigate(initial, { silent: true });

    if (window.R1K.events) {
      R1K.events.on("busy", (p) => {
        if (p && p.busy) toggleActivity(true);
      });
      R1K.events.on("log", () => {
        /* app.js também escuta */
      });
    }
  }

  window.R1K = window.R1K || {};
  window.R1K.shell = {
    navigate,
    toggleActivity,
    init,
    current: () => current,
    driveRoleLabel,
    refreshRoleBadge,
    updateHomeDrive,
  };

  document.addEventListener("DOMContentLoaded", () => {
    // Depois do boot de app.js (mesmo tick: defer order — shell carrega antes de app.js)
    setTimeout(init, 0);
  });
})();
