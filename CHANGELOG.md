# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste ficheiro.

O formato inspira-se em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

**Notas para utilizadores:** linguagem simples; **dizer o quê**, sem explicar o funcionamento.
Aparecem na aba **Sobre**. Build, CI, código, README e docs do Git ficam em **Desenvolvimento**.

## [Unreleased]

## [1.1.0] — 2026-10-11

### Alterado

- **UI redesenhada (pywebview + Tailwind)**: sidebar com DSPico e Softmod em destaque; GEi/R4 despromovidos; shell em `static/` + `services/FilePickerPort` / `web_events`

### Adicionado

- **Verificar Atualizações** (ecossistema DSPico): canal pinado e opt-in «mais recente» LNH com verificação por digest
- Área **Utilidades**: Emuladores, Apps (incl. DSPico USB), Capas/Ícones, Temas Pico Launcher

### Adicionado

- **Capas e ícones no DSPico**: pesquisa online (GameTDB + Libretro), opções semelhantes / campo de pesquisa, escolha manual PNG/BMP; grava BMP Pico Launcher em `/_pico/covers/` e `/_pico/icons/`
- Modo de topo **DSPico**: estado do microSD, instalar pacote oficial LNH, jogos em `Games/`, emunand, `settings.json` e firmware UF2 (só releases `LNH-team`)
- **Emuladores** no modo DSPico: selecção múltipla (GBARunner3/2, GameYob, nesDS, Atari, Sega, NGP, TurboGrafx, Coleco, Intellivision, SNEmulDS, jEnesisDS, NeoDS); instala em `/_pico/emulators/` ou `/Emulators/`, cria `/ROMs/…` e configura `fileAssociations` (SHA-256 pinado; sem BIOS proprietária)
- **Organizar pastas** no modo DSPico: remove conteúdo de outros sistemas e organiza jogos por franquia, plataforma (`nds`/`dsi`), soltos em `Games/` ou soltos na raiz ao lado do launcher; preserva `/ROMs/`, `_gba/`, `Emulators/` e `data/`
- Kit TWiLight inclui o add-on **Virtual Console** (GameYob para GB/GBC e outros emuladores retro)
- Organização de jogos sincroniza saves/estados dos emuladores (GameYob `.sav`/`.yss`/`.ysN`, cheats `.cht`, S8DS `.gg.sav`/`.sms.sav`) e cria todas as pastas `/roms/` do Virtual Console (nes, snes, tg16, cpc, …)
- Pacote base **GEi v4.2 EN** incluído em `vendor/GEiv4.2_EN` (kernel + `_SYSTEM_` + MoonShell) — instalação sem pasta em Downloads
- Instalação automatizada de **hiyaCFW** (SDNAND a partir do `nand.bin`, tools TWLMagician pinados)
- Instalação do pacote **DSPico** (Pico Launcher + Loader oficiais) no microSD
- Passos no Assistente e cards no Modo avançado para hiyaCFW e DSPico
- Organização de jogos com escolha de layout: **por consola**, **por franquia**, ou **consola + franquia** (`/roms/nds/Pokemon/`)
- **Gestor de jogos** no cartão: adicionar/remover ROMs no app (cópia rápida), com opções de save ao apagar (apagar / backup no PC / manter no SD)
- **Explorador visual** de `/roms/` (árvore + grelha): arrastar entre pastas e soltar ficheiros do computador; remoção com painel de opções de save
- Explorador: **tooltip** ao pairar 3s e **gaveta de detalhes** (capa, como corre, saves) com troca de capa/ícone TWiLight
- Capas/ícones multi-consola: GameTDB (NDS) + Libretro Thumbnails (GBA, NES, SNES, …); botão «Buscar capa e ícone» na gaveta; ícones de plataforma SVG (sem placeholders genéricos)

### Corrigido

- hiyaCFW no macOS: tools (`twltool` / `7za`) passam a vir de `Darwin/` pinado (o zip do release é só o GUI)
- hiyaCFW: extracção da SDNAND via `fatcat` (offset TWLN), porque o `7za` Darwin não abre `.img` de NAND
- Organizar jogos: cria as pastas do layout escolhido e remove pastas vazias (em «por franquia» limpa pastas de consola vazias que ficavam para trás)

