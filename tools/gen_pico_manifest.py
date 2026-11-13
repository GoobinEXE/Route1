#!/usr/bin/env python3
"""Gera core/data/pico_manifest.json: SHA-256 do LAUNCHER.nds de cada release do
Pico Launcher (LNH-team) e do Pico Launcher Enhanced, e dos picoLoader7/9.bin do
Pico Loader Enhanced (rasalopa/pico-loader).

O Pico Loader oficial NÃO está aqui: o RouteDex usa o manifesto mantido pela
própria PicoDex (core/data/picodex/loaderReleases.json, via
tools/sync_upstreams.py). Este ficheiro cobre só o que a PicoDex não cobre.

Uso:
    python tools/gen_pico_manifest.py            # regenera o JSON
    python tools/gen_pico_manifest.py --check    # falha se o JSON estiver desatualizado

Requer acesso a api.github.com (usa GITHUB_TOKEN se definido). Cada asset é
verificado contra o digest SHA-256 que a API do GitHub publica.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "core", "data", "pico_manifest.json")

LAUNCHER_FILE = "LAUNCHER.nds"

SOURCES = {
    "launcher_official": {"repo": "LNH-team/pico-launcher", "asset_re": r"^Pico[._]Launcher\.zip$"},
    "launcher_enhanced": {
        "repo": "rasalopa/pico-launcher-enhanced",
        "asset_re": r"^Pico_Launcher_Enhanced\.zip$",
    },
    "loader_enhanced": {
        "repo": "rasalopa/pico-loader",
        "asset_re": r"^Pico_Loader_Enhanced_v[0-9.]+\.zip$",
    },
}


def _get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    headers = {"User-Agent": "RoutePico-manifest", "Accept": accept}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310 - URLs fixas do GitHub
        return resp.read()


def _releases(repo: str) -> list[dict]:
    out: list[dict] = []
    page = 1
    while True:
        batch = json.loads(_get(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"))
        if not batch:
            break
        out.extend(r for r in batch if not r.get("draft") and not r.get("prerelease"))
        page += 1
    out.sort(key=lambda r: r.get("published_at") or "")
    return out


def _download_verified(asset: dict) -> bytes:
    data = _get(asset["browser_download_url"], accept="application/octet-stream")
    digest = str(asset.get("digest") or "")
    if digest.startswith("sha256:"):
        actual = hashlib.sha256(data).hexdigest()
        if actual != digest.split(":", 1)[1]:
            raise RuntimeError(f"digest não confere: {asset['name']}")
    return data


def _hash_members(zdata: bytes, wanted: tuple[str, ...]) -> dict[str, str]:
    found: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(zdata)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            base = info.filename.replace("\\", "/").rsplit("/", 1)[-1]
            for name in wanted:
                if base.lower() == name.lower() and name not in found:
                    found[name] = hashlib.sha256(zf.read(info)).hexdigest()
    return found


def build() -> dict:
    manifest: dict = {
        "generated_by": "tools/gen_pico_manifest.py",
        "loader_enhanced": {"releases": [], "files": {}},
        "launcher": {"official": {}, "enhanced": {}},
    }

    def add(table: dict, file: str, digest: str, tag: str) -> None:
        tags = table.setdefault(file, {}).setdefault(digest, [])
        if tag not in tags:
            tags.append(tag)

    src = SOURCES["loader_enhanced"]
    for rel in _releases(src["repo"]):
        tag = rel["tag_name"]
        for asset in rel.get("assets", []):
            if not re.match(src["asset_re"], asset["name"]):
                continue
            hashes = _hash_members(_download_verified(asset), ("picoLoader7.bin", "picoLoader9.bin"))
            for file, digest in hashes.items():
                add(manifest["loader_enhanced"]["files"], file, digest, tag)
            manifest["loader_enhanced"]["releases"].append({"tag": tag, "published": rel.get("published_at", "")[:10]})
            print(f"loader enhanced {tag}: {len(hashes)} ficheiros", file=sys.stderr)

    for variant in ("official", "enhanced"):
        src = SOURCES[f"launcher_{variant}"]
        for rel in _releases(src["repo"]):
            tag = rel["tag_name"]
            for asset in rel.get("assets", []):
                if not re.match(src["asset_re"], asset["name"]):
                    continue
                hashes = _hash_members(_download_verified(asset), (LAUNCHER_FILE,))
                digest = hashes.get(LAUNCHER_FILE)
                if digest:
                    manifest["launcher"][variant][digest] = tag
                    print(f"launcher {variant} {tag}", file=sys.stderr)

    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="falha se o JSON local diferir do gerado")
    args = ap.parse_args()
    text = json.dumps(build(), indent=1, sort_keys=True) + "\n"
    if args.check:
        try:
            with open(OUT, encoding="utf-8") as f:
                current = f.read()
        except OSError:
            current = ""
        if current != text:
            print("pico_manifest.json desatualizado: rode tools/gen_pico_manifest.py", file=sys.stderr)
            return 1
        print("pico_manifest.json em dia.", file=sys.stderr)
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".partial"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, OUT)
    print(f"escrito {os.path.relpath(OUT, ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
