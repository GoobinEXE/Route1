# Changelog

Todas as mudanças notáveis deste projeto são documentadas neste arquivo.

O formato se inspira em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere a [Versionamento Semântico](https://semver.org/lang/pt-BR/).

**Notas para usuários:** linguagem simples; **dizer o quê**, sem explicar o funcionamento.
Aparecem na aba **Sobre**. Build, CI, código, README e docs do Git ficam em **Desenvolvimento**.

## [Unreleased]

## [1.2.0] — 2026-11-14

### Alterado

- **Novo nome: Route Pico** (antes Route 1 Kit). O app passa a focar o cartucho DSPico; Softmod DSi e Outros flashcards ficam em **Mais ferramentas**

- **Navegação de console**: o app abre num Início com blocos para cada tarefa, como o menu de um console; cada bloco abre uma tela com Voltar, e embaixo ficam a barra de ícones (Início, Atividade, Configurações). Setas movem a seleção, Enter abre, Esc volta. Utilidades deixa de existir (cada função foi para o lugar dela), o cartão é escolhido só na barra de cima e a gaveta Atividade abre sozinha durante operações

- **Regras da PicoDex primeiro**: capas escolhidas no catálogo libretro-thumbnails como na PicoDex (antes de SteamGridDB e GameTDB), cada capa/ícone gravado em um só destino, pastas `Games/` por sistema iguais às da PicoDex (GB e GBC em `gb/`, Mega Drive em `gen/`, `.dsi` em `nds/`) e versão do Pico Loader identificada pelo manifesto da PicoDex
- **Pico Loader 1.7.1** no pacote oficial; a atualização do loader passa a copiar também `patchlist.bin`

### Adicionado

- **Temas novos**: Dupla Tela, Câmera Dupla, Canais, Tablet de Sala, Cubo, Estéreo 3D e Híbrido, inspirados em menus de consoles, cada um com paleta original e modos Claro (Catppuccin Latte), Noturno (Catppuccin Mocha) ou Sistema. Cada tema arruma o Início do seu jeito: duas telas com cantos azuis, fileira de ícones com balão, grade de canais com barra curva e relógio, grade de vidro com bloco ciano, painéis violeta com barra dourada, bandeja de blocos com cantos menta, ou fileira de blocos com doca redonda
- **Início** com o estado do microSD, o próximo passo (preparar, adicionar jogos, ver jogos) com um botão, dez blocos com ícones coloridos e selos, hora e medidor de espaço na barra de cima
- **Funções reunidas**: a saúde do cartão foi para a tela Cartão; as Apps homebrew entraram na Biblioteca TWiLight; o assistente se dividiu entre Softmod DSi (SD lateral) e Flashcards R4/GEi (cartucho); o pacote DSPico ficou só no Cartão, com o caminho «Começar do zero»; Configurações fica só na barra de baixo
- **Telas mais curtas**: cada tela abre com uma ação principal, e o que é raro (atualizações, reinstalação, manuais, organizar pastas, Sobre) fica em seções recolhíveis; Jogos abre pela biblioteca; Emuladores tem a barra «Instalar selecionados» fixa embaixo
- **Fonte Geist** em toda a interface (cantos retos, no lugar da Nunito arredondada) e **ícones sólidos** de cantos retos nos blocos, abas e barras
- **Ícone novo do programa**: a framboesa do DSPico (logo do LNH team, CC BY-SA 4.0) com a seta de rota, no lugar do antigo "1" do Route 1 Kit
- Interface mais limpa: títulos de seção em frase normal, ícones desenhados em vez de emojis no estado do microSD e no RouteDex, objetivos do assistente em lista, grafia atual (atualizar, selecionar, ativo)
- Textos em português do Brasil em todo o app e no app do console: arquivo, console, tela, Configurações, Baixar, Salvar
- **Fontes oficiais**: PicoDex, Pico Launcher, Pico Loader e as duas variantes Enhanced em um registro único, com versões fixadas, verificação semanal e PR automático; os dados da PicoDex podem ser atualizados em Verificar atualizações
- **RouteDex** (DSPico → RouteDex): favoritos, concluídos, partidas e tempo de jogo do Pico Launcher Enhanced, com edição à mão
- **Saúde do cartão**: versão do Pico Loader e do launcher, arquivos ausentes ou de releases misturadas, saves sem jogo ou duplicados, capas órfãs e lixo do macOS (com cópia no computador antes de remover)
- **Capturas** do Enhanced com as duas telas juntas, para salvar em PNG ou apagar
- **Banners e capas de pasta**, **fundos noturnos** dos temas e **importar cheats** (`usrcheat.dat`)
- **Pico Launcher Enhanced / Pico Loader Enhanced** como opção recomendada em Verificar Atualizações, com aviso de versão não oficial e «Voltar ao oficial»

### Corrigido

- O app no macOS passa a ser assinado e notarizado pela Apple: abre sem o aviso de desenvolvedor não identificado
- A tela Cartão não mostra mais «Outra operação já está em andamento» ao abrir enquanto o Início ainda verifica o cartão
- A gaveta Atividade não abre mais por cima da lista de atualizações, e as colunas da lista ficaram alinhadas
- A Biblioteca TWiLight acompanha o cartão escolhido na barra de cima
- No macOS, imagens de disco montadas (como o DMG do instalador) não aparecem mais na lista de cartões

### Desenvolvimento

- RouteDex baseado no PicoDex de rasalopa (MIT); licenças em `docs/licenses/`
- `tools/gen_pico_manifest.py` gera `core/data/pico_manifest.json`; pins `pico_launcher_enhanced` / `pico_loader_enhanced_dspico`
- Repositório Route1-DSi integrado: app do console em `nds/`, spec R1USB unificada em `protocol/R1USB.md`, plano e manuais em `docs/console/`; testes C e de conformidade do protocolo rodam no `pytest`
- Artefatos de build renomeados para `RoutePico` (AppId Windows e bundle id macOS mantidos para atualizar instalações existentes)
- Versão única em `core/__init__.py`: o Info.plist do macOS e o instalador Windows leem dali
- macOS: assinatura Developer ID com hardened runtime, notarização e staple no `tools/build_macos_release.sh` e no workflow de release (ver `docs/MACOS_SIGNING.md`)
- Testes isolados das preferências reais do usuário e da chave SteamGridDB do ambiente

## [1.1.0] — 2026-10-11

### Alterado

- **UI redesenhada (pywebview + Tailwind)**: sidebar com DSPico e Softmod em destaque; GEi/R4 despromovidos; shell em `static/` + `services/FilePickerPort` / `web_events`

### Adicionado

- **Verificar Atualizações** (ecossistema DSPico): canal pinado e opt-in «mais recente» LNH com verificação por digest
- Área **Utilidades**: Emuladores, Apps (incl. DSPico USB), Capas/Ícones, Temas Pico Launcher

### Adicionado

- **Capas e ícones no DSPico**: pesquisa online (SteamGridDB + GameTDB + Libretro), opções semelhantes / campo de pesquisa, escolha manual PNG/BMP; grava BMP Pico Launcher em `/_pico/covers/` e `/_pico/icons/`
- **SteamGridDB**: fonte principal de capas/ícones (TWiLight e DSPico); chave API em Configurações (ou env `STEAMGRIDDB_API_KEY`); fallback GameTDB / Libretro
- Modo de topo **DSPico**: estado do microSD, instalar pacote oficial LNH, jogos em `Games/`, emunand, `settings.json` e firmware UF2 (só releases `LNH-team`)
- **Emuladores** no modo DSPico: seleção múltipla (GBARunner3/2, GameYob, nesDS, Atari, Sega, NGP, TurboGrafx, Coleco, Intellivision, SNEmulDS, jEnesisDS, NeoDS); instala em `/_pico/emulators/` ou `/Emulators/`, cria `/ROMs/…` e configura `fileAssociations` (SHA-256 pinado; sem BIOS proprietária)
- **Organizar pastas** no modo DSPico: remove conteúdo de outros sistemas e organiza jogos por franquia, plataforma (`nds`/`dsi`), soltos em `Games/` ou soltos na raiz ao lado do launcher; preserva `/ROMs/`, `_gba/`, `Emulators/` e `data/`
- Kit TWiLight inclui o add-on **Virtual Console** (GameYob para GB/GBC e outros emuladores retro)
- Organização de jogos sincroniza saves/estados dos emuladores (GameYob `.sav`/`.yss`/`.ysN`, cheats `.cht`, S8DS `.gg.sav`/`.sms.sav`) e cria todas as pastas `/roms/` do Virtual Console (nes, snes, tg16, cpc, …)
- Pacote base **GEi v4.2 EN** incluído em `vendor/GEiv4.2_EN` (kernel + `_SYSTEM_` + MoonShell) — instalação sem pasta em Downloads
- Instalação automatizada de **hiyaCFW** (SDNAND a partir do `nand.bin`, tools TWLMagician pinados)
- Instalação do pacote **DSPico** (Pico Launcher + Loader oficiais) no microSD
- Passos no Assistente e cards no Modo avançado para hiyaCFW e DSPico
- Organização de jogos com escolha de layout: **por console**, **por franquia**, ou **console + franquia** (`/roms/nds/Pokemon/`)
- **Gerenciador de jogos** no cartão: adicionar/remover ROMs no app (cópia rápida), com opções de save ao apagar (apagar / backup no PC / manter no SD)
- **Explorador visual** de `/roms/` (árvore + grade): arrastar entre pastas e soltar arquivos do computador; remoção com painel de opções de save
- Explorador: **tooltip** ao pairar 3s e **gaveta de detalhes** (capa, como roda, saves) com troca de capa/ícone TWiLight
- Capas/ícones multiconsole: GameTDB (NDS) + Libretro Thumbnails (GBA, NES, SNES, …); botão «Buscar capa e ícone» na gaveta; ícones de plataforma SVG (sem placeholders genéricos)

### Corrigido

- hiyaCFW no macOS: tools (`twltool` / `7za`) passam a vir de `Darwin/` pinado (o zip do release é só o GUI)
- hiyaCFW: extracção da SDNAND via `fatcat` (offset TWLN), porque o `7za` Darwin não abre `.img` de NAND
- Organizar jogos: cria as pastas do layout escolhido e remove pastas vazias (em «por franquia» limpa pastas de console vazias que ficavam para trás)

### Alterado

- Modo DSPico: botão **Manual DSPico** (PDF ChiScart) junto dos links GitHub oficiais LNH
- Agents: fontes oficiais DSPico (manual ChiScart + repos LNH) em `AGENTS.md` e `.cursor/rules/dspico-sources.mdc`
- UX/UI das telas de configuração do SD: opções com propósito, “o que escreve” e risco; Assistente e Avançado separam **SD do DSi** vs **MicroSD do cartucho**
- Explorador de jogos: chrome unificado, árvore com hierarquia, grade refinada, barra de estado e remoção em overlay
- Explorador: ícones SVG por plataforma (NDS, GBA, GB, NES, …) em vez de caixas CSS genéricas; listagem usa ícone TWiLight custom quando existir
- Explorador: pesquisa por nome em todo `/roms/` (campo na barra, Escape limpa)
- Organizar jogos: em layout **por franquia** só garante `apps`/`saves`/`bios` (não recria dezenas de pastas de console vazias)

### Desenvolvimento

- `core/pico_artwork.py` + `core/pico_bmp.py`: pesquisa/aplicação de arte DSPico (BMP 8/4 bpp); API `search_dspico_artwork` / `apply_dspico_artwork_url` / `set_dspico_artwork`
- `core/artwork.py`: pipeline multiconsole; `core/boxart.py` passa a reexportar
- Ícones de plataforma em `static/assets/platforms/` (silhuetas originais; ver NOTICE.txt)
- `vendor/GEiv4.2_EN` bundled; `find_gei_source` prioriza vendor e exige `_DS_MSHL.NDS`
- `core/hiya.py`, `core/dspico.py` (inspect/Games/emunand/settings/RP2), pins `DSPICO_CACHE_KEYS` em `core/cache.py`, flags `has_hiya` / `has_dspico` em `inspect_sd`
- UI `static/dspico.js` + tab `mode-dspico`; UF2 só quando `dspico_firmware_uf2_ready()` (asset oficial LNH)
- Componentes UI `.opt-card`, `.path-badge`, `.action-row`, glossário inline em `static/`
- `organize_roms_directory(..., layout=)` + `detect_franchise`; API `organize_roms(mount, layout)`
- `core/rom_manager.py` + `copy_fast` em `sdio`; API `list_roms` / `import_roms` / `delete_roms` / diálogos de arquivo
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
- Script Windows usa `cygpath` para o ZIP; workflow publica artefatos mesmo se um SO falhar

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

- Verificação de arquivos oficiais
- Proteção ao gravar no cartão
- Privacidade nos registros

### Desenvolvimento

- Packaging PyInstaller (`packaging/Route1Kit.spec`) e scripts `tools/build_*_release.sh`
- Instalador Windows (Inno Setup) e DMG macOS; tarballs Linux (portátil + atalho)
- Workflow GitHub Actions `release.yml` (artefatos multiplataforma em tags `v*`)
- README com seção técnica; `app.py` resolve `BASE_DIR` em builds frozen (`sys._MEIPASS`)
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
- Privacidade nos registros

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