### Alterado

- Modo DSPico: botão **Manual DSPico** (PDF ChiScart) junto dos links GitHub oficiais LNH
- Agents: fontes oficiais DSPico (manual ChiScart + repos LNH) em `AGENTS.md` e `.cursor/rules/dspico-sources.mdc`
- UX/UI das telas de configuração do SD: opções com propósito, “o que escreve” e risco; Assistente e Avançado separam **SD do DSi** vs **MicroSD do cartucho**
- Explorador de jogos: chrome unificado, árvore com hierarquia, grelha refinada, barra de estado e remoção em overlay
- Explorador: ícones SVG por plataforma (NDS, GBA, GB, NES, …) em vez de caixas CSS genéricas; listagem usa ícone TWiLight custom quando existir
- Explorador: pesquisa por nome em todo `/roms/` (campo na barra, Escape limpa)
- Organizar jogos: em layout **por franquia** só garante `apps`/`saves`/`bios` (não recria dezenas de pastas de consola vazias)

### Desenvolvimento

- `core/pico_artwork.py` + `core/pico_bmp.py`: pesquisa/aplicação de arte DSPico (BMP 8/4 bpp); API `search_dspico_artwork` / `apply_dspico_artwork_url` / `set_dspico_artwork`
- `core/artwork.py`: pipeline multi-consola; `core/boxart.py` passa a reexportar
- Ícones de plataforma em `static/assets/platforms/` (silhuetas originais; ver NOTICE.txt)
- `vendor/GEiv4.2_EN` bundled; `find_gei_source` prioriza vendor e exige `_DS_MSHL.NDS`
- `core/hiya.py`, `core/dspico.py` (inspect/Games/emunand/settings/RP2), pins `DSPICO_CACHE_KEYS` em `core/cache.py`, flags `has_hiya` / `has_dspico` em `inspect_sd`
- UI `static/dspico.js` + tab `mode-dspico`; UF2 só quando `dspico_firmware_uf2_ready()` (asset oficial LNH)
- Componentes UI `.opt-card`, `.path-badge`, `.action-row`, glossário inline em `static/`
- `organize_roms_directory(..., layout=)` + `detect_franchise`; API `organize_roms(mount, layout)`
- `core/rom_manager.py` + `copy_fast` em `sdio`; API `list_roms` / `import_roms` / `delete_roms` / diálogos de ficheiro
- Explorador: `list_rom_dir` / `list_rom_tree` / `move_roms` / `mkdir_rom_dir`; drop nativo pywebview; UI `rom_explorer.js`
## [1.0.3] — 2026-09-14

### Adicionado

- Aba **Sobre**
- Estúdio **Dark Room** na aba Sobre e no instalador Windows
- Catálogo **Apps** no modo Avançado: instalação autónoma (download + SHA-256) de homebrew em `/roms/apps/` (GodMode9i, ftpd, NTM, Rocket Video Player, pkmn-chest, etc.)
- Sub-navegação do modo Avançado: **Preparar** · **Cartão** · **Apps**
- Guias GameBrew/README aplicadas na instalação (pastas, `databases.txt` do Kekatsu, cópia nitroFS do pkmn-chest, pastas de vídeos/backups)
- Atalho **GitHub** em cada app do catálogo (abre o repositório oficial) e listagem de todas as fontes de download disponíveis

### Corrigido

- Formatação no macOS: o cluster 32 KB volta a ser aplicado (o sistema pede administrador; se o macOS bloquear, abre o Terminal com sudo)

### Desenvolvimento

- `core/about.py`, `Api.get_about` / `open_external_url`, e `CHANGELOG.md` incluído no build PyInstaller
- Pipeline Windows preparado para Authenticode (Azure Artifact Signing); ver `docs/WINDOWS_SIGNING.md`
- Script Windows com fases `build` / `package` / `all`
- `core/homebrew_catalog.py`, `core/homebrew_install.py`, `install_homebrew`, pins GitHub adicionais em `core/cache.py`
- Catálogo expõe `github_url` + `download_sources` (lista); `URLS` aceita uma ou várias fontes; allowlist GitHub em `open_external_url`

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
