"""Cliente SteamGridDB (API v2) — fonte principal de capas e ícones.

Requer chave API do utilizador (prefs `steamgriddb_api_key` ou env
`STEAMGRIDDB_API_KEY`). Sem chave, as funções devolvem listas vazias / None
e o pipeline cai para GameTDB / Libretro.

Documentação: https://www.steamgriddb.com/api/v2
"""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from core.cache import USER_AGENT
from core.logging_util import emit_log
from core.prefs import get_pref

_API_BASE = "https://www.steamgriddb.com/api/v2"
_PREF_KEY = "steamgriddb_api_key"
_ENV_KEY = "STEAMGRIDDB_API_KEY"
_API_TIMEOUT = 20
_DOWNLOAD_TIMEOUT = 30
_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_PNG_MIN = 64
_MAX_SEARCH_GAMES = 8
_MAX_ASSETS = 12
_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{8,256}$")
_TRAILING_TAG = re.compile(r"\s*[\(\[][^\)\]]+[\)\]]\s*$")

# CDN de assets (não a API). s3 só com path SteamGridDB.
_CDN_HOSTS = frozenset(
    {
        "cdn2.steamgriddb.com",
        "cdn.steamgriddb.com",
    }
)

# Evitar spam de logs em lotes longos (mesmo status só 1× por sessão).
_logged_api_status: set[int] = set()
_log_status_lock = threading.Lock()

_cache_lock = threading.Lock()
_game_id_cache: dict[str, Optional[int]] = {}
_CACHE_MAX = 256


def _url_looks_png(url: str) -> bool:
    path = (urllib.parse.urlparse(url).path or "").lower()
    return path.endswith(".png")


def _url_looks_ico(url: str) -> bool:
    path = (urllib.parse.urlparse(url).path or "").lower()
    return path.endswith(".ico")


def _log_api_failure(status: Optional[int], *, reason: str) -> None:
    """Log redigido (sem chave) — no máximo 1× por código HTTP nesta sessão."""
    code = int(status) if status is not None else 0
    with _log_status_lock:
        if code in _logged_api_status:
            return
        _logged_api_status.add(code)
    if code in (401, 403):
        msg = (
            f"SteamGridDB: chave rejeitada (HTTP {code}) — "
            "verifique a chave em Definições."
        )
    elif code:
        msg = f"SteamGridDB: falha na API (HTTP {code})."
    else:
        msg = f"SteamGridDB: {reason}."
    emit_log(None, msg)


