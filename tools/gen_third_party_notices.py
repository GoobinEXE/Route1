#!/usr/bin/env python3
"""Gera docs/licenses/THIRD_PARTY_NOTICES.txt com as licenças do que vai dentro do app.

Roda nos scripts de build de cada sistema, depois de instalar o requirements.lock.txt:
as dependências mudam por plataforma (PyObjC no macOS, pythonnet no Windows,
Qt no Linux), então o aviso tem de refletir o ambiente que empacota.

Inclui o runtime do Python (licença PSF) e, para cada pacote do lock que está
instalado, nome, versão, licença declarada e o texto dos arquivos de licença
do dist-info. As licenças das fontes, ícones e código portado ficam nos outros
arquivos de docs/licenses/.
"""

from __future__ import annotations

import importlib.metadata as md
import os
import re
import sys
import sysconfig

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, "requirements.lock.txt")
OUT = os.path.join(ROOT, "docs", "licenses", "THIRD_PARTY_NOTICES.txt")
_LICENSE_NAME = re.compile(r"(^|/)(licen[cs]e|copying|notice|authors)([.\-_].*)?$", re.I)


def lock_names() -> list[str]:
    names = []
    with open(LOCK, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^([A-Za-z0-9_.\-]+)==", line.strip())
            if m:
                names.append(m.group(1))
    return sorted(set(names), key=str.lower)


def license_of(meta) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    lic = (meta.get("License") or "").strip()
    if lic and "\n" not in lic and len(lic) < 80:
        return lic
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return ", ".join(classifiers) or (lic.splitlines()[0][:80] if lic else "ver texto abaixo")


def license_texts(dist) -> list[tuple[str, str]]:
    out = []
    for f in dist.files or []:
        name = str(f)
        if ".dist-info/" not in name or not _LICENSE_NAME.search(name.split(".dist-info/", 1)[1]):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if text.strip():
            out.append((name.split(".dist-info/", 1)[1], text.strip()))
    return out


FALLBACKS = os.path.join(ROOT, "tools", "license_texts")


def fallback_text(name: str) -> list[tuple[str, str]]:
    """Texto oficial guardado no repo para pacotes que não trazem a licença no wheel.

    pyobjc-*: o mesmo texto MIT de pyobjc-framework-Cocoa. proxy_tools: o texto
    BSD do repositório de origem (o PyPI declara MIT; fica o mais restritivo).
    """
    low = name.lower().replace("_", "-")
    key = "pyobjc" if low.startswith("pyobjc") else ("proxy_tools" if low == "proxy-tools" else None)
    if not key:
        return []
    path = os.path.join(FALLBACKS, f"{key}.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return [(f"{key}.txt (texto do projeto de origem)", f.read().strip())]
    except OSError:
        return []


def python_license() -> str:
    for base in (sysconfig.get_paths().get("stdlib", ""), os.path.dirname(sysconfig.get_paths().get("stdlib", ""))):
        p = os.path.join(base, "LICENSE.txt")
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read().strip()
    return "Python Software Foundation License Version 2 (https://docs.python.org/3/license.html)."


def main() -> int:
    sep = "=" * 78
    parts = [
        "Route Pico — avisos de terceiros",
        "",
        "O Route Pico é distribuído sob a GNU General Public License v3.0 (arquivo LICENSE).",
        "O código-fonte completo está em https://github.com/GoobinEXE/Route1.",
        "O app empacotado inclui os componentes abaixo, cada um sob a sua própria licença.",
        "Bibliotecas sob LGPL são usadas sem modificação; o código-fonte delas está nos",
        "projetos de origem (links no PyPI) e o do Route Pico no repositório acima.",
        f"Gerado para: {sys.platform}, Python {sys.version.split()[0]}.",
        "",
        "Fontes, ícones e código portado: ver Geist-OFL.txt, IBM-Plex-OFL.txt,",
        "DSPico-logo-CC-BY-SA-4.0.txt, PicoDex-LICENSE.txt e README.md nesta pasta.",
        "",
        sep,
        f"Python {sys.version.split()[0]} (runtime embutido) — PSF-2.0",
        sep,
        python_license(),
        "",
    ]
    missing = []
    for name in lock_names():
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            missing.append(name)
            continue
        meta = dist.metadata
        parts += [sep, f"{meta['Name']} {meta['Version']} — {license_of(meta)}", f"{meta.get('Home-page') or ''}".strip(), sep]
        texts = license_texts(dist) or fallback_text(meta["Name"])
        if texts:
            for fname, text in texts:
                parts += [f"--- {fname} ---", text, ""]
        else:
            parts += ["(o pacote não traz o texto da licença; ver o projeto de origem)", ""]
    if missing:
        parts += [sep, "Pacotes do lock que não se aplicam a este sistema (não empacotados):", ", ".join(missing), ""]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts).rstrip() + "\n")
    print(f"{OUT}: {len(lock_names()) - len(missing)} pacotes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
