#!/usr/bin/env python3
"""Gera static/themes.css e static/theme-data.js a partir das paletas abaixo.

Sete temas (inspirados em menus de consoles, nomes genéricos) × três modos:
  original  paleta própria do tema
  light     Catppuccin Latte com o acento do tema
  dark      Catppuccin Mocha com o acento do tema

Cada combinação é verificada contra WCAG AA: texto principal, secundário e
discreto ≥ 4.5:1 sobre painel e fundo; texto de acento ≥ 4.5:1; texto sobre o
botão de acento ≥ 4.5:1; estados (ok/aviso/erro) ≥ 4.5:1 sobre o painel. Cores
de texto derivadas (accent-fg, on-accent, estados) são escurecidas/clareadas
até passarem; uma paleta base que mesmo assim falhe aborta a geração.

    python tools/build_themes.py          # escreve os arquivos
    python tools/build_themes.py --check  # falha se estiverem desatualizados
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_OUT = os.path.join(ROOT, "static", "themes.css")
JS_OUT = os.path.join(ROOT, "static", "theme-data.js")

LATTE = {
    "base": "#eff1f5", "mantle": "#e6e9ef", "crust": "#dce0e8", "surface0": "#ccd0da", "surface1": "#bcc0cc",
    "surface2": "#acb0be", "subtext0": "#6c6f85", "subtext1": "#5c5f77", "text": "#4c4f69",
    "red": "#d20f39", "peach": "#fe640b", "yellow": "#df8e1d", "green": "#40a02b", "teal": "#179299",
    "sky": "#04a5e5", "sapphire": "#209fb5", "blue": "#1e66f5", "mauve": "#8839ef", "lavender": "#7287fd",
}
MOCHA = {
    "base": "#1e1e2e", "mantle": "#181825", "crust": "#11111b", "surface0": "#313244", "surface1": "#45475a",
    "surface2": "#585b70", "subtext0": "#a6adc8", "subtext1": "#bac2de", "text": "#cdd6f4",
    "red": "#f38ba8", "peach": "#fab387", "yellow": "#f9e2af", "green": "#a6e3a1", "teal": "#94e2d5",
    "sky": "#89dceb", "sapphire": "#74c7ec", "blue": "#89b4fa", "mauve": "#cba6f7", "lavender": "#b4befe",
}

# id, nome, descrição curta, raio (sm/md/lg), paleta original, acentos Catppuccin
# (acento das ações, cor da seleção-assinatura) para os modos claro/noturno.
FAMILIES = [
    {
        "id": "dupla", "label": "Dupla Tela", "hint": "Papel quadriculado, cantos azuis",
        "radius": (6, 10, 14),
        "original": {
            "scheme": "light", "bg": "#f3f4f5", "surface": "#ffffff", "surface2": "#f2f3f4", "line": "#d6d9dc",
            "line_strong": "#a9afb6", "fg": "#2a2d31", "soft": "#45494f", "mute": "#5d6269",
            "accent": "#2b7fe0", "select": "#2e8cf0", "ok": "#1e8e3e", "warn": "#b4640a", "danger": "#cf2f3d",
            "chrome": "#ffffff", "chrome_fg": "#5d6269", "hero": "#ffffff", "hero_fg": "#2a2d31",
        },
        "catppuccin": ("blue", "blue"),
    },
    {
        "id": "camera", "label": "Câmera Dupla", "hint": "Tela menta, balão com bico",
        "radius": (8, 12, 16),
        "original": {
            "scheme": "light", "bg": "#e7e9eb", "surface": "#ffffff", "surface2": "#f1f3f4", "line": "#d0d5d9",
            "line_strong": "#a7afb7", "fg": "#26292d", "soft": "#41464c", "mute": "#5b6168",
            "accent": "#2a86c9", "select": "#3a8fd8", "ok": "#2a8a3f", "warn": "#b0620c", "danger": "#c8323a",
            "chrome": "#55595e", "chrome_fg": "#ffffff", "hero": "#9fd3c7", "hero_fg": "#173f37",
        },
        "catppuccin": ("sapphire", "sapphire"),
    },
    {
        "id": "canais", "label": "Canais", "hint": "Canais brancos, barra curva",
        "radius": (14, 18, 24),
        "original": {
            "scheme": "light", "bg": "#eceef0", "surface": "#ffffff", "surface2": "#f4f5f7", "line": "#d3d7dc",
            "line_strong": "#aab1b9", "fg": "#383c41", "soft": "#4b5057", "mute": "#646a71",
            "accent": "#1a9fd6", "select": "#34beed", "ok": "#2a8b45", "warn": "#b0640d", "danger": "#cc3440",
            "chrome": "#e2e4e7", "chrome_fg": "#55595f", "hero": "#ffffff", "hero_fg": "#383c41",
        },
        "catppuccin": ("sapphire", "sky"),
    },
    {
        "id": "tablet", "label": "Tablet de Sala", "hint": "Vidro branco, bloco ciano",
        "radius": (14, 18, 22),
        "original": {
            "scheme": "light", "bg": "#e8e9eb", "surface": "#fafbfb", "surface2": "#eff1f3", "line": "#d6dadd",
            "line_strong": "#aeb5bc", "fg": "#2b2f33", "soft": "#43484e", "mute": "#5d636a",
            "accent": "#169fd0", "select": "#2bbde6", "ok": "#2b8a3e", "warn": "#b5650b", "danger": "#cf3443",
            "chrome": "#f6f7f8", "chrome_fg": "#4a4f55", "hero": "#ffffff", "hero_fg": "#2b2f33",
        },
        "catppuccin": ("sky", "sky"),
    },
    {
        "id": "cubo", "label": "Cubo", "hint": "Painéis violeta, botão dourado",
        "radius": (4, 6, 8),
        "original": {
            "scheme": "dark", "bg": "#07070c", "surface": "#1d1a63", "surface2": "#28217c", "line": "#4a46b4",
            "line_strong": "#7a76de", "fg": "#eef0ff", "soft": "#cfd2f6", "mute": "#a9ade6",
            "accent": "#d9b52e", "select": "#e8c43a", "ok": "#5fd08d", "warn": "#f3a24f", "danger": "#ff7184",
            "chrome": "#0c0c16", "chrome_fg": "#c9cdf2", "hero": "#2c1f86", "hero_fg": "#eef0ff",
        },
        "catppuccin": ("yellow", "yellow"),
    },
    {
        "id": "cubos3d", "label": "Estéreo 3D", "hint": "Cubos lavanda, cantos menta",
        "radius": (12, 16, 22),
        "original": {
            "scheme": "light", "bg": "#e8e7ef", "surface": "#ffffff", "surface2": "#e9e5de", "line": "#d4d2db",
            "line_strong": "#aba9b4", "fg": "#2d2e33", "soft": "#46474d", "mute": "#5f6067",
            "accent": "#e2681a", "select": "#38d39b", "ok": "#24894a", "warn": "#b0610a", "danger": "#cb3038",
            "chrome": "#f3f2f7", "chrome_fg": "#55565c", "hero": "#dedcea", "hero_fg": "#2d2e33",
        },
        "catppuccin": ("peach", "green"),
    },
    {
        "id": "hibrido", "label": "Híbrido", "hint": "Doca redonda, anel ciano",
        "radius": (6, 10, 14),
        "original": {
            "scheme": "light", "bg": "#ebebeb", "surface": "#ffffff", "surface2": "#f4f4f4", "line": "#d6d6d6",
            "line_strong": "#a8a8a8", "fg": "#2d2d2d", "soft": "#454545", "mute": "#5f5f5f",
            "accent": "#3a5fd8", "select": "#19c6e4", "ok": "#24894a", "warn": "#ae600b", "danger": "#c4202f",
            "chrome": "#ebebeb", "chrome_fg": "#2d2d2d", "hero": "#ffffff", "hero_fg": "#2d2d2d",
        },
        "catppuccin": ("blue", "sky"),
    },
]

# Cores dos blocos (laranja, verde, azul, turquesa, vermelho, amarelo, roxo):
# ícones coloridos por tarefa, como nos menus. Ajustadas a 3:1 contra o painel.
TILE_LIGHT = ["#e46c12", "#2f9e3a", "#2a6fdb", "#12928d", "#d93a3a", "#c18600", "#8a4fd6"]
TILE_DARK = ["#ff9a4a", "#6fd67c", "#7fb0ff", "#5fd6cf", "#ff7a7a", "#f2c84b", "#c39bff"]
TILE_CP = ["peach", "green", "blue", "teal", "red", "yellow", "mauve"]

DEFAULT_FAMILY = "dupla"
DEFAULT_MODE = "original"


# --------------------------------------------------------------------------- cor


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_hex(c) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def _lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def lum(h: str) -> float:
    r, g, b = hex_rgb(h)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = hex_rgb(a), hex_rgb(b)
    return rgb_hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def ensure(color: str, grounds: list[str], target: float, toward: str) -> str:
    """Aproxima ``color`` de ``toward`` até ter ``target`` contra todos os fundos."""
    for i in range(0, 101):
        c = mix(color, toward, i / 100)
        if all(contrast(c, g) >= target for g in grounds):
            return c
    raise SystemExit(f"impossível obter contraste {target} para {color}")


def on_color(fill: str, light: str, dark: str) -> tuple[str, str]:
    """(texto, preenchimento) com 4.5:1. Escolhe o texto mais legível; se nem assim
    chega, aprofunda o preenchimento no sentido oposto ao texto (só o necessário)."""
    best = light if contrast(light, fill) >= contrast(dark, fill) else dark
    if contrast(best, fill) >= 4.5:
        return best, fill
    away = "#000000" if best == light else "#ffffff"
    for i in range(1, 101):
        f = mix(fill, away, i / 100)
        if contrast(best, f) >= 4.5:
            return best, f
    raise SystemExit(f"impossível obter texto legível sobre {fill}")


# --------------------------------------------------------------------------- tokens


def tokens(family: dict, mode: str) -> dict[str, str]:
    if mode == "original":
        p = dict(family["original"])
    else:
        cp = LATTE if mode == "light" else MOCHA
        acc, sel = family["catppuccin"]
        p = {
            "scheme": "light" if mode == "light" else "dark",
            "bg": cp["mantle"], "surface": cp["base"], "surface2": cp["crust"] if mode == "light" else cp["surface0"],
            "line": cp["surface0"] if mode == "light" else cp["surface1"],
            "line_strong": cp["surface1"] if mode == "light" else cp["surface2"],
            "fg": cp["text"], "soft": cp["subtext1"], "mute": cp["subtext0"],
            "accent": cp[acc], "select": cp[sel], "ok": cp["green"], "warn": cp["peach"], "danger": cp["red"],
            "chrome": cp["base"] if family["id"] not in ("camera", "cubo") else cp["crust"],
            "chrome_fg": cp["subtext1"] if family["id"] not in ("camera", "cubo") else cp["text"],
            "hero": mix(cp["base"], cp[sel], 0.22 if mode == "light" else 0.16)
            if family["id"] in ("camera", "cubo", "cubos3d") else cp["base"],
            "hero_fg": cp["text"],
        }
    dark = p["scheme"] == "dark"
    toward_text = "#ffffff" if dark else "#000000"
    grounds = [p["surface"], p["surface2"], p["bg"]]
    out = {
        "scheme": p["scheme"],
        "bg": p["bg"], "surface": p["surface"], "surface-2": p["surface2"],
        "line": p["line"], "line-strong": p["line_strong"],
        "fg": ensure(p["fg"], grounds, 7.0, toward_text),
        "fg-soft": ensure(p["soft"], grounds, 4.5, toward_text),
        "fg-mute": ensure(p["mute"], grounds, 4.5, toward_text),
    }
    on_acc, acc_fill = on_color(p["accent"], "#ffffff", mix(p["fg"], "#000000", 0.4) if not dark else p["bg"])
    on_sel, sel_fill = on_color(p["select"], "#ffffff", "#141414")
    out.update({
        "accent": acc_fill,
        "accent-strong": mix(acc_fill, toward_text, 0.14),
        "accent-fg": ensure(p["accent"], grounds, 4.5, toward_text),
        "on-accent": on_acc,
        # A seleção mantém a cor da marca (anéis, molduras); só o preenchimento
        # com texto usa a versão ajustada.
        "select": p["select"],
        "select-fill": sel_fill,
        "on-select": on_sel,
        "ok": ensure(p["ok"], grounds, 4.5, toward_text),
        "warn": ensure(p["warn"], grounds, 4.5, toward_text),
        "danger": ensure(p["danger"], grounds, 4.5, toward_text),
    })
    out["chrome"] = p["chrome"]
    out["chrome-fg"] = ensure(p["chrome_fg"], [p["chrome"]], 4.5, "#ffffff" if lum(p["chrome"]) < 0.4 else "#000000")
    out["hero"] = p["hero"]
    out["hero-fg"] = ensure(p["hero_fg"], [p["hero"]], 4.5, "#ffffff" if lum(p["hero"]) < 0.4 else "#000000")
    if mode == "original":
        tiles = TILE_DARK if dark else TILE_LIGHT
    else:
        cp = LATTE if mode == "light" else MOCHA
        tiles = [cp[k] for k in TILE_CP]
    for i, t in enumerate(tiles, 1):
        out[f"tile-{i}"] = ensure(t, [p["surface"], p["surface2"]], 3.0, toward_text)
    # Contornos de controlo (WCAG 1.4.11): a borda forte separa-se do painel a 3:1.
    out["line-strong"] = ensure(out["line-strong"], [p["surface"]], 3.0, toward_text) if contrast(out["line-strong"], p["surface"]) < 3.0 else out["line-strong"]
    return out


def css_triplet(h: str) -> str:
    return "%d %d %d" % hex_rgb(h)


def build() -> tuple[str, str, list[str]]:
    report = []
    css = [
        "/* GERADO por tools/build_themes.py — não editar à mão.",
        "   Sete temas × três modos (original, claro = Catppuccin Latte, noturno = Catppuccin Mocha).",
        "   Cores em triplas RGB para o Tailwind aplicar opacidade (bg-accent/10) e o CSS usar",
        "   rgb(var(--c-x) / 0.5). A assinatura visual de cada tema está em static/skins.css. */",
        "",
        ":root {",
        "  --ease: cubic-bezier(0.22, 1, 0.36, 1);",
        "  --dur: 180ms;",
        '  --font-sans: "Geist", system-ui, -apple-system, "Segoe UI", sans-serif;',
        '  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;',
        "}",
        "",
    ]
    data = {"defaultFamily": DEFAULT_FAMILY, "defaultMode": DEFAULT_MODE, "families": []}
    for fam in FAMILIES:
        sm, md, lg = fam["radius"]
        sel = f'html[data-family="{fam["id"]}"]'
        if fam["id"] == DEFAULT_FAMILY:
            sel = ":root, " + sel
        css += [f"{sel} {{", f"  --radius-sm: {sm}px;", f"  --radius: {md}px;", f"  --radius-lg: {lg}px;", "}", ""]
        entry = {"id": fam["id"], "label": fam["label"], "hint": fam["hint"], "modes": {}}
        for mode in ("original", "light", "dark"):
            t = tokens(fam, mode)
            sel = f'html[data-family="{fam["id"]}"][data-mode="{mode}"]'
            if fam["id"] == DEFAULT_FAMILY and mode == DEFAULT_MODE:
                sel = ":root, " + sel
            css.append(f"{sel} {{")
            css.append(f"  color-scheme: {t['scheme']};")
            for k, v in t.items():
                if k == "scheme":
                    continue
                css.append(f"  --c-{k}: {css_triplet(v)};")
            css.append("}")
            css.append("")
            entry["modes"][mode] = {
                "scheme": t["scheme"],
                "swatch": [t["bg"], t["surface"], t["accent"], t["select"]],
            }
            report.append(
                f"{fam['id']:<8} {mode:<8} fg {contrast(t['fg'], t['surface']):4.1f}  mute {contrast(t['fg-mute'], t['surface-2']):4.1f}"
                f"  accent-fg {contrast(t['accent-fg'], t['surface']):4.1f}  on-accent {contrast(t['on-accent'], t['accent']):4.1f}"
                f"  danger {contrast(t['danger'], t['surface']):4.1f}"
            )
        data["families"].append(entry)
    css += [
        "/* Sombras por esquema (data-scheme é escrito pelo theme.js a partir do modo). */",
        ":root, html[data-scheme=\"light\"] {",
        "  --shadow-panel: 0 1px 2px rgb(20 22 26 / 0.05), 0 6px 18px rgb(20 22 26 / 0.06);",
        "  --shadow-hover: 0 2px 4px rgb(20 22 26 / 0.06), 0 12px 28px rgb(20 22 26 / 0.10);",
        "  --shadow-menu: 0 2px 6px rgb(20 22 26 / 0.08), 0 18px 48px rgb(20 22 26 / 0.16);",
        "  --shadow-press: 0 1px 1px rgb(20 22 26 / 0.10);",
        "  --glow-alpha: 0.08;",
        "  --select-chevron: url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' fill='none'%3E%3Cpath d='M1 1.5 6 6.5 11 1.5' stroke='%236E7684' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\");",
        "}",
        "html[data-scheme=\"dark\"] {",
        "  --shadow-panel: 0 1px 0 rgb(255 255 255 / 0.04) inset, 0 2px 4px rgb(0 0 0 / 0.32), 0 10px 28px rgb(0 0 0 / 0.30);",
        "  --shadow-hover: 0 1px 0 rgb(255 255 255 / 0.05) inset, 0 3px 6px rgb(0 0 0 / 0.38), 0 16px 36px rgb(0 0 0 / 0.36);",
        "  --shadow-menu: 0 1px 0 rgb(255 255 255 / 0.05) inset, 0 14px 44px rgb(0 0 0 / 0.55);",
        "  --shadow-press: 0 1px 1px rgb(0 0 0 / 0.40);",
        "  --glow-alpha: 0.16;",
        "  --select-chevron: url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' fill='none'%3E%3Cpath d='M1 1.5 6 6.5 11 1.5' stroke='%23B4BCD0' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E\");",
        "}",
        "",
    ]
    js = (
        "/* GERADO por tools/build_themes.py — não editar à mão. */\n"
        "window.R1K_THEME_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n"
    )
    return "\n".join(css), js, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    css, js, report = build()
    if args.check:
        for path, text in ((CSS_OUT, css), (JS_OUT, js)):
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() != text:
                        print(f"{os.path.relpath(path, ROOT)} desatualizado", file=sys.stderr)
                        return 1
            except OSError:
                return 1
        return 0
    for path, text in ((CSS_OUT, css), (JS_OUT, js)):
        with open(path + ".partial", "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(path + ".partial", path)
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
