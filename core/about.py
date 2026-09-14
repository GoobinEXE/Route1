"""Metadados da tela Sobre e parsing da última entrada do CHANGELOG."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core import __version__

REPO_URL = "https://github.com/GoobinEXE/Route1"
RELEASES_URL = f"{REPO_URL}/releases"
GUIDE_URL = "https://dsi.cfw.guide/"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"
GAMEBREW_WIKI_PREFIX = "https://www.gamebrew.org/wiki/"
_GAMEBREW_SLUG_RE = re.compile(r"^[A-Za-z0-9_()%.\-]+$")
_GITHUB_REPO_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$"
)
_GITHUB_RELEASE_TAG_RE = re.compile(
    r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
    r"/releases/tag/([A-Za-z0-9_.\-]+)$"
)

# URLs exactas que a UI pode abrir no browser do sistema (allowlist).
EXTERNAL_URL_ALLOWLIST = frozenset(
    {
        REPO_URL,
        RELEASES_URL,
        GUIDE_URL,
        LICENSE_URL,
        f"{REPO_URL}/blob/main/CHANGELOG.md",
        f"{REPO_URL}/blob/main/LICENSE",
        "https://www.gamebrew.org/wiki/List_of_DS_homebrew_applications",
    }
)


def _pinned_github_repos() -> frozenset:
    """Repositórios GitHub pinados em PIN_META (import lazy)."""
    from core.cache import PIN_META

    repos = set()
    for meta in PIN_META.values():
        repo = meta.get("repo") if isinstance(meta, dict) else None
        if isinstance(repo, str) and repo.strip() and "/" in repo:
            repos.add(repo.strip().strip("/"))
    return frozenset(repos)


def _pinned_github_release_pages() -> frozenset:
    from core.cache import PIN_META

    pages = set()
    for meta in PIN_META.values():
        if not isinstance(meta, dict):
            continue
        repo = meta.get("repo")
        tag = meta.get("tag")
        if not isinstance(repo, str) or not isinstance(tag, str):
            continue
        repo = repo.strip().strip("/")
        tag = tag.strip()
        if repo and tag and "/" in repo and "/" not in tag and ".." not in repo:
            pages.add(f"https://github.com/{repo}/releases/tag/{tag}")
    return frozenset(pages)


def is_allowed_external_url(url: str) -> bool:
    """Allowlist exacta + GameBrew wiki + repos/releases GitHub pinados."""
    if not isinstance(url, str):
        return False
    cleaned = url.strip()
    if cleaned in EXTERNAL_URL_ALLOWLIST:
        return True
    if cleaned.startswith(GAMEBREW_WIKI_PREFIX):
        slug = cleaned[len(GAMEBREW_WIKI_PREFIX) :]
        if not slug or "/" in slug or "\\" in slug or ".." in slug:
            return False
        return bool(_GAMEBREW_SLUG_RE.fullmatch(slug))

    repo_m = _GITHUB_REPO_RE.fullmatch(cleaned.rstrip("/"))
    if repo_m:
        repo = f"{repo_m.group(1)}/{repo_m.group(2)}"
        return repo in _pinned_github_repos()

    if _GITHUB_RELEASE_TAG_RE.fullmatch(cleaned):
        return cleaned in _pinned_github_release_pages()

    return False

_HEADING_RE = re.compile(
    r"^##\s+\[([^\]]+)\](?:\s*[—–-]\s*(\d{4}-\d{2}-\d{2}))?\s*$"
)
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
_SECTION_RE = re.compile(r"^###\s+(.+)$")

# Secções só para maintainers — não entram na aba Sobre.
_INTERNAL_SECTIONS = frozenset(
    {
        "desenvolvimento",
        "interno",
        "técnico",
        "tecnico",
        "build",
        "ci",
        "documentação",
        "documentacao",
        "docs",
        "repositório",
        "repositorio",
    }
)

# Itens de docs/git que, se forem parar a uma secção de utilizador por engano, são omitidos na UI.
_REPO_DOCS_ONLY_RE = re.compile(
    r"(?i)("
    r"\breadme\b|"
    r"\bchangelog\b|"
    r"\bagents\.md\b|"
    r"\bsecurity\.md\b|"
    r"\blicense\b|"
    r"aviso legal no (readme|guia)|"
    r"liga[cç][oõ]es? do (readme|guia|reposit)|"
    r"links? do (readme|guia|reposit|inno)|"
    r"reposit[oó]rio renomeado|"
    r"documenta[cç][aã]o (do )?(repo|git|projeto)|"
    r"apenas (no|para o) (git|reposit)|"
    r"pull request|\bprs?\b"
    r")"
)

# Títulos mostrados a utilizadores leigos / medianos.
_USER_SECTION_TITLES = {
    "adicionado": "Novidades",
    "alterado": "Melhorias",
    "corrigido": "Correções",
    "segurança": "Segurança",
    "seguranca": "Segurança",
    "removido": "Removido",
    "descontinuado": "Avisos",
    "geral": "Geral",
}


def _changelog_path(base_dir: str) -> str:
    return os.path.join(base_dir, "CHANGELOG.md")


def _is_internal_section(title: str) -> bool:
    key = (title or "").strip().lower()
    return key in _INTERNAL_SECTIONS


def _is_repo_docs_only(item: str) -> bool:
    """True para mudanças só de docs/git — não interessam no patch note do app."""
    return bool(_REPO_DOCS_ONLY_RE.search(item or ""))


def _user_section_title(title: str) -> str:
    key = (title or "").strip().lower()
    return _USER_SECTION_TITLES.get(key, (title or "").strip() or "Geral")


def _plain_user_text(text: str) -> str:
    """Remove markdown leve (**negrito**, `código`) das notas para a UI."""
    s = (text or "").strip()
    if not s:
        return ""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s


def parse_latest_changelog(text: str) -> Optional[Dict[str, Any]]:
    """Extrai a primeira versão publicada (ignora Unreleased).

    Secções internas (ex. Desenvolvimento) são omitidas — a UI Sobre
    só mostra notas em linguagem de utilizador.
    """
    if not text or not isinstance(text, str):
        return None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _HEADING_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        version = m.group(1).strip()
        date = (m.group(2) or "").strip() or None
        if version.lower() == "unreleased":
            i += 1
            continue

        i += 1
        body: List[str] = []
        while i < len(lines) and not lines[i].startswith("## "):
            body.append(lines[i])
            i += 1

        summary = ""
        sections: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        skip_section = False
        for raw in body:
            s = raw.strip()
            if not s or s.startswith(">"):
                continue
            sec = _SECTION_RE.match(s)
            if sec:
                raw_title = sec.group(1).strip()
                skip_section = _is_internal_section(raw_title)
                if skip_section:
                    current = None
                    continue
                current = {
                    "title": _user_section_title(raw_title),
                    "items": [],
                }
                sections.append(current)
                continue
            if skip_section:
                continue
            bullet = _BULLET_RE.match(s)
            if bullet:
                item = _plain_user_text(bullet.group(1))
                if not item or _is_repo_docs_only(item):
                    continue
                if current is not None:
                    current["items"].append(item)
                else:
                    if not summary:
                        summary = item
                    else:
                        if not sections or sections[0].get("title") != "Geral":
                            sections.insert(0, {"title": "Geral", "items": []})
                        sections[0]["items"].append(item)
                continue
            if not summary and not s.startswith("#"):
                plain = _plain_user_text(s)
                if plain and not _is_repo_docs_only(plain):
                    summary = plain

        sections = [s for s in sections if s.get("items")]
        return {
            "version": version,
            "date": date,
            "summary": summary,
            "sections": sections,
        }
    return None


def load_latest_changelog(base_dir: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = _changelog_path(base_dir)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return None, str(e)
    return parse_latest_changelog(text), None


def build_about_payload(base_dir: str) -> Dict[str, Any]:
    latest, err = load_latest_changelog(base_dir)
    return {
        "success": True,
        "app_name": "Route 1 Kit",
        "version": __version__,
        "license": "GPL-3.0",
        "repo_url": REPO_URL,
        "releases_url": RELEASES_URL,
        "guide_url": GUIDE_URL,
        "license_url": LICENSE_URL,
        "studio": {
            "name": "Dark Room",
            "role": "Estúdio",
            "blurb": (
                "Estúdio por trás do Route 1 Kit — builds oficiais e identidade "
                "do publisher no Windows."
            ),
        },
        "creator": {
            "name": "GoobinEXE",
            "role": "Criador e maintainer",
            "blurb": (
                "Projeto pessoal open source para tornar o softmod e a preparação "
                "de cartões DSi mais acessíveis, com fluxos guiados e menos risco "
                "de gravar no volume errado."
            ),
            "url": REPO_URL,
        },
        "project": {
            "tagline": "Prepare e organize o cartão do Nintendo DSi",
            "blurb": (
                "App desktop (macOS, Windows e Linux) que prepara o SD para "
                "desbloqueio SD-direct (TWiLight + Unlaunch) e flashcards GEi / R4 — "
                "sem montar pastas à mão."
            ),
            "goals": [
                "Guiar iniciantes pelo Assistente, passo a passo",
                "Oferecer atalhos no Modo avançado para quem já conhece o fluxo",
                "Validar volumes removíveis e downloads com SHA-256 pinado",
                "Reduzir erros comuns (slot errado, pit Facebook, format destrutivo)",
            ],
        },
        "warnings": [
            {
                "title": "Unlaunch / brick",
                "text": "O app só prepara o SD. O Unlaunch, no console, grava na NAND — risco pequeno de brick.",
            },
            {
                "title": "Backup da NAND",
                "text": "Não salte o nand.bin. Guarde a pasta DT… no computador antes de instalar o Unlaunch.",
            },
            {
                "title": "Formatação",
                "text": "FAT32 apaga tudo no volume selecionado. Confirme sempre a unidade certa.",
            },
            {
                "title": "Consola e slot",
                "text": "Só DSi / DSi XL. Softmod = SD lateral; flashcard = MicroSD do cartucho Slot-1.",
            },
        ],
        "legal": [
            "Software “como está” (AS IS), sem garantias. Você assume a responsabilidade pelo uso.",
            "Não afiliado à Nintendo. Marcas pertencem aos respetivos donos.",
            "Código do app: GPL-3.0. Binários descarregados mantêm licenças dos projetos originais.",
            "O app não fornece ROMs; só organiza ficheiros que você coloca no cartão.",
        ],
        "latest_release": latest,
        "changelog_error": err,
    }
