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

  function mount(view) {
    if (mounted[view]) return;
    mounted[view] = true;
    if (view === "softmod" && typeof Wizard !== "undefined" && Wizard.render) {
      Wizard.render();
    }
    if (view === "dspico" && typeof Dspico !== "undefined" && Dspico.enter) {
      Dspico.enter();
    }
    if (view === "card" && typeof RomExplorer !== "undefined" && RomExplorer.refresh) {
      RomExplorer.refresh();
    }
    if (view === "utilidades" && window.R1K.utilidades && R1K.utilidades.ensure) {
      R1K.utilidades.ensure();
    }
    if (view === "settings") {
      if (typeof loadAboutPage === "function") loadAboutPage();
      const host = $("settings-theme-host");
      if (host && typeof Theme !== "undefined" && Theme.list) {
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
    if (typeof busy !== "undefined" && busy && !silent) {
      alert("Aguarde a operação em andamento terminar antes de mudar de ecrã.");
      return;
    }
    if (!VIEWS.includes(view)) view = "home";
    relocateLegacyPanels();
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
