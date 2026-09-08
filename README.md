# Route 1 Kit

Licensed under the GNU General Public License v3.0 — see [`LICENSE`](LICENSE).

**Route 1 Kit** é um app desktop multiplataforma (macOS, Windows e Linux) para automatizar e gerenciar a preparação de cartões SD para o **Nintendo DSi** e flashcards (como o **GEi / AceKard / R4**).

A interface abre em uma **janela nativa** via [pywebview](https://pywebview.flowrl.com/) — sem navegador e sem servidor HTTP.

> O diretório local ou o repositório podem ainda chamar-se `DSi-SD-Studio`; o nome do produto é **Route 1 Kit**.

---

## Recursos principais

1. **Assistente passo a passo:** guia para iniciantes (atualizar/criar flashcard R4 ou GEi; instalar ou atualizar SD-direct com TWiLight + Unlaunch).
2. **Modo avançado:** atalhos do painel clássico (Passo 1/2, ROMs, GEi, utilitários).
3. **Detecção de cartões SD:** lista unidades externas montadas (capacidade, formato e espaço livre).
4. **Passo 1 — Exploit & backup da NAND:** Memory Pit + dumpTool como `boot.nds`.
5. **Passo 2 — TWiLight Menu++ & Unlaunch:** prepara o menu e o Safe Unlaunch Installer.
6. **Organizador de ROMs:** limpa nomes, sincroniza saves e separa por plataforma em `/roms/<nds|dsi|gba|…>/`.
7. **Flashcard GEi / R4:** instala kernel Galaxy Eagle i ou copia kernel R4 a partir de Downloads.
8. **Utilitários:** backup do SD, limpeza de metadados e formatação FAT32.

### Assistente vs Avançado

- O app abre no **Assistente** (escolha o objetivo → etapas no PC e no DSi, com bloqueios para evitar saltar o dump da NAND ou formatar o cartão errado).
- O **Modo avançado** mantém o dashboard de ações livres para quem já conhece o fluxo.
- A preferência Assistente/Avançado fica só na sessão (`sessionStorage`); fechar a meio do assistente volta ao início do guia.

---

## Segurança e integridade

- Downloads oficiais com **SHA-256 pinado** (Memory Pit, dumpTool, Unlaunch v2.6, TWiLight Menu++ v27.24.1).
- Cópia para o cartão com verificação pós-gravação (`fsync` + rehash).
- Validação de cabeçalho NDS (CRC) antes de gravar bootloaders.
- Etapas 1/2 transacionais com rollback se algo falhar.
- Formatação só em volumes removíveis/USB/SD reconhecidos.
- UI offline (sem CDN); CSP restritiva.

Para atualizar pins após uma nova release upstream:

```bash
python tools/update_pins.py --check
# Se divergir, atualize PINNED_SHA256 e URLS em core/cache.py com evidência do digest da API GitHub.
```

---

## Requisitos

- Python 3.9+
- Dependências pinadas: `pywebview==6.2.1`, `py7zr==1.1.3` (veja `requirements.txt` / `requirements.lock.txt`)
- UI 100% offline (Tailwind e fontes embutidos em `static/`)

### Extras por sistema

| SO | Notas |
|----|--------|
| **macOS** | Usa `diskutil` / `dot_clean`; lista apenas volumes USB/SD removíveis |
| **Windows** | Formatação FAT32 pode exigir Administrador; HD interno (C:) nunca é listado |
| **Linux** | Formatação usa `mkfs.vfat` (`dosfstools`); pode precisar de permissões elevadas |

Para regenerar o CSS Tailwind após alterar classes na UI:

```bash
npx --yes tailwindcss@3.4.17 -i ./static/tailwind.input.css -o ./static/tailwind.css --minify
```

---

## Identidade visual e temas

### Marca

O símbolo é uma **placa de rota** com o número **1** — a Rota 1, onde toda jornada começa — fincada num poste à beira de uma **estrada** que segue para o horizonte. A placa tem a **silhueta de um cartão SD** (chanfro no canto), ligando o nome ao que o app faz. O "1" é desenhado como path (sem depender de fontes) e a variante compacta (`logo-small.svg`) remove a estrada para ficar legível em 16 px. Gradiente da marca: `#4F72F8 → #6A47EC` (índigo → violeta). Tipografia: **Sora** (interface) e **IBM Plex Mono** (caminhos, logs, códigos), ambas embutidas offline.

| Ficheiro | Uso |
|----------|-----|
| `static/assets/logo.svg` | Marca completa (header, ícones ≥ 64 px) |
| `static/assets/logo-small.svg` | Variante compacta para favicon / 16–48 px |
| `static/assets/app-icon*.png` | 1024 / 512 / 256 / 128 px |
| `static/assets/favicon*.png` | 64 / 32 / 16 px |
| `static/assets/app-icon.icns` / `.ico` | Ícone de app macOS / Windows |

Para regerar os rasters após editar os SVGs (requer Chrome/Chromium):

```bash
python tools/build_icons.py
```

### Temas

O tema padrão é o **Studio Escuro**. O seletor no header (ícone de paleta) alterna entre:

- **Studio:** Escuro (padrão) · Claro · Automático (segue o sistema)
- **Catppuccin:** Latte · Frappé · Macchiato · Mocha
- **Dracula**
- **Retro:** Game Boy · DS Lite — painéis com a paleta LCD do Game Boy DMG (`#9BBC0F / #8BAC0F / #306230 / #0F380F`), grade de pixels e moldura preta; fundo, header e botões em pílula com a carcaça branca brilhante do DS Lite; estados com as cores dos LEDs (verde, laranja, vermelho). A "pele" (gradientes/moldura) fica na seção `skin: Game Boy · DS Lite` de `style.css`.

A preferência fica em `localStorage` (`route_1_kit_theme`) e é aplicada antes do primeiro paint por `static/theme.js`. As paletas vivem em `static/themes.css` como tokens semânticos (`--c-bg`, `--c-surface`, `--c-fg`, `--c-accent`, `--c-ok`, …); `style.css` e o Tailwind (`bg-surface`, `text-fg-mute`, `bg-accent/10`, …) consomem só esses tokens, portanto um tema novo é apenas um bloco `html[data-theme="…"]` em `themes.css` mais uma entrada em `THEMES` no `theme.js`.

---

## Instalação

```bash
cd /caminho/para/Route-1-Kit
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install --upgrade "pip>=26.2"
pip install --require-hashes -r requirements.lock.txt
# desenvolvimento / testes:
pip install -r requirements-dev.txt
```

Os scripts `start.command` / `start.bat` / `start.sh` criam o `.venv`, atualizam o pip e instalam com hashes automaticamente.

---

## Como iniciar

### macOS — dois cliques
Abra a pasta no Finder e dê dois cliques em `start.command`.

### Windows — dois cliques
Execute `start.bat`.

### Linux
No terminal, a partir da pasta do projeto:

```bash
chmod +x start.sh   # só na primeira vez
./start.sh
```

### Terminal (qualquer SO)

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python app.py
```

### Testes

```bash
pytest -q
```

Antes de uma release futura, siga o checklist em [`docs/SMOKE_TEST.md`](docs/SMOKE_TEST.md).

A janela do app abre automaticamente. Feche a janela para encerrar.

Use sempre um **cartão SD de teste** na primeira utilização. Detalhes de risco e responsabilidade estão em [Aviso legal / Termos de uso](#aviso-legal--termos-de-uso).

---

## Aviso legal / Termos de uso

Este software é oferecido **“como está” (AS IS)**, **sem garantias** de qualquer tipo — expressas ou implícitas — incluindo, sem limitação, comercialização, adequação a um fim específico e não violação. Na máxima extensão permitida pela lei aplicável, os autores e contribuidores **não respondem** por danos diretos, indiretos, incidentais, especiais, consequenciais ou punitivos (perda de dados, dano a hardware, impossibilidade de uso do console, etc.) decorrentes do uso ou da impossibilidade de uso do Route 1 Kit.

Ao usar o app, você assume **toda a responsabilidade** pelas operações no cartão SD e pelas ações subsequentes na consola (incluindo instalação de Unlaunch ou outro software).

### Risco de brick e papel do app

- O Route 1 Kit **prepara ficheiros no cartão SD**. **Não grava na NAND** do Nintendo DSi por si só.
- O **Unlaunch** (e fluxos semelhantes), quando executados **na consola**, **escrevem na NAND**. Há um **risco real, ainda que pequeno, de brick** (consola inutilizável). Só avance se tiver **backup da NAND** e compreender o guia oficial ([dsi.cfw.guide](https://dsi.cfw.guide/)).
- Binários incorretos, incompletos ou de origem não verificada no cartão podem causar falhas graves se forem instalados via Unlaunch ou outros instaladores.
- A UI do assistente reforça estes avisos nas etapas críticas; leia-os antes de continuar.

### Afiliação e marcas

O Route 1 Kit **não é afiliado, endossado ou patrocinado** pela Nintendo Co., Ltd. nem pelas respetivas subsidiárias. **Nintendo**, **DSi** e demais marcas relacionadas são propriedade dos seus titulares. Nomes de flashcards (GEi, AceKard, R4, etc.) e de projetos homebrew são usados apenas para identificação; pertencem aos respetivos donos.

### Licença do código deste repositório

O **código-fonte do Route 1 Kit** (Python, HTML/CSS/JS da UI embutida, scripts e documentação deste repositório, salvo indicação em contrário) está licenciado sob a **GNU General Public License versão 3** — ver [`LICENSE`](LICENSE).

### Componentes descarregados (terceiros)

Durante o uso, o app pode **descarregar** binários e arquivos de projetos upstream (por exemplo Memory Pit e dumpTool via [dsi.cfw.guide](https://dsi.cfw.guide/), Unlaunch Installer, TWiLight Menu++). Esses componentes:

- mantêm as **licenças, autores e termos dos projetos originais**;
- **não** são “relicenciados” sob a GPL-3.0 do Route 1 Kit só por serem descarregados ou copiados para o SD;
- são obtidos de URLs documentadas em `core/cache.py`, com verificação **SHA-256 pinada** (integridade, não uma garantia de isenção de risco).

Respeite as licenças e créditos de cada projeto ao redistribuir ou modificar esses ficheiros fora do fluxo do app.

### ROMs, dumps e conteúdo no cartão

O organizador de ROMs **não fornece** jogos, ROMs nem dumps protegidos por direitos de autor. Apenas reorganiza ficheiros que **você** coloca no cartão. É **sua responsabilidade** garantir que possui o direito legal de possuir e usar esse conteúdo na sua jurisdição.

### Formatação e unidades

A formatação **FAT32** **apaga todos os dados** do volume selecionado. O app tenta restringir operações a volumes **removíveis / USB / SD** reconhecidos; ainda assim, confirme sempre a unidade correta. Erros de seleção ou limitações do sistema operativo podem ter consequências graves.

### Segurança

Para reportar vulnerabilidades de segurança, consulte [`SECURITY.md`](SECURITY.md).

---

## Tecnologias

- **App shell:** Python 3 + pywebview (janela nativa)
- **UI:** HTML5, Tailwind CSS (compilado local), fontes locais, JavaScript; 8 temas via tokens CSS (`static/themes.css`)
- **Lógica:** módulos em `core/` (discos, exploits, TWiLight, ROMs, limpeza, cache, sdio, validate)
