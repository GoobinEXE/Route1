# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste ficheiro.

O formato inspira-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Planejado

- Packaging / instaladores (adiado)
- Release pública `1.0.0`

## [0.9.0] — 2026-09-08

Pré-release de consolidação antes do lançamento oficial.

### Adicionado

- Assistente passo a passo (`static/wizard.js`) com bloqueios de fluxo
- Temas via tokens CSS (`static/themes.css` / `theme.js`)
- Módulos `core/sdio.py`, `core/validate.py`, `core/inspect_sd.py`, `core/privacy.py`
- Suite pytest (`tests/`) e `requirements.lock.txt` com hashes
- Ferramentas `tools/update_pins.py` e `tools/build_icons.py`
- Licença GPL-3.0 (`LICENSE`) e aviso legal no README
- `SECURITY.md` e checklist de smoke test
- Script `start.sh` para Linux

### Segurança

- Downloads com SHA-256 pinado
- Preflight de montagem e validação de volumes removíveis
- Verificação pós-gravação e etapas 1/2 com rollback
- Redação de paths em logs (`core/privacy.py`)

### Alterado

- Identidade do produto: **Route 1 Kit**
- Bridge `Api` em `app.py` com operações serializadas e erros estruturados
- Ícones e marca regenerados
