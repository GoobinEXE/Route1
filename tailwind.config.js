/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./static/index.html", "./static/app.js"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Sora", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        ink: {
          DEFAULT: "#14161A",
          soft: "#3A4150",
          mute: "#6B7380",
        },
        paper: {
          DEFAULT: "#F0F2F5",
          raised: "#FFFFFF",
          line: "#D9DEE6",
        },
        brand: {
          DEFAULT: "#1E4DD8",
          deep: "#1636A8",
          soft: "#E8EEFF",
          mist: "#F3F6FF",
        },
        ok: "#0F7B5C",
        warn: "#A85B12",
        danger: "#C23B3B",
      },
      boxShadow: {
        panel:
          "0 1px 2px rgba(20, 22, 26, 0.04), 0 8px 24px rgba(20, 22, 26, 0.06)",
      },
    },
  },
  plugins: [],
};
