# AGENTS.md — Route 1 Kit

Guia para agentes (Cursor e similares) que trabalham neste repositório.

## O que é

App desktop **multiplataforma** (macOS / Windows / Linux) que prepara cartões SD para **Nintendo DSi** e flashcards (GEi / AceKard / R4). Nome do produto: **Route 1 Kit**.

- Shell: Python 3.9+ + **pywebview** (janela nativa; **sem** servidor HTTP)
- UI: HTML/CSS/JS offline em `static/` (Tailwind compilado localmente, fontes embutidas)
- Lógica: módulos em `core/`
- Bridge: classe `Api` em `app.py` exposta ao JS via `js_api`

**Aviso de domínio:** o app não escreve na NAND do DSi, mas binários errados no cartão (Unlaunch, etc.) podem brickar o console. Tratar operações de escrita/format como destrutivas e exigir validação estrita de montagens.

## Mapa do repositório

| Caminho | Papel |
|---------|--------|
| `app.py` | Entrada, `Api` (bridge JS↔Python), `OP_LOCK` / logs, preflight + ops de montagem |
| `core/disks.py` | Listagem e formatação de volumes removíveis |
| `core/sdio.py` | Pré-voo de escrita, sync de volume |
| `core/exploits.py` | Passo 1 (Memory Pit + dumpTool) e Passo 2 (Unlaunch) |
| `core/twilight.py` | TWiLight Menu++, kernels GEi / R4 |
| `core/rom_cleaner.py` | Organização de ROMs / saves |
| `core/cleaner.py` | Backup do SD, limpeza de metadados macOS |
| `core/cache.py` | Downloads oficiais + **SHA-256 pinados** |
| `core/validate.py` | Validação NDS / integridade |
| `core/inspect_sd.py` | Inspeção do cartão (wizard) |
| `core/privacy.py` | Redação de paths / PII em logs e respostas |
| `static/app.js` | Modo avançado, poll de logs, `runMountOp` / `busy` |
| `static/wizard.js` | Assistente passo a passo (`renderGen`) |
| `static/theme.js` + `themes.css` | Temas (tokens `--c-*`) |
| `tests/` | pytest |
| `tools/update_pins.py` | Verificar / atualizar pins SHA-256 |
| `tools/build_icons.py` | Regenerar ícones a partir dos SVGs |
| `.cursor/rules/*.mdc` | Regras detalhadas e sempre/parcialmente aplicadas |

## Como correr

```bash
source .venv/bin/activate
pip install --require-hashes -r requirements.lock.txt
pip install -r requirements-dev.txt   # testes
python app.py
pytest -q
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
4. Respostas tipicamente `{success: bool, error?: str, ...}` — erros via `_reject` / redação em `core.privacy`.
5. Fecho da janela: se `OP_LOCK.locked()`, **bloquear** o close.

## Invariantes (não negociáveis)

Detalhe e exemplos: `.cursor/rules/` — não duplicar aqui; cumprir sempre.

1. **Concorrência** (`concurrency-safety`): timeouts em subprocess de disco; `finally` no lock; JS `setBusy` + `finally`; um poll de logs in-flight; wizard com `renderGen`.
2. **Defensiva** (`defensive-programming`): `with` / cleanup; inputs da UI não confiáveis; nunca crashar a janela com exceção não tratada na fronteira.
3. **API segura** (`secure-api-boundary`): `_as_path_str`, `_as_bool` (nunca `bool("false")`), `is_safe_mount_path` / `resolve_safe_drive`; `subprocess` só com lista de args; XSS → `escapeHtml` / `textContent`.
4. **Privacidade** (`privacy-logging`): não logar home absoluto; `redact_path` / `redact_text`; não devolver conteúdo de `nand.bin` nem segredos.
5. **Cleanup** (`resource-cleanup`): `.partial` + `os.replace`; probes de escrita removidos em `finally`; handles Win32 fechados; backups de etapa limpos no sucesso.
6. **SD resiliente** (`resilient-sd-ops`): verify-before-replace; `UndoStack` + sync após rollback; promote atómico (staging); `inspect_sd` sob `OP_LOCK`.
7. **Null / buffers / tipos** (`null-safety-buffers`): Win32 tamanhos em TCHARs (`len(buf)`, não `sizeof`); sem `[0]`/`result.x` sem guarda; `float`/`int` com try; helpers de path não devolvem `None`.

## Convenções de código

- Preferir mudanças mínimas e alinhadas ao estilo existente (nomes, helpers de `app.py` / `core/`).
- UI 100% **offline**: sem CDN, sem fetch remoto na UI (downloads oficiais só via `core/cache.py` com pins).
- Temas: só tokens em `themes.css` + entrada em `THEMES` (`theme.js`); `style.css` / Tailwind consomem `--c-*`.
- Preferência Assistente/Avançado: `sessionStorage` (sessão); tema: `localStorage` (`route_1_kit_theme`).
- Idioma do produto / README: português (pt); manter mensagens de UI e logs de utilizador em PT.
- Não inventar telemetria remota.

## Ao rever ou alterar código

Antes de refactors cosméticos, assinalar:

- [ ] subprocess sem `timeout=`
- [ ] preflight / escrita fora de `OP_LOCK`
- [ ] fecho da janela sem guarda de lock
- [ ] Promise JS sem `finally { setBusy(false) }`
- [ ] path / bool da UI sem tipagem / revalidação
- [ ] path absoluto de home em log ou payload
- [ ] ficheiro de probe / handle / `.partial` sem cleanup
- [ ] `copy_verified` a verificar **depois** do replace, ou multi-write sem undo
- [ ] Win32 `ctypes.sizeof(buf)` onde a API pede TCHARs
- [ ] `split()[0]` / `result.success` / `float(...)` sem guarda

## Fora de âmbito típico

- Não commitiar sem pedido explícito do utilizador.
- Não alterar pins SHA-256 / URLs em `core/cache.py` sem evidência (`update_pins.py` / digest oficial).
- Não formatar / escrever em volumes que falhem `is_safe_mount_path`.
- Não adicionar dependências sem atualizar `requirements.txt` + lock com hashes quando aplicável.
