"""Testes do parser / payload da tela Sobre."""

from core.about import (
    EXTERNAL_URL_ALLOWLIST,
    build_about_payload,
    parse_latest_changelog,
)
from core import __version__

import app as app_mod


SAMPLE = """# Changelog

## [Unreleased]

### Adicionado

- Algo ainda não lançado

## [1.0.2] — 2026-09-08

### Corrigido

- Compatibilidade dos instaladores (Windows e macOS)
- Estabilidade na publicação das versões

### Desenvolvimento

- Spec PyInstaller só importa BUNDLE no macOS
- Script Windows usa cygpath para o ZIP

## [1.0.1] — 2026-09-08

### Corrigido

- Lock regenerado
"""


def test_parse_skips_unreleased_and_internal():
    latest = parse_latest_changelog(SAMPLE)
    assert latest is not None
    assert latest["version"] == "1.0.2"
    assert latest["date"] == "2026-09-08"
    assert latest["sections"] == [
        {
            "title": "Correções",
            "items": [
                "Compatibilidade dos instaladores (Windows e macOS)",
                "Estabilidade na publicação das versões",
            ],
        }
    ]
    joined = " ".join(latest["sections"][0]["items"])
    assert "PyInstaller" not in joined
    assert "cygpath" not in joined


def test_parse_omits_readme_and_repo_docs():
    text = """## [2.0.0] — 2026-09-09

### Corrigido

- App abre mais depressa
- Links do README apontam para o repositório certo
- Atualizado o CHANGELOG e o AGENTS.md

### Documentação

- Mais exemplos no guia do GitHub
"""
    latest = parse_latest_changelog(text)
    assert latest is not None
    assert latest["sections"] == [
        {"title": "Correções", "items": ["App abre mais depressa"]}
    ]


def test_parse_empty():
    assert parse_latest_changelog("") is None
    assert parse_latest_changelog(None) is None


def test_build_about_payload_user_facing_latest():
    data = build_about_payload(app_mod.BASE_DIR)
    assert data["success"] is True
    assert data["version"] == __version__
    release = data["latest_release"]
    assert release is not None
    assert release["version"] == "1.0.2"
    titles = [s["title"] for s in release["sections"]]
    assert "Desenvolvimento" not in titles
    assert "Correções" in titles
    blob = " ".join(
        item for sec in release["sections"] for item in sec["items"]
    ).lower()
    assert "pyinstaller" not in blob
    assert "cygpath" not in blob
    assert data["creator"]["name"] == "GoobinEXE"
    assert data["studio"]["name"] == "Dark Room"
    assert data["warnings"]
    assert data["legal"]


def test_api_get_about():
    api = app_mod.Api()
    res = api.get_about()
    assert res["success"] is True
    assert res["app_name"] == "Route 1 Kit"
    assert res["studio"]["name"] == "Dark Room"
    assert res["latest_release"]["version"]


def test_api_open_external_allowlist(monkeypatch):
    api = app_mod.Api()
    opened = []

    monkeypatch.setattr(
        app_mod.webbrowser, "open", lambda url: opened.append(url) or True
    )

    bad = api.open_external_url("https://evil.example/")
    assert bad["success"] is False
    assert opened == []

    url = next(iter(EXTERNAL_URL_ALLOWLIST))
    ok = api.open_external_url(url)
    assert ok["success"] is True
    assert opened == [url]

    gb = "https://www.gamebrew.org/wiki/GodMode9i"
    ok2 = api.open_external_url(gb)
    assert ok2["success"] is True
    assert opened[-1] == gb

    udb = "https://db.universal-team.net/ds/godmode9i"
    ok3 = api.open_external_url(udb)
    assert ok3["success"] is True
    assert opened[-1] == udb

    nested = api.open_external_url("https://www.gamebrew.org/wiki/foo/bar")
    assert nested["success"] is False

    udb_nested = api.open_external_url("https://db.universal-team.net/ds/foo/bar")
    assert udb_nested["success"] is False


def test_api_homebrew_catalog():
    api = app_mod.Api()
    res = api.get_homebrew_catalog()
    assert res["success"] is True
    assert res["apps"]
    assert all(a.get("installable") for a in res["apps"])

