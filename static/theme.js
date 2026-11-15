/**
 * Temas — Route Pico
 *
 * Dois eixos: o tema (sete, inspirados em menus de consoles) e o modo
 * (Original, Claro = Catppuccin Latte, Noturno = Catppuccin Mocha, ou Sistema).
 * Carregado no <head> depois de theme-data.js (gerado por tools/build_themes.py)
 * para aplicar data-family / data-mode / data-scheme antes do primeiro paint.
 * As cores vivem em themes.css; a assinatura de cada tema em skins.css.
 */
const Theme = (() => {
  const STORAGE_KEY = "route_pico_theme_v2";
  const LEGACY_KEY = "route_1_kit_theme";
  const DATA = window.R1K_THEME_DATA || { families: [], defaultFamily: "dupla", defaultMode: "original" };
  const FAMILIES = Object.fromEntries(DATA.families.map((f) => [f.id, f]));
  const MODES = [
    { id: "original", label: "Original" },
    { id: "light", label: "Claro" },
    { id: "dark", label: "Noturno" },
    { id: "auto", label: "Sistema" },
  ];
  const MODE_IDS = MODES.map((m) => m.id);

  let pref = { family: DATA.defaultFamily, mode: DATA.defaultMode };
  let menuOpen = false;
  let listHost = null;

  function systemDark() {
    return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  /** Converte a preferência do tema antigo (um só eixo) para tema + modo. */
  function migrate(old) {
    const dark = ["dark", "catppuccin-frappe", "catppuccin-macchiato", "catppuccin-mocha", "dracula"];
    if (old === "catppuccin-latte") return { family: DATA.defaultFamily, mode: "light" };
    if (dark.includes(old)) return { family: DATA.defaultFamily, mode: "dark" };
    if (old === "system") return { family: DATA.defaultFamily, mode: "auto" };
    return null;
  }

  function readStored() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const v = JSON.parse(raw);
        if (v && FAMILIES[v.family] && MODE_IDS.includes(v.mode)) return v;
      }
      const legacy = migrate(localStorage.getItem(LEGACY_KEY));
      if (legacy) return legacy;
    } catch (e) {
      /* storage indisponível */
    }
    return { family: DATA.defaultFamily, mode: DATA.defaultMode };
  }

  function resolvedMode(p) {
    if (p.mode === "auto") return systemDark() ? "dark" : "light";
    return p.mode;
  }

  function apply() {
    const fam = FAMILIES[pref.family] || FAMILIES[DATA.defaultFamily];
    if (!fam) return;
    const mode = resolvedMode(pref);
    const meta = fam.modes[mode];
    const root = document.documentElement;
    root.setAttribute("data-family", fam.id);
    root.setAttribute("data-mode", mode);
    root.setAttribute("data-scheme", meta.scheme);
    const tc = document.querySelector('meta[name="theme-color"]');
    if (tc) tc.setAttribute("content", meta.swatch[0]);
  }

  function set(next = {}, { persist = true } = {}) {
    if (next.family && FAMILIES[next.family]) pref.family = next.family;
    if (next.mode && MODE_IDS.includes(next.mode)) pref.mode = next.mode;
    apply();
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(pref));
      } catch (e) {
        /* ignorar */
      }
    }
    renderAll();
    try {
      document.dispatchEvent(new Event("r1k-theme"));
    } catch (e) {
      /* ignore */
    }
  }

  function current() {
    return { family: pref.family, mode: resolvedMode(pref), preference: pref.mode };
  }

  /* ---------- seletor (menu do topo e Configurações usam o mesmo) ---------- */

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  }

  function swatchHtml(colors) {
    return `<span class="theme-swatch" aria-hidden="true">${colors
      .map((c) => `<span style="background:${esc(c)}"></span>`)
      .join("")}</span>`;
  }

  function pickerHtml(role) {
    const mode = resolvedMode(pref);
    const radio = role === "menu" ? "menuitemradio" : "radio";
    const fams = DATA.families
      .map((f) => {
        const on = f.id === pref.family;
        return `<button type="button" class="theme-item" role="${radio}" aria-checked="${on}" data-family-id="${esc(f.id)}">
          ${swatchHtml(f.modes[mode].swatch)}
          <span class="theme-item-text"><span class="theme-item-label">${esc(f.label)}</span><span class="theme-item-hint">${esc(f.hint)}</span></span>
        </button>`;
      })
      .join("");
    const modes = MODES.map(
      (m) =>
        `<button type="button" class="theme-mode" role="${radio}" aria-checked="${m.id === pref.mode}" data-mode-id="${m.id}">${m.label}</button>`
    ).join("");
    return `<div class="theme-group" id="theme-group-family-${role}">Tema</div>
      <div class="theme-families" role="group" aria-labelledby="theme-group-family-${role}">${fams}</div>
      <div class="theme-group" id="theme-group-mode-${role}">Modo</div>
      <div class="theme-modes" role="group" aria-labelledby="theme-group-mode-${role}">${modes}</div>`;
  }

  function bind(root, onPick) {
    root.querySelectorAll("[data-family-id]").forEach((b) =>
      b.addEventListener("click", () => {
        set({ family: b.getAttribute("data-family-id") });
        if (onPick) onPick(b);
      })
    );
    root.querySelectorAll("[data-mode-id]").forEach((b) =>
      b.addEventListener("click", () => {
        set({ mode: b.getAttribute("data-mode-id") });
        if (onPick) onPick(b);
      })
    );
  }

  function renderList(host) {
    if (host) listHost = host;
    if (!listHost) return;
    listHost.setAttribute("aria-label", "Tema e modo do app");
    listHost.innerHTML = pickerHtml("list");
    bind(listHost);
  }

  function renderMenu(focusSame) {
    const menu = document.getElementById("theme-menu");
    if (!menu) return;
    const prevKey = focusSame && document.activeElement && (document.activeElement.dataset.familyId || document.activeElement.dataset.modeId);
    menu.innerHTML = pickerHtml("menu");
    bind(menu, () => {});
    if (prevKey) {
      const again = menu.querySelector(`[data-family-id="${prevKey}"], [data-mode-id="${prevKey}"]`);
      if (again) again.focus();
    }
    const trigger = document.getElementById("btn-theme");
    if (trigger) {
      const fam = FAMILIES[pref.family];
      const label = `${fam ? fam.label : ""} · ${MODES.find((m) => m.id === pref.mode).label}`;
      trigger.setAttribute("title", `Tema: ${label}`);
      trigger.setAttribute("aria-label", `Tema: ${label}. Alterar tema`);
    }
  }

  function renderAll() {
    renderMenu(menuOpen);
    if (listHost) renderList();
  }

  function openMenu() {
    const menu = document.getElementById("theme-menu");
    const trigger = document.getElementById("btn-theme");
    if (!menu || !trigger) return;
    renderMenu(false);
    menu.classList.remove("hidden");
    trigger.setAttribute("aria-expanded", "true");
    menuOpen = true;
    const active = menu.querySelector('.theme-item[aria-checked="true"]') || menu.querySelector(".theme-item");
    if (active) active.focus();
  }

  function closeMenu() {
    const menu = document.getElementById("theme-menu");
    const trigger = document.getElementById("btn-theme");
    if (menu) menu.classList.add("hidden");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    menuOpen = false;
  }

  function toggleMenu() {
    if (menuOpen) closeMenu();
    else openMenu();
  }

  function onDocumentClick(ev) {
    if (!menuOpen) return;
    const wrap = document.getElementById("theme-picker");
    if (wrap && !wrap.contains(ev.target)) closeMenu();
  }

  function onKeydown(ev) {
    if (!menuOpen) return;
    const menu = document.getElementById("theme-menu");
    if (!menu) return;
    const items = Array.from(menu.querySelectorAll(".theme-item, .theme-mode"));
    const idx = items.indexOf(document.activeElement);
    if (ev.key === "Escape") {
      ev.preventDefault();
      closeMenu();
      document.getElementById("btn-theme")?.focus();
    } else if (ev.key === "ArrowDown" || ev.key === "ArrowRight") {
      ev.preventDefault();
      items[(idx + 1) % items.length]?.focus();
    } else if (ev.key === "ArrowUp" || ev.key === "ArrowLeft") {
      ev.preventDefault();
      items[(idx - 1 + items.length) % items.length]?.focus();
    }
  }

  function init() {
    renderMenu(false);
    document.addEventListener("click", onDocumentClick);
    document.addEventListener("keydown", onKeydown);
    if (typeof window.matchMedia === "function") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => {
        if (pref.mode === "auto") set({}, { persist: false });
      };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
  }

  // Aplicação imediata (antes do primeiro paint).
  pref = readStored();
  apply();

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  function list() {
    return DATA.families.map((f) => ({ id: f.id, label: f.label, hint: f.hint }));
  }

  return {
    set,
    current,
    list,
    renderList,
    toggleMenu,
    closeMenu,
    get preference() {
      return { ...pref };
    },
  };
})();
