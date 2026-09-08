#!/usr/bin/env python3
"""
Gera os ícones rasterizados a partir de static/assets/logo.svg e logo-small.svg.

Saída (static/assets/):
  app-icon.png            1024×1024 (master)
  app-icon-512.png / app-icon-256.png / app-icon-128.png
  favicon.png             64×64 (variante compacta)
  favicon-32.png / favicon-16.png
  app-icon.ico            Windows (16/32/48/64/128/256 embutidos como PNG)
  app-icon.icns           macOS (via iconutil — só no macOS)

Requisitos: Google Chrome/Chromium para rasterizar (headless). No macOS usa
`sips` para redimensionar; noutros sistemas renderiza cada tamanho no Chrome.

Uso:
  python tools/build_icons.py
  python tools/build_icons.py --chrome /caminho/para/chrome
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "static", "assets")

LARGE_SVG = os.path.join(ASSETS, "logo.svg")
SMALL_SVG = os.path.join(ASSETS, "logo-small.svg")

# tamanho -> (svg de origem, nome do ficheiro)
OUTPUTS = {
    1024: (LARGE_SVG, "app-icon.png"),
    512: (LARGE_SVG, "app-icon-512.png"),
    256: (LARGE_SVG, "app-icon-256.png"),
    128: (LARGE_SVG, "app-icon-128.png"),
    64: (SMALL_SVG, "favicon.png"),
    32: (SMALL_SVG, "favicon-32.png"),
    16: (SMALL_SVG, "favicon-16.png"),
}

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    for cand in CHROME_CANDIDATES:
        if os.path.isabs(cand) and os.path.isfile(cand):
            return cand
        found = shutil.which(cand)
        if found:
            return found
    sys.exit("Chrome/Chromium não encontrado. Use --chrome /caminho/para/chrome")


def render_svg(chrome: str, svg_path: str, size: int, out_png: str, workdir: str) -> None:
    """Rasteriza o SVG em `size`×`size` com fundo transparente."""
    html = os.path.join(workdir, f"render-{size}.html")
    with open(html, "w", encoding="utf-8") as fh:
        fh.write(
            "<!doctype html><html><head><style>"
            "html,body{margin:0;padding:0;background:transparent;overflow:hidden}"
            f"img{{display:block;width:{size}px;height:{size}px}}"
            "</style></head><body>"
            f'<img src="file://{svg_path}"></body></html>'
        )
    profile = os.path.join(workdir, "profile")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile}",
        "--hide-scrollbars",
        "--default-background-color=00000000",
        f"--window-size={size},{size}",
        f"--screenshot={out_png}",
        f"file://{html}",
    ]
    # Algumas builds do Chrome não terminam sozinhas após o screenshot;
    # esperamos pelo ficheiro e encerramos o processo.
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 40
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if os.path.isfile(out_png) and os.path.getsize(out_png) > 0:
                time.sleep(0.5)
                break
            time.sleep(0.2)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if not os.path.isfile(out_png):
        sys.exit(f"Falha ao rasterizar {svg_path} em {size}px")


def resize_with_sips(src: str, size: int, dst: str) -> bool:
    if not shutil.which("sips"):
        return False
    res = subprocess.run(
        ["sips", "-Z", str(size), src, "--out", dst],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return res.returncode == 0 and os.path.isfile(dst)


def build_ico(entries: list[tuple[int, str]], out_path: str) -> None:
    """ICO com imagens PNG embutidas (suportado desde o Windows Vista)."""
    images = []
    for size, path in entries:
        with open(path, "rb") as fh:
            images.append((size, fh.read()))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    payload = b""
    for size, data in images:
        dim = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        payload += data
        offset += len(data)
    with open(out_path, "wb") as fh:
        fh.write(header + directory + payload)


def build_icns(master_large: str, master_small: str, out_path: str, workdir: str) -> bool:
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        return False
    iconset = os.path.join(workdir, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    plan = {
        "icon_16x16.png": (master_small, 16),
        "icon_16x16@2x.png": (master_small, 32),
        "icon_32x32.png": (master_small, 32),
        "icon_32x32@2x.png": (master_large, 64),
        "icon_128x128.png": (master_large, 128),
        "icon_128x128@2x.png": (master_large, 256),
        "icon_256x256.png": (master_large, 256),
        "icon_256x256@2x.png": (master_large, 512),
        "icon_512x512.png": (master_large, 512),
        "icon_512x512@2x.png": (master_large, 1024),
    }
    for name, (src, size) in plan.items():
        if not resize_with_sips(src, size, os.path.join(iconset, name)):
            return False
    res = subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out_path])
    return res.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chrome", help="caminho para o executável do Chrome/Chromium")
    args = parser.parse_args()

    chrome = find_chrome(args.chrome)
    os.makedirs(ASSETS, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dsi-icons-") as tmp:
        masters = {}
        for svg, size in ((LARGE_SVG, 1024), (SMALL_SVG, 256)):
            out = os.path.join(tmp, f"master-{size}.png")
            print(f"→ rasterizando {os.path.basename(svg)} @ {size}px")
            render_svg(chrome, svg, size, out, tmp)
            masters[svg] = out

        produced: list[tuple[int, str]] = []
        for size, (svg, name) in sorted(OUTPUTS.items(), reverse=True):
            dst = os.path.join(ASSETS, name)
            master = masters[svg]
            if not resize_with_sips(master, size, dst):
                render_svg(chrome, svg, size, dst, tmp)
            produced.append((size, dst))
            print(f"  {name} ({size}px)")

        # ICO: tamanhos clássicos do Windows
        ico_sizes = {16: SMALL_SVG, 32: SMALL_SVG, 48: SMALL_SVG, 64: LARGE_SVG, 128: LARGE_SVG, 256: LARGE_SVG}
        ico_entries = []
        for size, svg in ico_sizes.items():
            tmp_png = os.path.join(tmp, f"ico-{size}.png")
            if not resize_with_sips(masters[svg], size, tmp_png):
                render_svg(chrome, svg, size, tmp_png, tmp)
            ico_entries.append((size, tmp_png))
        ico_path = os.path.join(ASSETS, "app-icon.ico")
        build_ico(ico_entries, ico_path)
        print(f"  app-icon.ico ({', '.join(str(s) for s in ico_sizes)})")

        icns_path = os.path.join(ASSETS, "app-icon.icns")
        if build_icns(masters[LARGE_SVG], masters[SMALL_SVG], icns_path, tmp):
            print("  app-icon.icns")
        else:
            print("  (icns ignorado — requer macOS com iconutil)")

    print("Concluído.")


if __name__ == "__main__":
    main()
