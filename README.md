# Route 1 Kit

Licensed under the GNU General Public License v3.0 — see [`LICENSE`](LICENSE).

**Route 1 Kit** é um aplicativo desktop para **macOS, Windows e Linux** que prepara cartões SD para o **Nintendo DSi** e para flashcards (**GEi / AceKard / R4**).

A interface abre numa **janela nativa** (via [pywebview](https://pywebview.flowrl.com/)) — sem navegador externo e sem servidor HTTP. Tudo o que precisa para usar o app fica offline na pasta do projeto.

> A pasta ou o repositório podem ainda chamar-se `DSi-SD-Studio`; o nome do produto é **Route 1 Kit**.

---

## Descarregar (release 1.0.2)

Builds oficiais: [Releases no GitHub](https://github.com/GoobinEXE/Route1/releases).

| Plataforma | Portátil | Instalável |
|------------|----------|------------|
| **macOS** | ZIP com `Route 1 Kit.app` | DMG (arraste para Aplicações) |
| **Windows** | ZIP com a pasta do app | `setup.exe` (Inno Setup) |
| **Linux** | `.tar.gz` onedir | `.tar.gz` com script de atalho `.desktop` |

Na primeira abertura no macOS/Windows, o sistema pode pedir confirmação de segurança (binário ainda não notarizado pela Apple / SmartScreen sem Authenticode). Prefira sempre descarregar da página de Releases deste repositório. Builds Windows oficiais passam a ser assinados como **Dark Room** quando o Azure Artifact Signing estiver configurado ([guia](docs/WINDOWS_SIGNING.md)).

Se preferir correr a partir do código-fonte, use a secção [Como abrir o aplicativo](#como-abrir-o-aplicativo) abaixo.

---

## Para quem é este app?

- Você quer **desbloquear o DSi** (SD-direct com TWiLight Menu++ e Unlaunch) sem montar pastas à mão.
- Você quer **criar ou atualizar** o MicroSD de um flashcard GEi ou R4.
- Você já tem jogos no cartão e quer **organizar ROMs e saves**, instalar capas, cheats ou utilitários — com menos risco de apagar o volume errado.

Se é a primeira vez: comece pelo **Assistente**. O **Modo avançado** fica para quem já conhece o fluxo.

---

## O que você precisa

1. **Console** — Nintendo DSi / DSi XL (slot lateral) e/ou um DS/DSi com flashcard Slot-1.
2. **Cartão SD / MicroSD** — de preferência um cartão de **teste** na primeira utilização. Tamanhos comuns: 2–32 GB (FAT32).
3. **Leitor de cartão** ligado ao computador.
4. **Computador** com macOS, Windows ou Linux e ligação à internet **só** para o app descarregar os binários oficiais na primeira vez (depois ficam em cache local).

### Aviso importante (leia antes de gravar no console)

O Route 1 Kit **prepara ficheiros no cartão SD**. **Não grava na NAND** do DSi por si só.

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

Ao abrir, o Route 1 Kit começa no **Assistente**. Escolha o objetivo que corresponde ao que pretende fazer.

A preferência Assistente / Avançado vale **só nesta sessão**. Se fechar a meio do guia, na próxima abertura volta ao início do Assistente.

### 1. Instalar SD-direct (desbloqueio pelo slot lateral)

Para jogar pelo cartão SD do **lado do DSi**, sem flashcard:

1. Confirme que o console é um **DSi / DSi XL**.
2. Indique se a **Câmera Nintendo DSi** tem o ícone do **Facebook** ou não (define a versão correta do Memory Pit).
3. Selecione o cartão do **slot lateral** (não o MicroSD de um flashcard).
4. O app prepara o **Passo 1** (Memory Pit + dumpTool como `boot.nds`).
5. No DSi, abra a Câmera, aceda ao cartão SD e siga o **dumpTool** para criar o `nand.bin`.
6. Volte o cartão ao PC: o app valida o backup e guarda uma cópia no computador.
7. O app prepara o **Passo 2** (TWiLight Menu++ + instalador seguro do Unlaunch).
8. No DSi, execute o instalador do Unlaunch e configure o arranque (conforme o guia oficial).
9. Se quiser, organize jogos e finalize.

### 2. Atualizar SD-direct

Para um cartão que **já** tem TWiLight / softmod: o Assistente atualiza os componentes oficiais (com verificação SHA-256), preservando jogos e saves quando possível.

### 3. Criar flashcard do zero

Para um MicroSD novo (ou a limpar) no cartucho Slot-1:

1. Escolha a marca: **Galaxy Eagle i (GEi)** ou **R4**.
2. Formate em FAT32 se for preciso (o app usa cluster adequado; a formatação **apaga tudo**).
3. Instale o kernel e a estrutura de pastas.

Clones “R4” são muitos: o kernel tem de ser o **do seu** modelo. Kernel errado = cartucho não inicia.

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

## Modo avançado (visão geral)

No cabeçalho, **Modo avançado** abre o painel clássico, com secções **Preparar**, **Cartão** e **Apps**:

| Área | O que faz |
|------|-----------|
| **Preparar** | Passo 1 (Memory Pit + dumpTool), Passo 2 (TWiLight + Unlaunch), kernel GEi |
| **Cartão** | Organizar ROMs, cheats, boxarts, relatório, backup, limpeza, formatação, DCIM, cópia NAND |
| **Apps** | Catálogo homebrew: download + SHA-256, guias GameBrew, links Universal-DB, instalação em `/roms/apps/` |

Use o Assistente se ainda não tiver o hábito do fluxo completo; o modo avançado não “segura a mão” nas etapas críticas da mesma forma.

---

## Perguntas frequentes

**O cartão não aparece na lista.**  
Só entram unidades removíveis (SD / USB). Remonte o cartão, troque de leitor se precisar e clique em atualizar.

**A Câmera não dispara o exploit.**  
Confirme Com/Sem Facebook no Assistente; formate em FAT32; fotos antigas em `DCIM` podem atrapalhar — use a quarentena de fotos do app quando sugerida.

**O flashcard não arranca.**  
Confirme marca/kernel (GEi vs clone R4). Formate FAT32 com cluster 32 KB e reinstale o kernel pelo app.

**Posso fechar o app a meio de uma gravação?**  
Não. Aguarde o fim da operação. O app tenta bloquear o fecho se houver escrita em curso.

---

## Temas

No cabeçalho (ícone de paleta):

- **Studio** — Escuro (padrão), Claro, Automático (segue o sistema)
- **Catppuccin** — Latte, Frappé, Macchiato, Mocha
- **Dracula**
- **Retro** — Game Boy · DS Lite

A escolha fica guardada no computador entre sessões.

---

## Aviso legal / Termos de uso

Este software é oferecido **“como está” (AS IS)**, **sem garantias** de qualquer tipo — expressas ou implícitas — incluindo, sem limitação, comercialização, adequação a um fim específico e não violação. Na máxima extensão permitida pela lei aplicável, os autores e contribuidores **não respondem** por danos diretos, indiretos, incidentais, especiais, consequenciais ou punitivos (perda de dados, dano a hardware, impossibilidade de uso do console, etc.) decorrentes do uso ou da impossibilidade de uso do Route 1 Kit.

Ao usar o app, você assume **toda a responsabilidade** pelas operações no cartão SD e pelas ações subsequentes na consola (incluindo instalação de Unlaunch ou outro software).

### Risco de brick e papel do app

- O Route 1 Kit **prepara ficheiros no cartão SD**. **Não grava na NAND** do Nintendo DSi por si só.
- O **Unlaunch** (e fluxos semelhantes), quando executados **na consola**, **escrevem na NAND**. Há um **risco real, ainda que pequeno, de brick**. Só avance se tiver **backup da NAND** e compreender o guia oficial ([dsi.cfw.guide](https://dsi.cfw.guide/)).
- Binários incorretos, incompletos ou de origem não verificada no cartão podem causar falhas graves se forem instalados via Unlaunch ou outros instaladores.
- A UI do Assistente reforça estes avisos nas etapas críticas; leia-os antes de continuar.

### Afiliação e marcas

O Route 1 Kit **não é afiliado, endossado ou patrocinado** pela Nintendo Co., Ltd. nem pelas respetivas subsidiárias. **Nintendo**, **DSi** e demais marcas relacionadas são propriedade dos seus titulares. Nomes de flashcards (GEi, AceKard, R4, etc.) e de projetos homebrew são usados apenas para identificação; pertencem aos respetivos donos.

### Licença do código deste repositório

O **código-fonte do Route 1 Kit** (Python, HTML/CSS/JS da UI embutida, scripts e documentação deste repositório, salvo indicação em contrário) está licenciado sob a **GNU General Public License versão 3** — ver [`LICENSE`](LICENSE).

### Componentes descarregados (terceiros)

Durante o uso, o app pode **descarregar** binários e arquivos de projetos upstream (por exemplo Memory Pit e dumpTool via [dsi.cfw.guide](https://dsi.cfw.guide/), Unlaunch Installer, TWiLight Menu++, e apps do catálogo Homebrew com releases no GitHub). Esses componentes:

- mantêm as **licenças, autores e termos dos projetos originais**;
- **não** são “relicenciados” sob a GPL-3.0 do Route 1 Kit só por serem descarregados ou copiados para o SD;
- são obtidos de URLs documentadas em `core/cache.py`, com verificação **SHA-256 pinada** (integridade, não uma garantia de isenção de risco).

Respeite as licenças e créditos de cada projeto ao redistribuir ou modificar esses ficheiros fora do fluxo do app.

### ROMs, dumps e conteúdo no cartão

O organizador de ROMs **não fornece** jogos, ROMs nem dumps protegidos por direitos de autor. Apenas reorganiza ficheiros que **você** coloca no cartão. É **sua responsabilidade** garantir que possui o direito legal de possuir e usar esse conteúdo na sua jurisdição.

### Formatação e unidades

A formatação **FAT32** **apaga todos os dados** do volume selecionado. O app tenta restringir operações a volumes **removíveis / USB / SD** reconhecidos; ainda assim, confirme sempre a unidade correta. Erros de seleção ou limitações do sistema operativo podem ter consequências graves.

### Segurança

Para reportar vulnerabilidades, consulte [`SECURITY.md`](SECURITY.md).

---

## Documentação técnica

Secção destinada a desenvolvedores, mantenedores e utilizadores avançados. Linguagem e detalhe orientados à manutenção do código. Para o fluxo de produto e agentes de IA, ver também [`AGENTS.md`](AGENTS.md) e `.cursor/rules/`.

### Arquitetura (visão geral)

| Camada | Papel |
|--------|--------|
| **Shell** | Python 3.9+ + pywebview (janela nativa; sem HTTP server) |
| **UI** | `static/` — HTML/CSS/JS offline; Tailwind compilado localmente; fontes embutidas |
| **Bridge** | Classe `Api` em `app.py` exposta ao JS via `js_api` (JSON) |
| **Core** | Módulos em `core/` (discos, exploits, TWiLight, ROMs, cache, sdio, validate, …) |

Cada chamada `js_api` corre numa **thread não-daemon**. Escritas no SD passam por `_run_mount_op` + `OP_LOCK` (`blocking=False`); o **preflight** corre **dentro** do lock. Fecho da janela: se `OP_LOCK.locked()`, o close é bloqueado.

Respostas tipicamente `{success: bool, error?: str, ...}` com redação de paths (`core.privacy`).

### Mapa do repositório

| Caminho | Papel |
|---------|--------|
| `app.py` | Entrada, `Api`, `OP_LOCK` / logs, preflight + ops de montagem |
| `core/disks.py` | Listagem e formatação de volumes removíveis |
| `core/sdio.py` | Pré-voo de escrita, `copy_verified`, sync, `UndoStack` |
| `core/exploits.py` | Passo 1 (Memory Pit + dumpTool) e Passo 2 (Unlaunch) |
| `core/twilight.py` | TWiLight Menu++, kernels GEi / R4 |
| `core/rom_cleaner.py` | Organização de ROMs / saves |
| `core/boxart.py` | Capas GameTDB por Game Code / região |
| `core/sd_utils.py` | Homebrew do catálogo, cheats, relatório de cluster, cópia de `nand.bin` |
| `core/cleaner.py` | Backup do SD, limpeza de metadados macOS |
| `core/cache.py` | Downloads oficiais + **SHA-256 pinados** |
| `core/homebrew_catalog.py` | Catálogo de apps instaláveis (releases GitHub) |
| `core/validate.py` | Validação NDS / integridade |
| `core/inspect_sd.py` | Inspeção do cartão (wizard), sob `OP_LOCK` |
| `core/privacy.py` | Redação de paths / PII em logs e respostas |
| `static/app.js` | Modo avançado, poll de logs, `runMountOp` / `busy` |
| `static/wizard.js` | Assistente (`renderGen`) |
| `static/theme.js` + `themes.css` | Temas (tokens `--c-*`) |
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
- UI offline (sem CDN); CSP restritiva; sem telemetria remota.

Atualizar pins após release upstream:

```bash
python tools/update_pins.py --check
# Se divergir, atualize PINNED_SHA256 e URLS em core/cache.py com evidência do digest oficial.
```

### Requisitos

- Python 3.9+
- Dependências pinadas: `pywebview==6.2.1`, `py7zr==1.1.3` (ver `requirements.txt` / `requirements.lock.txt`)
- UI 100% offline (Tailwind e fontes em `static/`)

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

Tags `v*` disparam o workflow [`.github/workflows/release.yml`](.github/workflows/release.yml), que publica os artefactos na Release do GitHub. Assinatura Authenticode Windows (publisher **Dark Room**) activa-se quando os secrets/vars Azure estiverem configurados — guia em [`docs/WINDOWS_SIGNING.md`](docs/WINDOWS_SIGNING.md).

### Assets e identidade visual (manutenção)

O símbolo é uma **placa de rota** com o número **1**, silhueta de cartão SD e estrada ao horizonte. Gradiente da marca: `#4F72F8 → #6A47EC`. Tipografia embutida: **Sora** (UI) e **IBM Plex Mono** (paths / logs).

| Ficheiro | Uso |
|----------|-----|
| `static/assets/logo.svg` | Marca completa |
| `static/assets/logo-small.svg` | Favicon / 16–48 px |
| `static/assets/app-icon*.png` | 1024 / 512 / 256 / 128 px |
| `static/assets/favicon*.png` | 64 / 32 / 16 px |
| `static/assets/app-icon.icns` / `.ico` | Ícone macOS / Windows |

```bash
# Regenerar rasters após editar SVGs (requer Chrome/Chromium)
python tools/build_icons.py

# Regenerar CSS Tailwind após alterar classes na UI
npx --yes tailwindcss@3.4.17 -i ./static/tailwind.input.css -o ./static/tailwind.css --minify
```

Temas: tokens semânticos em `static/themes.css` (`--c-bg`, `--c-surface`, …); `style.css` / Tailwind consomem só esses tokens. Preferência: `localStorage` (`route_1_kit_theme`), aplicada antes do primeiro paint por `static/theme.js`. Novo tema = bloco `html[data-theme="…"]` + entrada em `THEMES` no `theme.js`.

### Invariantes (não negociáveis)

Resumo — detalhe em [`AGENTS.md`](AGENTS.md) e `.cursor/rules/`:

1. Subprocess de disco com `timeout=`; libertar `OP_LOCK` em `finally`.
2. Preflight / escrita no SD só sob `OP_LOCK`; `inspect_sd` idem.
3. Inputs da UI tipados (`_as_path_str`, `_as_bool`); revalidar montagem antes de ops destrutivas.
4. `copy_verified`: hash do `.partial` **antes** do `os.replace`.
5. Sem home absoluto em logs; `redact_path` / `redact_text`.
6. JS: `setBusy` + `finally`; wizard com `renderGen` após `await`.
