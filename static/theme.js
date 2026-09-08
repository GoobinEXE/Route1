/**
 * Temas — Route 1 Kit
 *
 * Carregado no <head> (síncrono) para aplicar `data-theme` / `data-scheme`
 * em <html> antes do primeiro paint e evitar flash. As cores em si vivem em
 * themes.css; este ficheiro só escolhe o tema, persiste a preferência e
 * desenha o menu no header.
 */
const Theme = (() => {
  const STORAGE_KEY = "route_1_kit_theme";
  const DEFAULT_THEME = "dark";

  // swatch: [fundo, painel, accent] — usado só para a pré-visualização no menu.
  const THEMES = {
    dark: {
      label: "Escuro",
      group: "Studio",
      scheme: "dark",
      swatch: ["#0F1116", "#171A21", "#6D8BFF"],
    },
    light: {
      label: "Claro",
      group: "Studio",
      scheme: "light",
      swatch: ["#F3F4F7", "#FFFFFF", "#2F5BEA"],
    },
    "catppuccin-latte": {
      label: "Latte",
      group: "Catppuccin",
      scheme: "light",
      swatch: ["#E6E9EF", "#EFF1F5", "#1E66F5"],
    },
    "catppuccin-frappe": {
      label: "Frappé",
      group: "Catppuccin",
      scheme: "dark",
      swatch: ["#292C3C", "#303446", "#8CAAEE"],
    },
    "catppuccin-macchiato": {
      label: "Macchiato",
      group: "Catppuccin",
      scheme: "dark",
      swatch: ["#1E2030", "#24273A", "#8AADF4"],
    },
    "catppuccin-mocha": {
      label: "Mocha",
      group: "Catppuccin",
      scheme: "dark",
      swatch: ["#181825", "#1E1E2E", "#89B4FA"],
    },
    dracula: {
      label: "Dracula",
      group: "Dracula",
      scheme: "dark",
      swatch: ["#21222C", "#282A36", "#BD93F9"],
    },
    gameboy: {
      label: "Game Boy · DS Lite",
      group: "Retro",
      scheme: "light",
      swatch: ["#E3E7EC", "#9BBC0F", "#306230"],
    },
  };

  // "system" segue prefers-color-scheme e alterna entre Studio Escuro/Claro.
  const SYSTEM = "system";
  const GROUP_ORDER = ["Studio", "Catppuccin", "Dracula", "Retro"];

  let preference = DEFAULT_THEME; // o que o utilizador escolheu (pode ser "system")
  let menuOpen = false;

  function readStored() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v === SYSTEM || THEMES[v]) return v;
    } catch (e) {
      /* storage indisponível */
    }
    return DEFAULT_THEME;
  }

  function systemPrefersLight() {
    return (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: light)").matches
    );
  }

  function resolve(pref) {
    if (pref === SYSTEM) return systemPrefersLight() ? "light" : "dark";
    return THEMES[pref] ? pref : DEFAULT_THEME;
  }

  function applyToDocument(id) {
    const root = document.documentElement;
    const def = THEMES[id];
    root.setAttribute("data-theme", id);
    root.setAttribute("data-scheme", def.scheme);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", def.swatch[1]);
  }

  function set(pref, { persist = true } = {}) {
    preference = pref === SYSTEM || THEMES[pref] ? pref : DEFAULT_THEME;
    applyToDocument(resolve(preference));
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, preference);
      } catch (e) {
        /* ignorar */
      }
    }
    renderMenu();
  }

  function current() {
    return resolve(preference);
  }

  /* ---------- menu ---------- */

  function swatchHtml(colors) {
    return `<span class="theme-swatch" aria-hidden="true">${colors
      .map((c) => `<span style="background:${c}"></span>`)
      .join("")}</span>`;
  }

  const CHECK_SVG =
    '<svg class="check" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 8.5l3 3 7-7"/></svg>';

  function itemHtml(id, label, colors) {
    const checked = preference === id;
    return `
      <button type="button" class="theme-item" role="menuitemradio" aria-checked="${checked}"
              data-theme-id="${id}">
        ${swatchHtml(colors)}
        <span>${label}</span>
        ${CHECK_SVG}
      </button>`;
  }

  function renderMenu() {
    const menu = document.getElementById("theme-menu");
    if (!menu) return;

    const systemColors = systemPrefersLight() ? THEMES.light.swatch : THEMES.dark.swatch;
    let html = `<div class="theme-group">Aparência</div>${itemHtml(
      SYSTEM,
      "Automático (sistema)",
      systemColors
    )}`;

    GROUP_ORDER.forEach((group) => {
      const ids = Object.keys(THEMES).filter((k) => THEMES[k].group === group);
      if (!ids.length) return;
      html += `<div class="theme-group">${group}</div>`;
      ids.forEach((id) => {
        html += itemHtml(id, THEMES[id].label, THEMES[id].swatch);
      });
    });

    menu.innerHTML = html;
    menu.querySelectorAll("[data-theme-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        set(btn.getAttribute("data-theme-id"));
        closeMenu();
      });
    });

    const trigger = document.getElementById("btn-theme");
    if (trigger) {
      const label = preference === SYSTEM ? "Automático" : THEMES[current()].label;
      trigger.setAttribute("title", `Tema: ${label}`);
      trigger.setAttribute("aria-label", `Tema: ${label}. Alterar tema`);
    }
  }

  function openMenu() {
    const menu = document.getElementById("theme-menu");
    const trigger = document.getElementById("btn-theme");
    if (!menu || !trigger) return;
    renderMenu();
    menu.classList.remove("hidden");
    trigger.setAttribute("aria-expanded", "true");
    menuOpen = true;
    const active = menu.querySelector('[aria-checked="true"]') || menu.querySelector(".theme-item");
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
    const items = Array.from(menu.querySelectorAll(".theme-item"));
    const idx = items.indexOf(document.activeElement);

    if (ev.key === "Escape") {
      ev.preventDefault();
      closeMenu();
      document.getElementById("btn-theme")?.focus();
    } else if (ev.key === "ArrowDown") {
      ev.preventDefault();
      items[(idx + 1) % items.length]?.focus();
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      items[(idx - 1 + items.length) % items.length]?.focus();
    }
  }

  function init() {
    renderMenu();
    document.addEventListener("click", onDocumentClick);
    document.addEventListener("keydown", onKeydown);

    if (typeof window.matchMedia === "function") {
      const mq = window.matchMedia("(prefers-color-scheme: light)");
      const onChange = () => {
        if (preference === SYSTEM) set(SYSTEM, { persist: false });
      };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
  }

  // Aplicação imediata (antes do primeiro paint).
  preference = readStored();
  applyToDocument(resolve(preference));

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return { THEMES, set, current, toggleMenu, closeMenu, get preference() { return preference; } };
})();
