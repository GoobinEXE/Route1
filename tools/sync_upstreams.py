#!/usr/bin/env python3
"""Mantém o Route Pico alinhado com as cinco fontes oficiais (core/upstreams.py).

    python tools/sync_upstreams.py --check   # sai 1 se alguma fonte tem release mais nova
    python tools/sync_upstreams.py --apply   # atualiza core/data/upstreams.lock.json

--apply, para cada fonte:
  * pacotes (launcher/loader oficiais e Enhanced): última release, asset pela
    regra ``asset_re``, digest SHA-256 publicado pelo GitHub conferido contra o
    download; grava tag/asset/sha256 no lock;
  * PicoDex: última release, copia os ficheiros de ``files`` dessa tag para
    core/data/picodex/ e grava tag, commit e sha256 de cada um. Um
    loaderReleases.json com menos releases do que o atual é recusado (mesma
    regra de crescimento do gerador da PicoDex).
Depois regenera core/data/pico_manifest.json (hashes do launcher e do loader
Enhanced) via tools/gen_pico_manifest.py.

Usa GITHUB_TOKEN se definido (limite de 60 pedidos/hora sem token).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.upstreams import LOCK_PATH, PICODEX_DATA_DIR, UPSTREAMS  # noqa: E402


def _get(url: str, accept: str = "application/vnd.github+json") -> bytes:
    headers = {"User-Agent": "RoutePico-sync", "Accept": accept}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:  # nosec B310
        return r.read()


def _api(path: str):
    return json.loads(_get(f"https://api.github.com{path}"))


def _latest(repo: str) -> dict:
    rel = _api(f"/repos/{repo}/releases/latest")
    if not isinstance(rel, dict) or not rel.get("tag_name"):
        raise RuntimeError(f"{repo}: release mais recente sem tag")
    return rel


def _load_lock() -> dict:
    try:
        with open(LOCK_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _write_atomic(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".partial"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _sync_package(uid: str, meta: dict, rel: dict) -> dict:
    rx = re.compile(meta["asset_re"])
    assets = [a for a in rel.get("assets") or [] if rx.match(str(a.get("name") or ""))]
    if len(assets) != 1:
        raise RuntimeError(f"{uid}: esperava 1 asset para {meta['asset_re']}, encontrei {len(assets)}")
    asset = assets[0]
    digest = str(asset.get("digest") or "")
    if not digest.startswith("sha256:"):
        raise RuntimeError(f"{uid}: asset sem digest SHA-256 publicado pelo GitHub")
    expected = digest.split(":", 1)[1]
    data = _get(asset["browser_download_url"], accept="application/octet-stream")
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f"{uid}: download não confere com o digest publicado")
    return {"repo": meta["repo"], "tag": rel["tag_name"], "asset": asset["name"], "sha256": expected, "size": len(data)}


def _sync_picodex(meta: dict, rel: dict, current: dict) -> dict:
    tag = rel["tag_name"]
    ref = _api(f"/repos/{meta['repo']}/commits/{tag}")
    commit = ref["sha"]
    files = {}
    for src, name in meta["files"].items():
        obj = _api(f"/repos/{meta['repo']}/contents/{src}?ref={commit}")
        data = base64.b64decode(obj["content"])
        parsed = json.loads(data)
        if name == "loaderReleases.json":
            new_n = len(parsed.get("releases") or [])
            old_path = os.path.join(PICODEX_DATA_DIR, name)
            if os.path.isfile(old_path):
                with open(old_path, encoding="utf-8") as f:
                    old_n = len(json.load(f).get("releases") or [])
                if new_n < old_n:
                    raise RuntimeError(f"picodex: {name} encolheu ({old_n} → {new_n} releases); recusado")
        _write_atomic(os.path.join(PICODEX_DATA_DIR, name), data)
        files[name] = {"source": src, "sha256": hashlib.sha256(data).hexdigest()}
    return {"repo": meta["repo"], "tag": tag, "commit": commit, "files": files}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    lock = _load_lock()
    behind = []
    for uid, meta in UPSTREAMS.items():
        rel = _latest(meta["repo"])
        cur = lock.get(uid) or {}
        status = "em dia" if cur.get("tag") == rel["tag_name"] else f"{cur.get('tag', '—')} → {rel['tag_name']}"
        print(f"{meta['label']:<24} {meta['repo']:<34} {status}")
        if cur.get("tag") != rel["tag_name"] or cur.get("repo") != meta["repo"]:
            behind.append(uid)
        if args.apply:
            if "files" in meta:
                lock[uid] = _sync_picodex(meta, rel, cur)
            else:
                lock[uid] = _sync_package(uid, meta, rel)
    if args.check:
        if behind:
            print("Desatualizado: " + ", ".join(behind) + " — rode tools/sync_upstreams.py --apply", file=sys.stderr)
            return 1
        return 0
    _write_atomic(LOCK_PATH, (json.dumps(lock, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(f"lock gravado: {os.path.relpath(LOCK_PATH, ROOT)}")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_pico_manifest.py")], check=True, timeout=900)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
