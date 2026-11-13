# Route Pico no console — plano

Documento vivo. Atualizar ao fechar cada fase. O app do console (`nds/`) e o desktop são o mesmo produto, Route Pico; este plano cobre o lado `.nds` e a ponte USB.

## Visão

Um `.nds` aberto a partir do Pico Launcher que gere o microSD no próprio DS e liga-se por USB ao Route Pico no PC para copiar ficheiros depressa e sem corromper nada. O PC continua a fazer o trabalho pesado (preparar o cartão, capas, RouteDex, catálogos pessoais e NAS); o console é a mão no cartão quando o microSD fica dentro do cartucho.

Pensado para quem tem DSPico, usa o Route Pico no PC e prefere não tirar o microSD do cartucho.

## Focos

| Foco | Inclui | Não inclui |
|---|---|---|
| 1. Gestor de ficheiros no console | Listar, navegar, criar pasta, renomear, mover, copiar e apagar; tamanho e espaço livre; atalhos `Games/`, `Apps/`, `_pico/`; proteção dos markers oficiais | Editor de texto, vídeo, browser |
| 2. USB rápido e seguro com o desktop | Chunks grandes, hash em streaming, `.r1partial` → SHA-256 → promote → sync, retoma, cancelamento limpo, uma escrita de cada vez | Wi‑Fi como transporte, compressão de ROMs |
| 3. Protocolo partilhado | [`protocol/R1USB.md`](../../protocol/R1USB.md) + `messages.json`, testes de conformidade em `tests/` | Formato no fio fora da spec |
| 4. Não corromper | Manifesto de sessão, limpeza de parciais, abortar se o volume desmontar, erros claros em PT | Sucesso reportado sem verificação |

O que pertence ao desktop e não se duplica aqui: softmod, Unlaunch, formatação, pins SHA-256 de upstream, temas e capas do Pico Launcher, RouteDex. Fora do produto em qualquer lado: loja ou agregador de ROMs (estilo Hydra/Overdrive), fontes pré-definidas de ROMs comerciais, download Wi‑Fi de jogos de terceiros.

## Fases

### Fase 0 — Fundação (concluída)

Estrutura, regras, manuais, spec inicial do protocolo e builds host-sim / `.nds`. Falta validar o `.nds` em hardware real.

### Fase 1 — Gestor local (código pronto; falta hardware)

- [x] Arranque na raiz; atalhos Y → `Games/`, R → `Apps/`
- [x] Navegar pastas, ver tamanho e espaço livre (no host; no NDS a libfat pode reportar 0)
- [x] Apagar ficheiro ou pasta (recursivo) com confirmação
- [x] Proteção de `_picoboot.nds` e `_pico/` com confirmação forte (A → X)
- [x] Path traversal rejeitado, com testes
- [x] Host-sim (`make -C nds host-sim`) e testes C corridos pelo `pytest` da raiz
- [ ] `RoutePico.nds` testado num DSPico

Limitações conhecidas: lista de até 200 entradas; sem copiar/mover locais (fase 4); sem USB (fase 2).

### Fase 2 — USB assistido (MSC)

O console entra em "USB ligado" e mostra que o cartão está ocupado; o desktop deteta o volume do DSPico e copia com o contrato que já usa (`_run_mount_op`, `OP_LOCK`, `copy_verified`, sync). Critérios: nenhuma escrita local no console durante o MSC; o desktop nunca reporta sucesso sem hash.

### Fase 3 — Protocolo R1USB (bulk)

Handshake versionado, LIST / PUT / GET / CANCEL / COMMIT, chunks com hash em streaming e retoma por offset. No desktop, a ponte fica em `core/r1usb_host.py` (framing e sessão) e `services/r1usb_bridge.py`, com a UI "Console ligado" na vista DSPico. Critérios: desligar o cabo a 50 % leva a retoma ou limpeza explícita; manifesto de sessão igual nos dois lados; throughput medido contra o MSC.

### Fase 4 — Gestor completo

Copiar e mover locais com progresso, seleção múltipla, atalhos DSPico (`Games/`, `Apps/`, saves), ajuda no ecrã em PT e instalação do `RoutePico.nds` em `Apps/` a partir do desktop, pelo mesmo caminho verificado das outras instalações.

### Fase 5 — Extensões (só com F1–F4 estáveis)

O console pede ao desktop "sincronizar a minha pasta pessoal / NAS" e o desktop executa. Console ↔ console não é prioridade (faz-se via PC).

## Checklist antes de ligar o desktop ao console

- [ ] Mesma versão de protocolo nos dois lados (`tests/test_protocol_messages.py`)
- [ ] Caminhos rejeitam `..` e NUL nos dois lados
- [ ] PUT usa `.r1partial` + SHA-256 + promote; CANCEL limpa o staging
- [ ] `OP_LOCK` no desktop e uma escrita de cada vez no console
- [ ] Timeout USB documentado; desligar a meio dá erro, nunca sucesso
- [ ] UI em PT e caminhos de home redigidos nos logs
- [ ] `_picoboot.nds` / `_pico` com confirmação
- [ ] Teste num DSPico real antes de release

## Riscos

| Risco | Mitigação |
|---|---|
| Bug de USB no firmware do DSPico (reset + USB) | Documentar o ciclo de energia; seguir `dspico-usb-examples` do LNH |
| SD lento ou corrupção | Staging + hash + uma escrita de cada vez |
| Âmbito a crescer para loja Wi‑Fi | Focos acima e `AGENTS.md` |
| Console e desktop divergirem | Spec versionada + teste que compara `messages.json` com os headers C |

## Métricas

Zero ficheiros reportados como "ok" com hash errado; transferência USB pelo menos tão rápida como o MSC; gestor usável sem mais de um ecrã de explicação; ligar e copiar um `.nds` em menos de 2 minutos para quem já usa o desktop.