def normalize_api_key(raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    key = raw.strip()
    if not key or "\x00" in key:
        return None
    if not _KEY_RE.match(key):
        return None
    return key


def get_api_key() -> Optional[str]:
    """Chave efectiva: env > prefs. None se ausente/inválida."""
    env = normalize_api_key(os.environ.get(_ENV_KEY))
    if env:
        return env
    return normalize_api_key(get_pref(_PREF_KEY))


def has_api_key() -> bool:
    return get_api_key() is not None


def is_asset_url(url: str) -> bool:
    """True se URL HTTPS for CDN SteamGridDB (download de grelha/ícone)."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    try:
        parts = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if host in _CDN_HOSTS:
        return True
    if host == "s3.amazonaws.com":
        path = parts.path or ""
        return path.startswith("/cdn.steamgriddb.com/") or path.startswith(
            "/steamgriddb/"
        )
    return False


def search_term_from_rom(
    basename: str, *, title: Optional[str] = None, query: str = ""
) -> str:
    """Nome limpo para autocomplete SGDB (sem tags No-Intro quando possível)."""
    q = (query or "").strip()
    if q and not (len(q) == 4 and q.isalnum()):
        return q[:120]

    def _strip(name: str) -> str:
        cur = os.path.splitext(os.path.basename(name or ""))[0].strip()
        if not cur:
            return ""
        for _ in range(8):
            nxt = _TRAILING_TAG.sub("", cur).strip()
            if not nxt or nxt == cur:
                break
            cur = nxt
        return cur[:120]

    for raw in (title or "", basename or ""):
        cleaned = _strip(raw)
        if cleaned:
            return cleaned
    return ""


def clear_game_cache() -> None:
    with _cache_lock:
        _game_id_cache.clear()
    with _log_status_lock:
        _logged_api_status.clear()


def _api_get(path: str, *, params: Optional[dict[str, str]] = None) -> Any:
    key = get_api_key()
    if not key:
        return None
    if not path.startswith("/"):
        path = "/" + path
    url = _API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT) as resp:  # nosec B310
            raw = resp.read(_MAX_DOWNLOAD_BYTES + 1)
        if len(raw) > _MAX_DOWNLOAD_BYTES:
            return None
        data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            status = int(getattr(e, "code", 0) or 0)
        except (TypeError, ValueError):
            status = 0
        _log_api_failure(status or None, reason="erro HTTP")
        return None
    except (OSError, urllib.error.URLError, TimeoutError) as e:
        _log_api_failure(None, reason=f"rede/timeout ({type(e).__name__})")
        return None
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ):
        _log_api_failure(None, reason="resposta inválida")
        return None
    if not isinstance(data, dict) or not data.get("success"):
        return None
    return data.get("data")


def search_games(term: str, *, limit: int = _MAX_SEARCH_GAMES) -> list[dict[str, Any]]:
    """Autocomplete → [{id, name, verified}, …]."""
    q = (term or "").strip()[:120]
    if not q or not get_api_key():
        return []
    enc = urllib.parse.quote(q, safe="")
    data = _api_get(f"/search/autocomplete/{enc}")
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            gid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        out.append(
            {
                "id": gid,
                "name": name.strip()[:200],
                "verified": bool(item.get("verified")),
            }
        )
        if len(out) >= max(1, min(int(limit), 20)):
            break
    # Preferir jogos verificados.
    out.sort(key=lambda g: (0 if g.get("verified") else 1, g.get("name") or ""))
    return out


def resolve_game_id(term: str) -> Optional[int]:
    """1.º match do autocomplete (com cache de sessão)."""
    q = (term or "").strip().lower()[:120]
    if not q:
        return None
    with _cache_lock:
        if q in _game_id_cache:
            return _game_id_cache[q]
    games = search_games(term, limit=3)
    gid = int(games[0]["id"]) if games else None
    with _cache_lock:
        if len(_game_id_cache) >= _CACHE_MAX:
            # Evitar crescimento ilimitado em lotes longos.
            _game_id_cache.clear()
        _game_id_cache[q] = gid
    return gid


def _parse_asset_items(
    data: Any, *, limit: int, allow_ico_via_thumb: bool
) -> list[dict[str, Any]]:
    """Filtra resposta da API → [{url, thumb, score}] com URL PNG aplicável."""
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        thumb = item.get("thumb")
        if not isinstance(url, str) or not is_asset_url(url):
            continue
        if not isinstance(thumb, str) or not is_asset_url(thumb):
            thumb = url
        # Apply só aceita PNG: preferir url PNG; ICO → thumb PNG se existir.
        apply_url = url
        if _url_looks_png(url):
            apply_url = url
        elif allow_ico_via_thumb and _url_looks_ico(url) and _url_looks_png(thumb):
            apply_url = thumb
        elif _url_looks_png(thumb):
            apply_url = thumb
        else:
            continue
        if not is_asset_url(apply_url):
            continue
        preview = thumb if _url_looks_png(thumb) else apply_url
        try:
            score = int(item.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        out.append(
            {
                "url": apply_url,
                "thumb": preview,
                "score": score,
                "label": None,
            }
        )
        if len(out) >= max(1, min(int(limit), 24)):
            break
    out.sort(key=lambda a: -int(a.get("score") or 0))
    return out


def _asset_list(
    kind: str, game_id: int, *, limit: int = _MAX_ASSETS
) -> list[dict[str, Any]]:
    """kind: boxart|cover|icon → grids ou icons PNG estáticos."""
    try:
        gid = int(game_id)
    except (TypeError, ValueError):
        return []
    if gid < 1:
        return []
    kind_n = (kind or "").strip().lower()
    if kind_n in ("boxart", "cover", "grid"):
        endpoint = f"/grids/game/{gid}"
        # Retrato (box) + square + wide (capas Pico 128×96).
        params = {
            "styles": "official,alternate,white_logo,material,blurred,no_logo",
            "dimensions": (
                "600x900,660x930,342x482,512x512,1024x1024,460x215,920x430"
            ),
            "mimes": "image/png",
            "types": "static",
            "nsfw": "false",
            "humor": "any",
        }
        retry_params = {
            "mimes": "image/png",
            "types": "static",
            "nsfw": "false",
        }
        allow_ico = False
    elif kind_n == "icon":
        endpoint = f"/icons/game/{gid}"
        params = {
            "styles": "official,custom",
            "mimes": "image/png",
            "types": "static",
            "nsfw": "false",
            "humor": "any",
        }
        # Ícones SGDB são muitas vezes .ico — pedir ambos e mapear thumb PNG.
        retry_params = {
            "mimes": "image/png,image/vnd.microsoft.icon",
            "types": "static",
            "nsfw": "false",
        }
        allow_ico = True
    else:
        return []

    data = _api_get(endpoint, params=params)
    out = _parse_asset_items(data, limit=limit, allow_ico_via_thumb=allow_ico)
    # Retry se a API rejeitar filtros OU devolver lista vazia (caso comum).
    if not out:
        data = _api_get(endpoint, params=retry_params)
        out = _parse_asset_items(
            data, limit=limit, allow_ico_via_thumb=allow_ico
        )
    return out


def candidate_assets(
    term: str,
    kind: str,
    *,
    game_name: Optional[str] = None,
    limit: int = _MAX_ASSETS,
) -> list[dict[str, Any]]:
    """
    Candidatos {url, thumb/preview, label, source='steamgriddb', score}.
    Sem chave ou sem match → [].
    """
    has_key = bool(get_api_key())
    if not has_key:
        return []
    q = (term or "").strip()[:120]
    if not q:
        return []
    games = search_games(q, limit=4)
    if not games:
        return []
    label_base = (game_name or games[0].get("name") or q).strip()[:200]
    # Tentar o melhor jogo; se sem assets, o seguinte.
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for game in games:
        assets = _asset_list(kind, int(game["id"]), limit=limit)
        gname = str(game.get("name") or label_base)[:200]
        for a in assets:
            url = a["url"]
            if url in seen:
                continue
            seen.add(url)
            collected.append(
                {
                    "url": url,
                    "preview": a.get("thumb") or url,
                    "thumb": a.get("thumb") or url,
                    "label": f"SteamGridDB · {gname}",
                    "source": "steamgriddb",
                    "score": a.get("score") or 0,
                }
            )
            if len(collected) >= limit:
                return collected
    return collected


def fetch_asset_png_bytes(term: str, kind: str) -> Optional[bytes]:
    """1.ª grelha/ícone PNG válida para o termo (lote / auto)."""
    for cand in candidate_assets(term, kind, limit=4):
        data = download_png_bytes(cand["url"])
        if data:
            return data
    return None


def download_png_bytes(
    url: str, *, timeout: Optional[float] = None
) -> Optional[bytes]:
    """GET CDN allowlisted → PNG válido."""
    if not is_asset_url(url):
        return None
    to = _DOWNLOAD_TIMEOUT if timeout is None else float(timeout)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=to) as resp:  # nosec B310
            chunks: list[bytes] = []
            written = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_DOWNLOAD_BYTES:
                    return None
                chunks.append(chunk)
        data = b"".join(chunks)
        if (
            len(data) >= _PNG_MIN
            and len(data) <= _MAX_DOWNLOAD_BYTES
            and data[:8] == _PNG_SIG
        ):
            return data
        return None
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None
