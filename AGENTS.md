# AGENTS.md — Route Pico

Guia para agentes (Cursor e similares) que trabalham neste repositório.

## O que é

App desktop **multiplataforma** (macOS / Windows / Linux) que prepara cartões SD para **Nintendo DSi** e flashcards (GEi / AceKard / R4 / **DSPico**). Nome do produto: **Route Pico** (antes Route 1 Kit). Foco: cartucho **DSPico**; softmod DSi e GEi/R4 ficam em «Mais ferramentas».

- Duas partes no mesmo repositório: o **desktop** (descrito abaixo) e o **app do console** `.nds` em `nds/` (secção «App do console»), ligados pelo protocolo USB em `protocol/`
- Shell: Python 3.10+ + **pywebview** (janela nativa; **sem** servidor HTTP)
- UI: HTML/CSS/JS offline em `static/` (Tailwind compilado localmente, fontes embutidas)
- Lógica: módulos em `core/` (intocados pela shell)
- Bridge: classe `Api` em `app.py` exposta ao JS via `js_api`; `services/FilePickerPort` + `wizard_flow` + `web_events`

**Aviso de domínio:** o app não escreve na NAND do DSi, mas binários errados no cartão (Unlaunch, etc.) podem brickar o console. Tratar operações de escrita/format como destrutivas e exigir validação estrita de montagens.

## Mapa do repositório

