/** @type {import('tailwindcss').Config} */

// Todas as cores vêm dos tokens definidos em static/themes.css (triplas RGB),
// para que cada tema (dark, light, Catppuccin, Dracula) redefina a paleta sem
// recompilar o Tailwind. `<alpha-value>` mantém utilitários como `bg-accent/10`.
const token = (name) => `rgb(var(--c-${name}) / <alpha-value>)`;

module.exports = {
  content: [
    "./static/index.html",
    "./static/app.js",
    "./static/wizard.js",
    "./static/theme.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Sora", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        bg: token("bg"),
        surface: {
          DEFAULT: token("surface"),
          2: token("surface-2"),
        },
        line: {
          DEFAULT: token("line"),
          strong: token("line-strong"),
        },
        fg: {
          DEFAULT: token("fg"),
          soft: token("fg-soft"),
          mute: token("fg-mute"),
        },
        accent: {
          DEFAULT: token("accent"),
          strong: token("accent-strong"),
          fg: token("accent-fg"),
          on: token("on-accent"),
        },
        ok: token("ok"),
        warn: token("warn"),
        danger: token("danger"),
      },
      boxShadow: {
        panel: "var(--shadow-panel)",
        hover: "var(--shadow-hover)",
        menu: "var(--shadow-menu)",
      },
    },
  },
  plugins: [],
};
