# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste ficheiro.

O formato inspira-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [1.0.2] — 2026-09-08

### Corrigido

- Spec PyInstaller só importa `BUNDLE` no macOS (quebrava o build Windows)
- Script Windows usa `cygpath` para o ZIP; workflow publica artefactos mesmo se um SO falhar

## [1.0.1] — 2026-09-08

### Corrigido

- `requirements.lock.txt` regenerado com `backports-zstd` (necessário em Python abaixo de 3.14) para `pip install --require-hashes` no CI
- Links do README / Inno apontam para o repositório renomeado [GoobinEXE/Route1](https://github.com/GoobinEXE/Route1)

## [1.0.0] — 2026-09-08

Primeira release pública do **Route 1 Kit**, com builds portátil e instalável.

> Nota: a tag `v1.0.0` falhou no CI por lock incompleto; use **`v1.0.1`** para os artefactos oficiais.

### Adicionado

- Packaging PyInstaller (`packaging/Route1Kit.spec`) e scripts `tools/build_*_release.sh`
- Instalador Windows (Inno Setup) e DMG macOS; tarballs Linux (portátil + atalho)
- Workflow GitHub Actions `release.yml` (artefactos multiplataforma em tags `v*`)
- Utilitários: boxarts (GameTDB), GodMode9i, cheats `usrcheat.dat`, relatório de SD
- README orientado a iniciantes (tutorial do Assistente) + secção técnica

### Alterado

- Versão do produto: **1.0.0**
- `app.py` resolve `BASE_DIR` corretamente em builds frozen (`sys._MEIPASS`)

### Segurança

- Mantidos pins SHA-256, preflight de montagem, rollback e redação de paths

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
