# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste ficheiro.

O formato inspira-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

**Notas para utilizadores:** linguagem simples; **dizer o quê**, sem explicar o funcionamento.
Aparecem na aba **Sobre**. Build, CI, código, README e docs do Git ficam em **Desenvolvimento**.

## [Unreleased]

### Adicionado

- Aba **Sobre**
- Estúdio **Dark Room** na aba Sobre e no instalador Windows

### Desenvolvimento

- `core/about.py`, `Api.get_about` / `open_external_url`, e `CHANGELOG.md` incluído no build PyInstaller
- Pipeline Windows preparado para Authenticode (Azure Artifact Signing); ver `docs/WINDOWS_SIGNING.md`
- Script Windows com fases `build` / `package` / `all`
## [1.0.2] — 2026-09-08

### Corrigido

- Compatibilidade dos instaladores (Windows e macOS)
- Estabilidade na publicação das versões

### Desenvolvimento

- Spec PyInstaller só importa `BUNDLE` no macOS (quebrava o build Windows)
- Script Windows usa `cygpath` para o ZIP; workflow publica artefactos mesmo se um SO falhar

## [1.0.1] — 2026-09-08

### Corrigido

- Estabilidade na instalação e atualização

### Desenvolvimento

- `requirements.lock.txt` regenerado com `backports-zstd` (necessário em Python abaixo de 3.14) para `pip install --require-hashes` no CI
- Links do README / Inno apontam para o repositório renomeado [GoobinEXE/Route1](https://github.com/GoobinEXE/Route1)

## [1.0.0] — 2026-09-08

Primeira versão pública do **Route 1 Kit**.

> Se a **1.0.0** falhar, use a **1.0.1** (ou posterior) nas Releases.

### Adicionado

- Versões para Windows, macOS e Linux
- Capas de jogos, GodMode9i, cheats e relatório do cartão
- Assistente

### Alterado

- Fiabilidade do app instalado / portátil

### Segurança

- Verificação de ficheiros oficiais
- Proteção ao gravar no cartão
- Privacidade nos registos

### Desenvolvimento

- Packaging PyInstaller (`packaging/Route1Kit.spec`) e scripts `tools/build_*_release.sh`
- Instalador Windows (Inno Setup) e DMG macOS; tarballs Linux (portátil + atalho)
- Workflow GitHub Actions `release.yml` (artefactos multiplataforma em tags `v*`)
- README com secção técnica; `app.py` resolve `BASE_DIR` em builds frozen (`sys._MEIPASS`)
- Pins SHA-256, preflight de montagem, rollback e redação de paths

## [0.9.0] — 2026-09-08

Pré-versão antes do lançamento oficial.

### Adicionado

- Assistente
- Temas
- Arranque no Linux

### Segurança

- Verificação de downloads
- Proteção de volumes removíveis
- Recuperação após falha
- Privacidade nos registos

### Alterado

- Nome do produto: **Route 1 Kit**
- Ícones e identidade visual

### Desenvolvimento

- Licença GPL-3.0 (`LICENSE`), aviso legal no README, `SECURITY.md` e checklist de smoke test
- Temas via tokens CSS (`static/themes.css` / `theme.js`)
- Módulos `core/sdio.py`, `core/validate.py`, `core/inspect_sd.py`, `core/privacy.py`
- Suite pytest (`tests/`) e `requirements.lock.txt` com hashes
- Ferramentas `tools/update_pins.py` e `tools/build_icons.py`
- Bridge `Api` em `app.py` com operações serializadas e erros estruturados
