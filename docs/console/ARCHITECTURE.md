# Arquitetura — Route Pico no console

## Diagrama lógico

```
┌─────────────────────────────────────────────┐
│                 DSi / DSPico                │
│  ┌─────────┐  ┌─────┐  ┌──────┐  ┌───────┐  │
│  │  ui     │──│ fs  │──│integr│──│  usb  │  │
│  └─────────┘  └─────┘  └──────┘  └───┬───┘  │
│                                      │      │
│              microSD ◄───────────────┘      │
└──────────────────────────────────┬──────────┘
                                   │ USB
┌──────────────────────────────────▼──────────┐
│          Route Pico desktop (PC)            │
│   core/r1usb_host.py (fase 3, ver PLAN)     │
└─────────────────────────────────────────────┘
```

## Módulos (`nds/src/`)

| Módulo | Responsabilidade | Não faz |
|--------|------------------|---------|
| `ui/` | Ecrãs, input, confirmações | I/O bruto no SD |
| `fs/` | Listar, mkdir, rename, unlink, copy local | USB frames |
| `integrity/` | SHA-256, partial path, promote, manifesto | UI |
| `usb/` | Sessão, chunks, estado da ligação | Layout de pastas DSPico |
| `util/` | Strings, path safe, logging local | Política de produto |

## Regras de dependência

```
ui → fs, usb, util
usb → integrity, util
fs → integrity (em writes), util
integrity → util
util → (nada de domínio)
```

Proibido: `fs` importar `ui`; `integrity` importar `usb`.

## Modelos de transporte USB

### A — MSC (Fase 2)

O DSi corre mass-storage (base LNH). O PC monta o volume e o **Route Pico desktop** escreve com as regras de integridade que já usa (`copy_verified`, `OP_LOCK`).

O app do console: UI de “modo USB” + bloqueio de writes locais.

### B — Protocolo R1USB (Fase 3)

Endpoints bulk (ou interface além de MSC). Frames em [`protocol/R1USB.md`](../../protocol/R1USB.md). O DSi ou o PC podem ser origem; o **commit** no SD segue sempre `integrity/`.

## Integridade (contrato)

Para qualquer escrita de ficheiro completo:

1. Destino final `path`  
2. Escrever `path.partial` (ou nome staging acordado)  
3. Hash do partial == esperado  
4. Rename/promote atómico  
5. Flush/sync do volume  
6. Só então ACK de sucesso no protocolo / UI  

Falha em qualquer passo: remover staging; destino antigo intacto.

## Concorrência

Mutex lógico `sd_op_lock`:

- Ops `fs` de escrita  
- Receção USB que escreve  

Leitura (listagem) pode partilhar com cuidado; durante USB MSC activo, preferir **só leitura** ou UI bloqueada.

## Layout SD (referência DSPico)

Não reinventar. Seguir manual LNH / ChiScart:

- `_picoboot.nds` na raiz (launcher)  
- `/_pico/` loaders e settings  
- `Games/` jogos  
- `Apps/` homebrew (destino do `RoutePico.nds`)  

O gestor deve **proteger** markers críticos com confirmação extra.

## Fronteira com o desktop

| Assunto | Onde vive |
|---------|-----------|
| Softmod, format, pins SHA upstream, RouteDex | `core/` (desktop) |
| UI desktop de sync / NAS pessoal | `core/` + `static/` (desktop) |
| Spec dos frames USB | `protocol/` |
| Implementação host USB | `core/r1usb_host.py` (fase 3) |
| Runtime `.nds` | `nds/src/` |
