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
        "id": "dupla", "label": "Dupla Tela", "hint": "Papel quadriculado, moldura azul",
        "radius": (10, 14, 18),
        "original": {
            "scheme": "light", "bg": "#e2e6ea", "surface": "#ffffff", "surface2": "#f1f3f5", "line": "#cdd3da",
            "line_strong": "#aab3be", "fg": "#1d2126", "soft": "#3b424a", "mute": "#59616b",
            "accent": "#2f7de1", "select": "#2f7de1", "ok": "#1e8e3e", "warn": "#b4640a", "danger": "#cf2f3d",
        },
        "catppuccin": ("blue", "blue"),
    },
    {
        "id": "camera", "label": "Câmera Dupla", "hint": "Branco e cinza, etiqueta com bico",
        "radius": (12, 16, 22),
        "original": {
            "scheme": "light", "bg": "#e9ecef", "surface": "#ffffff", "surface2": "#f2f4f6", "line": "#d3d8dd",
            "line_strong": "#b0b8c1", "fg": "#252a2f", "soft": "#41474e", "mute": "#5d646c",
            "accent": "#1f8fb3", "select": "#3e9fd3", "ok": "#2a8a3f", "warn": "#b0620c", "danger": "#c8323a",
        },
        "catppuccin": ("teal", "sapphire"),
    },
    {
        "id": "canais", "label": "Canais", "hint": "Risca fina prateada, anel ciano",
        "radius": (14, 18, 26),
        "original": {
            "scheme": "light", "bg": "#eef0f2", "surface": "#ffffff", "surface2": "#f5f6f8", "line": "#d5d9de",
            "line_strong": "#b3bac2", "fg": "#33383e", "soft": "#4a5057", "mute": "#646b73",
            "accent": "#1fb0e6", "select": "#34beed", "ok": "#2a8b45", "warn": "#b0640d", "danger": "#cc3440",
        },
        "catppuccin": ("sapphire", "sky"),
    },
    {
        "id": "tablet", "label": "Tablet de Sala", "hint": "Vidro claro, cartão realçado",
        "radius": (12, 16, 22),
        "original": {
            "scheme": "light", "bg": "#e6e9ec", "surface": "#fbfcfd", "surface2": "#f0f2f4", "line": "#d4d9de",
            "line_strong": "#afb7c0", "fg": "#272b30", "soft": "#41474e", "mute": "#5c636b",
            "accent": "#14a9dc", "select": "#23b8e8", "ok": "#2b8a3e", "warn": "#b5650b", "danger": "#cf3443",
        },
        "catppuccin": ("sky", "sky"),
    },
    {
        "id": "cubo", "label": "Cubo", "hint": "Índigo profundo, moldura dourada",
        "radius": (6, 10, 14),
        "original": {
            "scheme": "dark", "bg": "#0f0c2e", "surface": "#1b1752", "surface2": "#251f68", "line": "#3a3292",
            "line_strong": "#544ab8", "fg": "#ece9ff", "soft": "#c9c3f2", "mute": "#a29bdc",
            "accent": "#9d8cff", "select": "#f2c230", "ok": "#5fd08d", "warn": "#f3a24f", "danger": "#ff7184",
        },
        "catppuccin": ("mauve", "yellow"),
    },
    {
        "id": "cubos3d", "label": "Estéreo 3D", "hint": "Blocos em relevo, cantos verdes",
        "radius": (12, 16, 22),
        "original": {
            "scheme": "light", "bg": "#e3e4e8", "surface": "#fafafb", "surface2": "#efeff2", "line": "#d0d2d8",
            "line_strong": "#adb0b8", "fg": "#2c2f34", "soft": "#45484e", "mute": "#5f636a",
            "accent": "#e2681a", "select": "#2fbf71", "ok": "#24894a", "warn": "#b0610a", "danger": "#cb3038",
        },
        "catppuccin": ("peach", "green"),
    },
    {
        "id": "hibrido", "label": "Híbrido", "hint": "Cinza limpo, anel duplo",
        "radius": (10, 14, 20),
        "original": {
            "scheme": "light", "bg": "#ebebeb", "surface": "#ffffff", "surface2": "#f4f4f4", "line": "#d9d9d9",
            "line_strong": "#b6b6b6", "fg": "#2d2d2d", "soft": "#454545", "mute": "#5f5f5f",
            "accent": "#d7283d", "select": "#16c3e0", "ok": "#24894a", "warn": "#ae600b", "danger": "#c4202f",
        },
        "catppuccin": ("red", "sky"),
    },
]

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
        '  --font-sans: "Nunito", ui-rounded, system-ui, -apple-system, "Segoe UI", sans-serif;',
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
