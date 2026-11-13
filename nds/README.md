# Route Pico no console (`nds/`)

App homebrew `.nds` do Route Pico: gestor de ficheiros do microSD no próprio DS/DSi (alvo: DSPico + Pico Launcher) e, nas próximas fases, ponte USB verificada com o desktop.

```bash
cd nds
make test                                   # testes C no host
make host-sim && ./build/routepico_host --sd tests/fixtures/fake_sd
make nds                                    # RoutePico.nds (requer DEVKITPRO + libnds + libfat)
```

Plano, manuais e arquitetura: [`docs/console/`](../docs/console/). Protocolo USB: [`protocol/R1USB.md`](../protocol/R1USB.md). Regras para agentes: secção «App do console» do [`AGENTS.md`](../AGENTS.md).

Este diretório veio do repositório Route1-DSi (fase 1). Os prefixos `r1_` / `R1_` e o nome de protocolo R1USB foram mantidos de propósito.
