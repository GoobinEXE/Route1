# Manual do desenvolvedor — Route Pico no console

## Visão rápida

- Runtime: homebrew `.nds` (C, libnds / toolchain DSPico) em `nds/`
- Spec USB: `protocol/R1USB.md` + `protocol/messages.json`
- Host: o desktop Route Pico (Python/pywebview) neste mesmo repositório

Lê primeiro: `AGENTS.md` (raiz) e `docs/console/PLAN.md`.

## Setup

### Host-sim (Fase 1, sem hardware)

```bash
cd nds
make test
make host-sim
./build/routepico_host --sd tests/fixtures/fake_sd
```

O `pytest` da raiz corre os mesmos testes C (`tests/test_nds_host.py`) e a conformidade do protocolo (`tests/test_protocol_messages.py`).

Teclas no host: `W/S` ou setas, `A` abrir, `B` subir, `X` apagar, `Y` Games, `R` Apps, `Q` sair.

### NDS (`.nds`)

1. Instalar [devkitPro](https://devkitpro.org/) (devkitARM, libnds, libfat).
2. `export DEVKITPRO=...` e `DEVKITARM=$DEVKITPRO/devkitARM`
3. `make -C nds nds` → `nds/RoutePico.nds`
4. Copiar para `Apps/` no SD (Pico Launcher).

Para USB DSPico (Fase 2+): https://github.com/LNH-team/dspico-usb-examples  

## Layout do código

```
nds/src/main.c      — entrada
src/app/browser.c   — gestor (Fase 1)
src/ui/             — ui_host.c / ui_nds.c
src/input/          — input_host.c / input_nds.c
src/fs/             — fs.c (POSIX host) / fs_nds.c (libfat)
src/usb/            — sessão USB (Fase 2+)
src/integrity/      — hash / partial / promote
src/util/           — path, protect, err
nds/include/route1/ — API interna
nds/tests/          — testes C no host + fixtures/fake_sd
protocol/           — spec R1USB (partilhada com o desktop)
```

Os caminhos `src/…` acima são relativos a `nds/`.

## Regras de implementação

1. Toda escrita de ficheiro completo passa por `integrity`.
2. Paths: validar com helper único (`r1_path_is_safe`).
3. Mensagens UI em PT; códigos de erro de protocolo estáveis em inglês (`E_HASH`).
4. Alterar frames → bump em `protocol/messages.json`, `version.h` e `protocol/R1USB.md` no mesmo commit (ver «Alterar o protocolo» na spec).
5. Não adicionar download de ROMs de terceiros / scrapers.

## Testes

- `nds/tests/host/` no PC: path safety e fs; `tests/test_protocol_messages.py`: spec vs headers C.
- No hardware: checklist em `docs/console/PLAN.md`.
- Nunca testar writes em disco interno do Mac/PC sem volume removível isolado.

## Integração com o desktop

1. Ler a fase 3 de `docs/console/PLAN.md` e `protocol/R1USB.md`.
2. Implementar a ponte em `core/r1usb_host.py` / `services/r1usb_bridge.py`.
3. Mesma versão de protocolo no handshake (o teste de conformidade falha se divergir).
4. Escritas no SD pelo desktop passam por `_run_mount_op` / `OP_LOCK` / `copy_verified`.

## Build / CI (futuro)

- Compilar stub em CI Linux com devkitARM se possível
- Testes Python de protocolo sem hardware
- Artefacto `.nds` só em release assinado/versionado

## Estilo

- C99/C11 preferido
- Nomes: `r1_<modulo>_<accao>`
- Comentários só onde a regra de integridade/USB não for óbvia

## Referências

- Manual DSPico ChiScart (PDF)
- LNH GUIDE / pico-launcher Usage
- dspico-usb-examples
- `AGENTS.md` da raiz para os invariantes de SD no desktop
