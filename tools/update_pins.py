#!/usr/bin/env python3
"""
Atualiza pins SHA-256 de artefatos oficiais.

Uso:
  python tools/update_pins.py            # baixa e mostra digests vs PINNED_SHA256
  python tools/update_pins.py --check    # exit 1 se divergir

Compara também o digest publicado na API do GitHub Releases quando disponível.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.cache import PIN_META, PINNED_SHA256, URLS, USER_AGENT  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def github_asset_digest(repo: str, tag: str, asset: str) -> str | None:
    api = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(api, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    for a in data.get("assets", []):
        if a.get("name") == asset:
            dig = a.get("digest") or ""
            if dig.startswith("sha256:"):
                return dig.split(":", 1)[1].lower()
            return dig.lower() or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Falhar se pins divergirem")
    args = parser.parse_args()

    ok = True
    for key, url in URLS.items():
        print(f"\n=== {key} ===")
        print(f"URL: {url}")
        data = download(url)
        digest = sha256_bytes(data)
        pinned = (PINNED_SHA256.get(key) or "").lower()
        print(f"SHA-256 baixado: {digest}")
        print(f"Pin atual:       {pinned or '(nenhum)'}")
        match = pinned == digest
        print(f"Match pin:       {match}")
        if not match:
            ok = False

        meta = PIN_META.get(key)
        if meta:
            try:
                gh = github_asset_digest(meta["repo"], meta["tag"], meta["asset"])
                print(f"GitHub digest:   {gh or '(indisponível)'}")
                if gh and gh != digest:
                    print("AVISO: digest da API GitHub difere do arquivo baixado!")
                    ok = False
                elif gh and gh == digest:
                    print("GitHub digest:  OK")
            except Exception as e:
                print(f"GitHub API:      falhou ({e})")

        # Escreve cópia local opcional
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{key}") as tf:
            tf.write(data)
            print(f"Salvo temp:      {tf.name}")

    if args.check and not ok:
        print("\nFalha: pins desatualizados ou divergentes.", file=sys.stderr)
        return 1
    print("\nConcluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
