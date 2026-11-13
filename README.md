# Route Pico

Licensed under the GNU General Public License v3.0 — see [`LICENSE`](LICENSE).

**Route Pico** (antes **Route 1 Kit**) é um aplicativo desktop para **macOS, Windows e Linux** que prepara e mantém o microSD do cartucho **DSPico**: pacote oficial do LNH team, jogos, capas, emuladores, emunand, firmware e a biblioteca **RouteDex**. O softmod do **Nintendo DSi** e os flashcards **GEi / AceKard / R4** continuam disponíveis em **Mais ferramentas**.

A interface é uma **janela nativa pywebview** com UI HTML/CSS/JS offline em `static/` (Tailwind local, sem CDN e sem servidor HTTP). A lógica de cartão continua em Python (`core/`).

> A pasta ou o repositório podem ainda chamar-se `DSi-SD-Studio` / `Route1`; o nome do produto é **Route Pico**. Preferências, cache (`~/.route_1_kit_cache`) e a pasta de backups `Route1Kit_Saves` mantêm o nome antigo para não perder dados de quem atualiza.

---

## Baixar (release 1.1.0)

Builds oficiais: [Releases no GitHub](https://github.com/GoobinEXE/Route1/releases).

| Plataforma | Portátil | Instalável |
|------------|----------|------------|
| **macOS** | ZIP com `Route Pico.app` | DMG (arraste para Aplicações) |
| **Windows** | ZIP com a pasta do app | `setup.exe` (Inno Setup) |
| **Linux** | `.tar.gz` onedir | `.tar.gz` com script de atalho `.desktop` |

Na primeira abertura no macOS/Windows, o sistema pode pedir confirmação de segurança (binário ainda não notarizado pela Apple / SmartScreen sem Authenticode). Prefira sempre baixar da página de Releases deste repositório. Builds Windows oficiais passam a ser assinados como **Dark Room** quando o Azure Artifact Signing estiver configurado ([guia](docs/WINDOWS_SIGNING.md)).

Se preferir rodar a partir do código-fonte, use a seção [Como abrir o aplicativo](#como-abrir-o-aplicativo) abaixo.

---

## Para quem é este app?

- Você tem um **DSPico** e quer preparar o microSD com o pacote oficial, organizar jogos em `Games/`, pôr capas e emuladores e manter tudo atualizado.
- Você usa o **Pico Launcher Enhanced** e quer ver e corrigir favoritos, jogos concluídos e tempo de jogo no computador, ou ver as capturas de tela que fez no console.
- Você quer **desbloquear o DSi** (SD-direct com TWiLight Menu++ e Unlaunch) ou montar o MicroSD de um flashcard GEi / R4: isso está em **Mais ferramentas**.

Se é a primeira vez: abra **DSPico → Preparar SD**. O **Assistente** continua a guiar o softmod do DSi passo a passo.

---

## RouteDex

O separador **DSPico → RouteDex** lê e escreve diretamente no microSD, sem browser e sem servidor:

- **Biblioteca:** favoritos, concluídos, número de partidas, tempo de jogo e últimos jogados de `/_pico/gamedata.json`, com edição à mão. Campos que o Route Pico não conhece são preservados, e um `gamedata.json` que não faz parse nunca é sobrescrito.
- **Saúde do cartão:** arquivos do loader ausente, versão do Pico Loader e do launcher identificadas offline por hash (incluindo arquivos de releases misturadas ou de outro flashcard), saves sem jogo, saves em duplicado, capas órfãs e lixo do macOS. Tudo o que é removido é copiado antes para o computador.
- **Capturas:** as capturas do Enhanced (`shotNNN_top/bot.bmp`) com as duas telas empilhadas, para salvar em PNG ou apagar.
- **Pastas:** `banner.bnr` (ícone e nome mostrado), `cover.bmp` de pasta.
- **Fundos noturnos** dos temas (`*_night.bin`) e **cheats** (`usrcheat.dat` importado de um arquivo seu, validado antes de ir para o cartão).

O RouteDex é um port nativo das regras do [PicoDex](https://github.com/rasalopa/picodex) de rasalopa (licença MIT; aviso em [`docs/licenses/`](docs/licenses/)). Onde o app e a PicoDex fazem a mesma coisa, vale a regra da PicoDex: pastas por sistema em `Games/` (`nds`, `gba`, `gb`, `gen`, `sms`, `gg`, `nes`, `snes`, `ws`, `ngp`), onde gravar capas e ícones, escolha de capas no catálogo libretro-thumbnails (primeira fonte, antes de SteamGridDB e GameTDB) e versão do Pico Loader pelo manifesto que a própria PicoDex mantém.

## Fontes oficiais

O Route Pico usa e atualiza-se a partir de cinco repositórios, e só deles: [PicoDex](https://github.com/rasalopa/picodex), [Pico Launcher](https://github.com/LNH-team/pico-launcher), [Pico Loader](https://github.com/LNH-team/pico-loader), [Pico Launcher Enhanced](https://github.com/rasalopa/pico-launcher-enhanced) e [Pico Loader Enhanced](https://github.com/rasalopa/pico-loader). As versões em uso e os SHA-256 ficam em `core/data/upstreams.lock.json`; `tools/sync_upstreams.py --apply` traz as releases mais recentes e o workflow semanal abre um PR com elas. No app, **Verificar atualizações** compara o cartão com a versão do app e com a release mais recente de cada fonte, e permite atualizar os dados da PicoDex sem nova versão do Route Pico.

## Route Pico no console (em desenvolvimento)

Em [`nds/`](nds/) está o app `.nds` do Route Pico: um gerenciador de arquivos do microSD que roda no próprio DS a partir do Pico Launcher, com proteção de `_picoboot.nds` e `_pico/`. As próximas fases ligam-no ao desktop por USB (protocolo [R1USB](protocol/R1USB.md)), com cópia verificada por SHA-256 sem tirar o cartão do cartucho. Estado e fases: [`docs/console/PLAN.md`](docs/console/PLAN.md). O `.nds` ainda não foi validado em hardware.

## Pico Launcher Enhanced (opcional, recomendado)

Por padrão o Route Pico instala só o Pico Launcher e o Pico Loader **oficiais** do LNH team. Em **Verificar Atualizações** pode escolher as variantes [Enhanced](https://github.com/rasalopa/pico-launcher-enhanced) de rasalopa (licença Zlib): favoritos, estatísticas, recentes, capturas, slots de save e, com o Loader Enhanced, a volta ao launcher de dentro do jogo.

São forks **não oficiais**: problemas com elas vão para o repositório do rasalopa, não para o LNH team. O Loader Enhanced é só para o DSPico. Os dois zips estão pinados por SHA-256 como o resto, o launcher troca só `/_picoboot.nds` (e os temas incluídos), o loader troca só `picoLoader7.bin`/`picoLoader9.bin`, e o mesmo painel tem **Voltar ao oficial**.

---

## O que você precisa

1. **Console** — Nintendo DSi / DSi XL (slot lateral) e/ou um DS/DSi com flashcard Slot-1.
2. **Cartão SD / MicroSD** — de preferência um cartão de **teste** na primeira utilização. Tamanhos comuns: 2–32 GB (FAT32).
3. **Leitor de cartão** ligado ao computador.
4. **Computador** com macOS, Windows ou Linux e conexão com a internet **só** para o app baixar os binários oficiais na primeira vez (depois ficam em cache local).

### Aviso importante (leia antes de gravar no console)

O Route Pico **prepara arquivos no cartão SD**. **Não grava na NAND** do DSi por si só.

Ferramentas como o **Unlaunch**, quando executadas **no console**, **escrevem na memória interna**. Há um risco real (ainda que pequeno) de *brick*. **Não salte o backup da NAND** (`nand.bin`) e guarde uma cópia segura no computador. Siga também o guia da comunidade: [dsi.cfw.guide](https://dsi.cfw.guide/).

Detalhes legais e de responsabilidade: [Aviso legal / Termos de uso](#aviso-legal--termos-de-uso).

---

## Como abrir o aplicativo

Os scripts abaixo criam o ambiente Python (se ainda não existir), instalam dependências com verificação de hashes e abrem a janela.

### macOS — dois cliques

No Finder, abra a pasta do projeto e dê dois cliques em **`start.command`**.

### Windows — dois cliques

Execute **`start.bat`**.

### Linux

No terminal, na pasta do projeto:

```bash
chmod +x start.sh   # só na primeira vez
./start.sh
```

### Terminal (qualquer sistema)

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python app.py
```

Feche a janela para encerrar o app.

---

## Guia do iniciante: o Assistente

Ao abrir, o Route Pico começa no **Assistente**. Escolha o objetivo que corresponde ao que pretende fazer.

A preferência Assistente / Avançado vale **só nesta sessão**. Se fechar a meio do guia, na próxima abertura volta ao início do Assistente.

### 1. Instalar SD-direct (desbloqueio pelo slot lateral)

Para jogar pelo cartão SD do **lado do DSi**, sem flashcard:

1. Confirme que o console é um **DSi / DSi XL**.
2. Indique se a **Câmera Nintendo DSi** tem o ícone do **Facebook** ou não (define a versão correta do Memory Pit).
3. Selecione o cartão do **slot lateral** (não o MicroSD de um flashcard).
4. O app prepara o **Passo 1** (Memory Pit + dumpTool como `boot.nds`).
5. No DSi, abra a Câmera, aceda ao cartão SD e siga o **dumpTool** para criar o `nand.bin`.
6. Volte o cartão ao PC: o app valida o backup e salva uma cópia no computador.
7. O app prepara o **Passo 2** (TWiLight Menu++ + instalador seguro do Unlaunch).
8. No DSi, execute o instalador do Unlaunch e configure a inicialização (conforme o guia oficial).
9. Se quiser, organize jogos e finalize.

### 2. Atualizar SD-direct

Para um cartão que **já** tem TWiLight / softmod: o Assistente atualiza os componentes oficiais (com verificação SHA-256), preservando jogos e saves quando possível.

### 3. Criar flashcard do zero

Para um MicroSD novo (ou a limpar) no cartucho Slot-1:

1. Escolha a marca: **Galaxy Eagle i (GEi)** ou **R4**.
2. Formate em FAT32 se for preciso (o app usa cluster adequado; a formatação **apaga tudo**).
3. Instale o kernel e a estrutura de pastas.

O **GEi** usa o pacote base incluído em `vendor/GEiv4.2_EN` (pode sobrescrever com `~/Downloads/GEiv4.2_EN` completa). Clones “R4” são muitos: o kernel tem de ser o **do seu** modelo. Kernel errado = cartucho não inicia.

### 4. Atualizar flashcard

Faz backup preventivo (quando aplicável) e atualiza o kernel GEi ou R4.

---

## Dicas para quem está a começar

- **FAT32** — o DSi e a maioria dos flashcards esperam FAT32. Cartões grandes: cluster **32 KB** costuma ser o mais fiável neste ecossistema.
- **Dois cartões diferentes** — SD lateral (softmod) ≠ MicroSD dentro do flashcard. Não misture os fluxos.
- **Ejeção segura** — sempre “Ejetar” / “Remover com segurança” antes de puxar o cartão do PC.
- **Cartão de teste** — na primeira vez, use um cartão sem dados importantes.
- **Guia oficial** — o Assistente acompanha o fluxo; para teoria e troubleshooting no console, use [dsi.cfw.guide](https://dsi.cfw.guide/).
- **Lista vazia de unidades** — o app só mostra volumes **removíveis**. Confirme o leitor, monte o cartão no sistema e atualize a lista.

---

## Modo DSPico

Separador de topo para o flashcart [DSPico](https://github.com/LNH-team/dspico-hardware) (LNH-team). Referências: [manual do usuário](https://www.chiscart.com/manuals/DS_Pico_user_manual_87a632eec6.pdf) (ChiScart), [GUIDE](https://github.com/LNH-team/dspico/blob/develop/GUIDE.md) e repos [pico-launcher](https://github.com/LNH-team/pico-launcher) / [pico-loader](https://github.com/LNH-team/pico-loader) / [dspico-firmware](https://github.com/LNH-team/dspico-firmware).

1. **Estado** — checklist do microSD (`_picoboot.nds`, `_pico/`, `Games/`, bios/emunand, emuladores).
2. **Preparar SD** — baixa e escreve **Pico Launcher** + **Pico Loader DSPICO** oficiais (SHA-256 pinado; só `github.com/LNH-team/`).
3. **Jogos** — importar/remover ROMs em `Games/`; **Organizar pastas** limpa outros sistemas e coloca os jogos por franquia, plataforma, soltos em `Games/` ou na raiz ao lado do launcher (preserva `/ROMs/`, `_gba/`, `Emulators/`, `data/` dos emuladores). Clique em um jogo para **capa/ícone** Pico Launcher (pesquisa SteamGridDB + GameTDB + Libretro, opções semelhantes, arquivo manual → BMP em `/_pico/covers/` e `/_pico/icons/`).
4. **Emuladores** — seleccionar e instalar emuladores do guia [Pico-Launcher](https://sanrax.github.io/flashcart-guides/tutorials/emulators-pico/) (GBARunner, GameYob, nesDS, Atari, Sega, etc.): NDS em `/_pico/emulators/` (ou `/Emulators/` se só manual), pastas `/ROMs/…` e `fileAssociations` no `settings.json`. BIOS proprietária **não** é baixada.
5. **Emunand** — pastas oficiais + importar o *seu* `biosnds7.rom` / `TWLFontTable.dat` (sem download de BIOS).
6. **Configurações** — editar `/_pico/settings.json` (chaves documentadas no Usage do Launcher).
7. **Firmware** — detectar volume `RPI-RP2` e gravar `.uf2` **apenas** se existir asset pinado em [dspico-firmware](https://github.com/LNH-team/dspico-firmware/releases). Enquanto as releases LNH não publicarem o UF2, o botão fica desativado (o GUIDE oficial manda compilar); builds de terceiros não são aceites.

## Navegação

O app abre como o menu inicial de um console: barra de status em cima (marca, seletor do microSD, progresso, hora e medidor de espaço), o Início com doze blocos (seis do DSPico, cinco de Mais ferramentas e Configurações), uma barra de ícones embaixo (Início, Atividade, Tema, Configurações) e uma barra de dicas. Cada bloco abre uma tela com o botão Voltar; dentro dela, as telas irmãs aparecem como abas com ícone. Pelo teclado, as setas movem a seleção no Início, Enter abre, Esc ou Backspace voltam, setas mudam de aba e Alt+1 a Alt+4 levam a Início, DSPico, Mais ferramentas e Configurações. A gaveta Atividade abre sozinha durante operações. Cada um dos sete temas arruma o Início à sua maneira (duas telas, fileira com balão, grade de canais, grade de vidro, painéis em lista, bandeja ou fileira com doca).

| Vista | Abas |
|------|-----------|
| **DSPico** | Cartão (estado, atualizações, preparar SD) · Jogos · RouteDex · Launcher (`settings.json`, temas, fundos noturnos) · Emuladores e apps · Avançado (emunand, firmware) |
| **Mais ferramentas** | Softmod DSi (assistente e passos manuais: Passo 1, Passo 2, hiyaCFW, extras) · Flashcards R4/GEi · Biblioteca TWiLight (`/roms/`, organizar, cheats, capas) · Apps homebrew · Manutenção do cartão (relatório, backup, limpeza, formatação) |

Use o Assistente se ainda não tiver o hábito do fluxo completo; os passos manuais não “seguram a mão” nas etapas críticas da mesma forma.

---

## Perguntas frequentes

**O cartão não aparece na lista.**  
Só entram unidades removíveis (SD / USB). Remonte o cartão, troque de leitor se precisar e clique em atualizar.

**A Câmera não dispara o exploit.**  
Confirme Com/Sem Facebook no Assistente; formate em FAT32; fotos antigas em `DCIM` podem atrapalhar — use a quarentena de fotos do app quando sugerida.

**O flashcard não inicia.**  
Confirme marca/kernel (GEi vs clone R4). Formate FAT32 com cluster 32 KB e reinstale o kernel pelo app.

**Posso fechar o app a meio de uma gravação?**  
Não. Aguarde o fim da operação. O app tenta bloquear o fechamento se houver escrita em curso.

---

## Temas

No cabeçalho (ícone de paleta):

- **Studio** — Escuro (padrão), Claro, Automático (segue o sistema)
- **Catppuccin** — Latte, Frappé, Macchiato, Mocha
- **Dracula**
- **Retro** — Game Boy · DS Lite

A escolha fica salva no computador entre sessões.

---

## Aviso legal / Termos de uso

Este software é oferecido **“como está” (AS IS)**, **sem garantias** de qualquer tipo — expressas ou implícitas — incluindo, sem limitação, comercialização, adequação a um fim específico e não violação. Na máxima extensão permitida pela lei aplicável, os autores e contribuidores **não respondem** por danos diretos, indiretos, incidentais, especiais, consequenciais ou punitivos (perda de dados, dano a hardware, impossibilidade de uso do console, etc.) decorrentes do uso ou da impossibilidade de uso do Route Pico.

Ao usar o app, você assume **toda a responsabilidade** pelas operações no cartão SD e pelas ações subsequentes no console (incluindo instalação de Unlaunch ou outro software).

### Risco de brick e papel do app

- O Route Pico **prepara arquivos no cartão SD**. **Não grava na NAND** do Nintendo DSi por si só.
- O **Unlaunch** (e fluxos semelhantes), quando executados **no console**, **escrevem na NAND**. Há um **risco real, ainda que pequeno, de brick**. Só avance se tiver **backup da NAND** e compreender o guia oficial ([dsi.cfw.guide](https://dsi.cfw.guide/)).
- Binários incorretos, incompletos ou de origem não verificada no cartão podem causar falhas graves se forem instalados via Unlaunch ou outros instaladores.
- A UI do Assistente reforça estes avisos nas etapas críticas; leia-os antes de continuar.

### Afiliação e marcas

O Route Pico **não é afiliado, endossado ou patrocinado** pela Nintendo Co., Ltd. nem pelas respetivas subsidiárias. **Nintendo**, **DSi** e demais marcas relacionadas são propriedade dos seus titulares. Nomes de flashcards (GEi, AceKard, R4, etc.) e de projetos homebrew são usados apenas para identificação; pertencem aos respetivos donos.

### Licença do código deste repositório

O **código-fonte do Route Pico** (Python, HTML/CSS/JS da UI embutida, scripts e documentação deste repositório, salvo indicação em contrário) está licenciado sob a **GNU General Public License versão 3** — ver [`LICENSE`](LICENSE).

### Componentes baixados (terceiros)

Durante o uso, o app pode **baixar** binários e arquivos de projetos upstream (por exemplo Memory Pit e dumpTool via [dsi.cfw.guide](https://dsi.cfw.guide/), Unlaunch Installer, TWiLight Menu++, e apps do catálogo Homebrew com releases no GitHub). Esses componentes:

- mantêm as **licenças, autores e termos dos projetos originais**;
- **não** são “relicenciados” sob a GPL-3.0 do Route Pico só por serem baixados ou copiados para o SD;
- são obtidos de URLs documentadas em `core/cache.py`, com verificação **SHA-256 pinada** (integridade, não uma garantia de isenção de risco).

Respeite as licenças e créditos de cada projeto ao redistribuir ou modificar esses arquivos fora do fluxo do app.

### ROMs, dumps e conteúdo no cartão

O organizador de ROMs **não fornece** jogos, ROMs nem dumps protegidos por direitos de autor. Apenas reorganiza arquivos que **você** coloca no cartão. É **sua responsabilidade** garantir que possui o direito legal de possuir e usar esse conteúdo na sua jurisdição.

### Formatação e unidades

A formatação **FAT32** **apaga todos os dados** do volume selecionado. O app tenta restringir operações a volumes **removíveis / USB / SD** reconhecidos; ainda assim, confirme sempre a unidade correta. Erros de seleção ou limitações do sistema operativo podem ter consequências graves.

### Segurança

Para reportar vulnerabilidades, consulte [`SECURITY.md`](SECURITY.md).

---

## Documentação técnica

Secção destinada a desenvolvedores, mantenedores e usuários avançados. Linguagem e detalhe orientados à manutenção do código. Para o fluxo de produto e agentes de IA, ver também [`AGENTS.md`](AGENTS.md) e `.cursor/rules/`.

### Arquitetura (visão geral)

| Camada | Papel |
|--------|--------|
| **Shell** | Python 3.10+ + pywebview (janela nativa; sem servidor HTTP) |
| **UI** | `static/` — HTML/CSS/JS offline (Tailwind local); menu de console (barra de status, Início em blocos, barra de ícones e dicas) |
| **Bridge** | `Api` em `app.py` (`js_api`) + `services/FilePickerPort` / `web_events` |
| **Core** | Módulos em `core/` (discos, exploits, TWiLight, ROMs, cache, sdio, validate, …) |

Escritas no SD: `_run_mount_op` + `OP_LOCK` (`blocking=False`); o **preflight** roda **dentro** do lock. Fechamento da janela: se `OP_LOCK.locked()`, o close é bloqueado.

Respostas tipicamente `{success: bool, error?: str, ...}` com redação de paths (`core.privacy`).

### Mapa do repositório

| Caminho | Papel |
|---------|--------|
| `app.py` | Entrada pywebview, `Api`, `OP_LOCK` / logs, preflight + ops de montagem |
| `services/` | FilePickerPort, wizard_flow, web_events |
| `static/` | Interface HTML/CSS/JS |
| `core/disks.py` | Listagem e formatação de volumes removíveis |
| `core/sdio.py` | Pré-voo de escrita, `copy_verified`, sync, `UndoStack` |
| `core/exploits.py` | Passo 1 (Memory Pit + dumpTool) e Passo 2 (Unlaunch) |
| `core/twilight.py` | TWiLight Menu++, kernels GEi / R4 |
| `core/rom_cleaner.py` | Organização de ROMs / saves |
| `core/artwork.py` | Capas/ícones: SteamGridDB (principal) → GameTDB (NDS) + Libretro Thumbnails |
| `core/steamgriddb.py` | Cliente SteamGridDB (chave em Configurações / env `STEAMGRIDDB_API_KEY`) |
| `core/boxart.py` | Compat: reexporta `core.artwork` |
| `core/sd_utils.py` | Homebrew do catálogo, cheats, relatório de cluster, cópia de `nand.bin` |
| `core/cleaner.py` | Backup do SD, limpeza de metadados macOS |
| `core/cache.py` | Downloads oficiais + **SHA-256 pinados** (`DSPICO_CACHE_KEYS`) |
| `core/dspico.py` | DSPico: pacote LNH, `Games/`, emunand, settings, flash RPI-RP2 |
| `core/pico_artwork.py` | Capas/ícones Pico Launcher (pesquisa + BMP) |
| `core/dspico_emulators.py` | Emuladores Pico-Launcher (`/_pico/emulators/`, `/ROMs/`, `fileAssociations`) |
| `core/homebrew_catalog.py` | Catálogo de apps instaláveis (releases GitHub) |
| `core/validate.py` | Validação NDS / integridade |
| `core/inspect_sd.py` | Inspeção do cartão (wizard), sob `OP_LOCK` |
| `core/privacy.py` | Redação de paths / PII em logs e respostas |
| `packaging/` | Spec PyInstaller + Inno Setup (Windows) |
| `tools/build_*_release.sh` | Empacotar portátil / instalável por SO |
| `tests/` | pytest |
| `tools/update_pins.py` | Verificar / atualizar pins SHA-256 |
| `tools/build_icons.py` | Regenerar ícones a partir dos SVGs |

### Segurança e integridade (implementação)

- Downloads oficiais com **SHA-256 pinado** (Memory Pit, dumpTool, Unlaunch, TWiLight Menu++, e apps do catálogo Homebrew).
- Cópia para o cartão com verificação (`fsync` + rehash); promote atómico via `.partial` + `os.replace`.
- Validação de cabeçalho NDS (CRC) antes de gravar bootloaders.
- Etapas 1/2 (e kernels) transacionais com `UndoStack` + sync após rollback.
- Formatação só em volumes removíveis/USB/SD reconhecidos (`is_safe_mount_path`).
- UI offline (sem CDN); sem telemetria remota.

Atualizar pins após release upstream:

```bash
python tools/update_pins.py --check
# Se divergir, atualize PINNED_SHA256 e URLS em core/cache.py com evidência do digest oficial.
```

### Requisitos

- Python 3.10+
- Dependências pinadas: `pywebview==6.2.1`, `py7zr==1.1.3` (ver `requirements.txt` / `requirements.lock.txt`)
- UI offline em `static/`

| SO | Notas |
|----|--------|
| **macOS** | `diskutil` / `dot_clean`; lista apenas volumes USB/SD removíveis |
| **Windows** | Formatação FAT32 pode exigir Administrador; HD interno (C:) nunca é listado |
| **Linux** | Formatação via `mkfs.vfat` (`dosfstools`); pode precisar de permissões elevadas |

### Instalação a partir do código-fonte

```bash
git clone https://github.com/GoobinEXE/Route1.git
cd Route1
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade "pip>=26.2"
pip install --require-hashes -r requirements.lock.txt
# desenvolvimento / testes:
pip install -r requirements-dev.txt
```

Os scripts `start.command` / `start.bat` / `start.sh` automatizam venv + pip com hashes.

### Testes e smoke

```bash
pytest -q
```

Antes de uma release, siga o checklist em [`docs/SMOKE_TEST.md`](docs/SMOKE_TEST.md).

### Empacotar (portátil + instalável)

Requer PyInstaller (`pip install "pyinstaller>=6.11,<7"`) fora do lock com hashes — só no ambiente de build.

```bash
# macOS → ZIP portátil + DMG
./tools/build_macos_release.sh

# Linux → tar.gz portátil + tar.gz com atalho
./tools/build_linux_release.sh

# Windows (Git Bash / CI) → ZIP + setup.exe (Inno Setup 6)
./tools/build_windows_release.sh
# Fases no CI: ROUTE1KIT_WIN_PHASE=build|package — ver docs/WINDOWS_SIGNING.md
```

Tags `v*` disparam o workflow [`.github/workflows/release.yml`](.github/workflows/release.yml), que publica os artefatos na Release do GitHub. Assinatura Authenticode Windows (publisher **Dark Room**) activa-se quando os secrets/vars Azure estiverem configurados — guia em [`docs/WINDOWS_SIGNING.md`](docs/WINDOWS_SIGNING.md).

### Assets e identidade visual (manutenção)

O símbolo é uma **placa de rota** com o número **1**, silhueta de cartão SD e estrada ao horizonte. Gradiente da marca: `#4F72F8 → #6A47EC`. Tipografia embutida: **Sora** (UI) e **IBM Plex Mono** (paths / logs).

| Arquivo | Uso |
|----------|-----|
| `static/assets/logo.svg` | Marca completa |
| `static/assets/logo-small.svg` | Favicon / 16–48 px |
| `static/assets/app-icon*.png` | 1024 / 512 / 256 / 128 px |
| `static/assets/app-icon.icns` / `.ico` | Ícone macOS / Windows |

```bash
# Regenerar rasters após editar SVGs (requer Chrome/Chromium)
python tools/build_icons.py
```

Temas do app: sete temas inspirados em menus de consoles (Dupla Tela é o padrão), cada um com paleta Original e modos Claro (Catppuccin Latte) e Noturno (Catppuccin Mocha); escolhem-se no botão de tema da barra de cima ou em Configurações. As paletas vivem em `tools/build_themes.py` (gera `static/themes.css` e `static/theme-data.js`, com contraste AA verificado) e a assinatura visual de cada tema em `static/skins.css`. Temas Pico Launcher: `/_pico/themes/` em DSPico → Launcher.

### Invariantes (não negociáveis)

Resumo — detalhe em [`AGENTS.md`](AGENTS.md) e `.cursor/rules/`:

1. Subprocess de disco com `timeout=`; libertar `OP_LOCK` em `finally`.
2. Preflight / escrita no SD só sob `OP_LOCK`; `inspect_sd` idem.
3. Inputs da UI tipados (`_as_path_str`, `_as_bool`); revalidar montagem antes de ops destrutivas.
4. `copy_verified`: hash do `.partial` **antes** do `os.replace`.
5. Sem home absoluto em logs; `redact_path` / `redact_text`.
6. JS: `setBusy` + `finally`; wizard com `renderGen` após `await`.