| Caminho | Papel |
|---------|--------|
| `app.py` | Entrada pywebview, `Api` (fachada de domínio), `OP_LOCK` / logs, preflight + ops de montagem |
| `services/` | `FilePickerPort`, `wizard_flow`, `web_events` (UI ↔ Api) |
| `static/` | Shell HTML/CSS/JS (sidebar, DSPico, Softmod, Utilidades, Cartão) |
| `static/assets/` | Logo, ícones, plataformas, fontes |
| `core/disks.py` | Listagem e formatação de volumes removíveis |
| `core/sdio.py` | Pré-voo de escrita, sync de volume |
| `core/exploits.py` | Passo 1 (Memory Pit + dumpTool) e Passo 2 (Unlaunch) |
| `core/twilight.py` | TWiLight Menu++, kernels GEi / R4 |
| `vendor/GEiv4.2_EN/` | Pacote base do flashcard GEi (kernel + MoonShell) |
| `core/rom_cleaner.py` | Organização de ROMs / saves |
| `core/rom_manager.py` | Listar / importar / remover / mover jogos no SD (`/roms/`) |
| `core/dspico.py` | Pacote DSPico LNH (`Games/`, emunand, settings, RPI-RP2, organizar pastas); pacote/firmware só `LNH-team`; `DSPICO_OFFICIAL_LINKS` (repos + [manual ChiScart](https://www.chiscart.com/manuals/DS_Pico_user_manual_87a632eec6.pdf)) — ver secção **Fontes oficiais DSPico** |
| `core/dspico_emulators.py` | Catálogo + instalação de emuladores Pico-Launcher (pins `DSPICO_EMU_CACHE_KEYS`) |
| `core/updates.py` | Verificar / instalar actualizações do ecossistema DSPico (pinned + latest LNH); variante opt-in `enhanced` (rasalopa) para launcher/loader |
| `core/routedex.py` | RouteDex: `gamedata.json` sem perdas, saúde do cartão, versão do loader/launcher, capturas, banners/capas de pasta, fundos noturnos, `usrcheat.dat` (port do PicoDex, MIT) |
| `core/data/pico_manifest.json` | SHA-256 por ficheiro das releases Pico Loader/Launcher (oficial + Enhanced); regenerar com `tools/gen_pico_manifest.py` |
| `static/js/routedex.js` | UI do separador DSPico → RouteDex |
| `core/pico_themes.py` | Temas Pico Launcher (`/_pico/themes/`) |
| `core/artwork.py` | Capas/ícones: SteamGridDB (principal) → GameTDB + Libretro → TWiLight `boxart/` / `icons/` |
| `core/steamgriddb.py` | Cliente API SteamGridDB (chave em prefs / `STEAMGRIDDB_API_KEY`) |
| `core/pico_artwork.py` | Capas/ícones Pico Launcher (pesquisa + BMP em `/_pico/covers|icons/`) |
| `core/pico_bmp.py` | Conversão PNG/BMP → capa 128×96 8 bpp / ícone 32×32 4 bpp |
| `core/cleaner.py` | Backup do SD, limpeza de metadados macOS |
| `core/cache.py` | Downloads oficiais + **SHA-256 pinados** |
| `core/homebrew_catalog.py` | Catálogo de apps instaláveis (releases GitHub) |
| `core/homebrew_install.py` | Receitas GameBrew/README (pastas, configs) |
| `core/validate.py` | Validação NDS / integridade |
| `core/inspect_sd.py` | Inspeção do cartão (wizard) |
| `core/privacy.py` | Redação de paths / PII em logs e respostas |
| `tests/` | pytest |
| `tools/update_pins.py` | Verificar / atualizar pins SHA-256 |
| `tools/gen_pico_manifest.py` | Regenerar / `--check` o manifesto de hashes usado pelo RouteDex |
| `nds/` | App do console (C, libnds): gestor de ficheiros do microSD + ponte USB (`make -C nds test`, `make -C nds nds`) |
| `protocol/` | Spec R1USB partilhada desktop ↔ console (`R1USB.md` + `messages.json`) |
| `docs/console/` | Plano, arquitetura e manuais do app do console |
| `tools/build_icons.py` | Regenerar ícones a partir dos SVGs (`static/assets/`) |
| `packaging/` | Spec PyInstaller + Inno Setup (Windows; publisher **Dark Room**) |
| `docs/WINDOWS_SIGNING.md` | Authenticode / Azure Artifact Signing no CI |
| `docs/ui-parity.md` | Inventário de funcionalidades → navegação (gate de UI) |
| `.cursor/rules/*.mdc` | Regras detalhadas e sempre/parcialmente aplicadas (`dspico-sources` quando ficheiros DSPico) |

## Como correr

```bash
source .venv/bin/activate
pip install --require-hashes -r requirements.lock.txt
pip install -r requirements-dev.txt   # testes
python app.py
pytest -q          # inclui testes C do nds/ (make + cc) e conformidade do protocolo
```

Scripts: `start.command` (macOS) / `start.bat` (Windows).

CSS Tailwind após mudar classes na UI:

```bash
npx --yes tailwindcss@3.4.17 -i ./static/tailwind.input.css -o ./static/tailwind.css --minify
```

Pins upstream:

```bash
python tools/update_pins.py --check
```

## Arquitetura da bridge

1. JS chama métodos de `Api` (pywebview serializa JSON).
2. Cada chamada corre numa **thread não-daemon**.
3. Escritas no SD passam por `_run_mount_op` + `OP_LOCK` (`blocking=False`); **`preflight` dentro do lock**.
4. Diálogos de ficheiro: `FilePickerPort` (pywebview `create_file_dialog`), injectado na `Api`.
5. Eventos UI: `services/web_events.py` → `evaluate_js` (`R1K.events.dispatch`); `get_logs` é fallback.
6. Respostas tipicamente `{success: bool, error?: str, ...}` — erros via `_reject` / redação em `core.privacy`.
7. Fecho da janela: se `OP_LOCK.locked()`, **bloquear** o close.

## Invariantes (não negociáveis)

Detalhe e exemplos: `.cursor/rules/` — não duplicar aqui; cumprir sempre.

1. **Concorrência** (`concurrency-safety`): timeouts em subprocess de disco; `finally` no lock; UI `busy` + `finally`; fecho bloqueado com op em curso.
2. **Defensiva** (`defensive-programming`): `with` / cleanup; inputs da UI não confiáveis; nunca crashar a janela com exceção não tratada na fronteira.
3. **API segura** (`secure-api-boundary`): `_as_path_str`, `_as_bool` (nunca `bool("false")`), `is_safe_mount_path` / `resolve_safe_drive`; `subprocess` só com lista de args; XSS → `escapeHtml` / `textContent`.
4. **Privacidade** (`privacy-logging`): não logar home absoluto; `redact_path` / `redact_text`; não devolver conteúdo de `nand.bin` nem segredos.
5. **Cleanup** (`resource-cleanup`): `.partial` + `os.replace`; probes de escrita removidos em `finally`; handles Win32 fechados; backups de etapa limpos no sucesso.
6. **SD resiliente** (`resilient-sd-ops`): verify-before-replace; `UndoStack` + sync após rollback; promote atómico (staging); `inspect_sd` sob `OP_LOCK`.
7. **Null / buffers / tipos** (`null-safety-buffers`): Win32 tamanhos em TCHARs (`len(buf)`, não `sizeof`); sem `[0]`/`result.x` sem guarda; `float`/`int` com try; helpers de path não devolvem `None`.

## Convenções de código

- Preferir mudanças mínimas e alinhadas ao estilo existente (nomes, helpers de `app.py` / `core/` / `services/`).
- UI 100% **offline**: sem CDN, sem fetch remoto na UI (downloads oficiais só via `core/cache.py` com pins).
- Temas da app: tokens em `themes.css` + entrada em `THEMES` (`theme.js`); CSS consome `--c-*`.
- Navegação: sidebar Início / DSPico / Softmod DSi / Utilidades / Cartão SD / Outros flashcards / Definições; wizards em `services/wizard_flow.py`.
- DSPico (pacote/firmware): só downloads `DSPICO_CACHE_KEYS` / `github.com/LNH-team/`; jogos NDS/DSi em `Games/`; UF2 só com `dspico_firmware_uf2_ready()`.
- DSPico Enhanced: só por escolha explícita (`variant="enhanced"`), pins `DSPICO_ENHANCED_CACHE_KEYS`, aviso `ENHANCED_DISCLAIMER` visível; o oficial continua o padrão e há sempre «Voltar ao oficial».
- RouteDex: crédito ao PicoDex (rasalopa, MIT) visível na UI; nunca sobrescrever um `gamedata.json` que não faz parse; remoções copiam antes para `~/.route_1_kit_cache/routedex_backup/`.
- DSPico (emuladores): pins em `DSPICO_EMU_CACHE_KEYS` (guias Sanrax / autores oficiais); NDS em `/_pico/emulators/` ou `/Emulators/`; ROMs retro em `/ROMs/`; nunca descarregar BIOS proprietária.
- Idioma do produto / README: português (pt); manter mensagens de UI e logs de utilizador em PT.
- Não inventar telemetria remota.

## Fontes oficiais DSPico (agents)

Ao trabalhar no modo DSPico (`core/dspico*.py`, `core/pico_*.py`, `static/dspico.js`, `static/js/*`, testes associados), **usar estas fontes** — não inventar layout do SD, nomes de ficheiros nem fluxo de firmware. Regra Cursor: `.cursor/rules/dspico-sources.mdc`. URLs também em `DSPICO_OFFICIAL_LINKS` (`core/dspico.py`).

| Fonte | URL |
|-------|-----|
| Manual utilizador (ChiScart PDF) | https://www.chiscart.com/manuals/DS_Pico_user_manual_87a632eec6.pdf |
| GUIDE LNH | https://github.com/LNH-team/dspico/blob/develop/GUIDE.md |
| Usage Pico Launcher | https://github.com/LNH-team/pico-launcher/blob/develop/docs/Usage.md |
| Themes Pico Launcher | https://github.com/LNH-team/pico-launcher/blob/develop/docs/Themes.md |
| pico-launcher | https://github.com/LNH-team/pico-launcher |
| pico-loader | https://github.com/LNH-team/pico-loader |
| dspico-firmware | https://github.com/LNH-team/dspico-firmware |
| dspico-hardware | https://github.com/LNH-team/dspico-hardware |
| dspico (meta) | https://github.com/LNH-team/dspico |
| dspico-usb-examples | https://github.com/LNH-team/dspico-usb-examples |

Consultar o manual/GUIDE/Usage (ou o README dos repos) **antes** de alterar preparação do SD, markers (`_picoboot.nds`, `_pico/`), jogos, emunand ou flash UF2. Em conflito com código local, preferir a fonte oficial e actualizar o app com evidência.

## App do console (`nds/`)

Homebrew `.nds` aberto a partir do Pico Launcher. Plano e fases: `docs/console/PLAN.md`; regras detalhadas em `.cursor/rules/` (`defensive-nds`, `path-safety`, `integrity-transfers`, `protocol-versioning`). Identificadores em inglês com prefixo `r1_` / `R1_`; UI e mensagens em PT.

Invariantes:

1. **Integridade:** nunca promover sem hash OK; em falha apaga-se só o `.r1partial`.
2. **Concorrência:** uma escrita no SD de cada vez; USB e gestor local nunca escrevem em paralelo.
3. **Caminhos:** um só helper (`r1_path_is_safe`); rejeitar `..`, NUL e caminhos de outro volume; `_picoboot.nds` e `/_pico` exigem confirmação forte (`E_DENIED` sem ela).
4. **Protocolo:** mudança em `protocol/` sobe a versão em `messages.json`, `version.h` e `R1USB.md` no mesmo commit; `tests/test_protocol_messages.py` compara os dois lados.
5. **Timeouts:** I/O USB e SD com limite; a sessão aborta se o cartão desaparecer.

Fronteira: softmod, formatação, pins SHA-256 de upstream, temas, capas e RouteDex ficam no desktop; o console não os duplica. A ponte host vai para `core/r1usb_host.py` + `services/r1usb_bridge.py` (fase 3).

Fora do produto (desktop e console): loja ou agregador de ROMs (estilo Hydra/Overdrive), scrapers ou fontes pré-definidas de ROMs comerciais, download Wi‑Fi de jogos de terceiros, escrita na NAND do DSi.

## Orçamento de performance (UI)

- Arranque até interactivo &lt; 1,5 s
- Troca de vista: só `hidden` / mount preguiçoso (sem re-render total)
- Listas &gt; 200 itens: virtualizadas
- Sem polling em idle (logs/busy por push via `web_events`)
- CSS total &lt; 40 KB (Tailwind purge + `app.css`)
- Scripts `defer`; módulos carregados na primeira visita à vista

## Ao rever ou alterar código

Antes de refactors cosméticos, assinalar:

- [ ] subprocess sem `timeout=`
- [ ] preflight / escrita fora de `OP_LOCK`
- [ ] fecho da janela sem guarda de lock
- [ ] path / bool da UI sem tipagem / revalidação
- [ ] path absoluto de home em log ou payload
- [ ] ficheiro de probe / handle / `.partial` sem cleanup
- [ ] `copy_verified` a verificar **depois** do replace, ou multi-write sem undo
- [ ] Win32 `ctypes.sizeof(buf)` onde a API pede TCHARs
- [ ] `split()[0]` / `result.success` / `float(...)` sem guarda
- [ ] XSS: `innerHTML` com input do utilizador sem escape
- [ ] `nds/`: promote sem hash, escrita paralela no SD, path traversal, frame USB fora da spec ou sem bump de versão, sucesso reportado após falha parcial

## Fora de âmbito típico

- Não commitiar sem pedido explícito do utilizador.
- Não alterar pins SHA-256 / URLs em `core/cache.py` sem evidência (`update_pins.py` / digest oficial).
- Não formatar / escrever em volumes que falhem `is_safe_mount_path`.
- Não adicionar dependências sem atualizar `requirements.txt` + lock com hashes quando aplicável.
