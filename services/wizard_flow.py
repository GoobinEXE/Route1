"""Definição dos passos do assistente (paridade com static/wizard.js)."""

from __future__ import annotations

from typing import Any, Dict, List


Step = Dict[str, Any]


def initial_step(goal: str) -> Step:
    steps = build_steps(goal, brand="")
    if steps:
        return steps[0]
    return {
        "id": "home",
        "title": "Route 1 Kit",
        "where": "PC",
        "bodyKind": "home",
    }


def build_steps(goal: str, brand: str = "") -> List[Step]:
    g = (goal or "").strip()
    if g in ("flash-update", "flash-new"):
        return _flash_steps(from_scratch=(g == "flash-new"), brand=brand)
    if g == "sd-new":
        return _sd_new_steps()
    if g == "sd-update":
        return _sd_update_steps()
    if g == "dspico-sd":
        return _dspico_sd_steps()
    if g == "dspico-fw":
        return _dspico_fw_steps()
    return []


def _flash_steps(*, from_scratch: bool, brand: str) -> List[Step]:
    brand_label = {"gei": "GEi", "dspico": "DSPico", "r4": "R4"}.get(brand, "flashcard")
    steps: List[Step] = [
        {
            "id": "brand",
            "title": "Qual é o seu flashcard?",
            "where": "PC",
            "bodyKind": "brand",
        },
        {
            "id": "select-card",
            "title": "Selecione o MicroSD do cartucho",
            "where": "PC",
            "bodyKind": "drive",
            "warning": (
                "Use o MicroSD que fica dentro do cartucho Slot-1 "
                "(não o SD lateral do DSi)."
            ),
        },
    ]
    if from_scratch:
        steps.append(
            {
                "id": "format-warn",
                "title": "Formatar em FAT32",
                "where": "PC",
                "bodyKind": "format",
                "warning": "Apaga todos os dados do MicroSD seleccionado.",
            }
        )
        steps.append(
            {
                "id": "reinsert-format",
                "title": "Reinserir o cartão após formatar",
                "where": "PC",
                "bodyKind": "reinsert",
                "warning": (
                    "Após formatar, actualize a lista e seleccione o MicroSD de novo."
                ),
            }
        )
    else:
        steps.append(
            {
                "id": "backup",
                "title": "Backup recomendado",
                "where": "PC",
                "bodyKind": "backup",
            }
        )

    if not brand:
        # Só brand até escolher; total aproximado
        return steps[:1]

    prep_title = (
        "Preparar pacote DSPico"
        if brand == "dspico"
        else f"Preparar kernel {brand_label}"
    )
    install_title = (
        "Instalar pacote DSPico"
        if brand == "dspico"
        else f"Instalar kernel {brand_label}"
    )
    steps.append(
        {
            "id": "kernel-prep",
            "title": prep_title,
            "where": "PC",
            "bodyKind": "kernel_prep",
        }
    )
    steps.append(
        {
            "id": "kernel-install",
            "title": install_title,
            "where": "PC",
            "bodyKind": "kernel_install",
        }
    )
    steps.append(
        {
            "id": "roms-opt",
            "title": (
                "Adicionar jogos a Games/ (opcional)"
                if brand == "dspico"
                else "Organizar jogos (opcional)"
            ),
            "where": "PC",
            "bodyKind": "dspico_games" if brand == "dspico" else "roms_opt",
        }
    )
    if brand == "dspico":
        done = [
            "Ejete o MicroSD com segurança no sistema operativo.",
            "Insira-o no cartucho DSPico e o cartucho no DSi/DS.",
            "O microSD já tem Pico Launcher + Loader oficiais LNH.",
            "Para firmware UF2 e mais opções, use Instalar DSPico no hub.",
        ]
    else:
        done = [
            "Ejete o MicroSD com segurança no sistema operativo.",
            f"Coloque-o no cartucho {brand_label} e ligue o DSi/DS.",
            "Se o menu não abrir, confirme que o kernel é do clone exacto.",
        ]
    steps.append(
        {
            "id": "done-flash",
            "title": "Pronto",
            "where": "PC",
            "bodyKind": "done",
            "doneLines": done,
        }
    )
    return steps


def _sd_new_steps() -> List[Step]:
    return [
        {
            "id": "model",
            "title": "É um Nintendo DSi?",
            "where": "PC",
            "bodyKind": "model",
        },
        {
            "id": "camera",
            "title": "Qual versão da app Câmera?",
            "where": "PC",
            "bodyKind": "camera",
        },
        {
            "id": "select-lateral",
            "title": "Selecione o SD do slot lateral",
            "where": "PC",
            "bodyKind": "drive",
            "warning": (
                "Use o cartão do slot lateral do DSi — "
                "não o MicroSD de um flashcard Slot-1."
            ),
        },
        {
            "id": "dcim-fat",
            "title": "Preparar o cartão (DCIM e FAT32)",
            "where": "PC",
            "bodyKind": "dcim_fat",
        },
        {
            "id": "stage1",
            "title": "Passo 1 — preparar exploit e dumpTool",
            "where": "PC",
            "bodyKind": "stage1",
        },
        {
            "id": "exploit",
            "title": "No DSi — abrir o exploit da Câmera",
            "where": "DSi",
            "bodyKind": "exploit_dsi",
        },
        {
            "id": "nand-dump",
            "title": "No DSi — guardar cópia da memória interna",
            "where": "DSi",
            "bodyKind": "nand_dump_dsi",
        },
        {
            "id": "reinsert-nand",
            "title": "No PC — verificar a cópia (nand.bin)",
            "where": "PC",
            "bodyKind": "nand_verify",
        },
        {
            "id": "stage2",
            "title": "Passo 2 — menu e instalador Unlaunch",
            "where": "PC",
            "bodyKind": "stage2",
        },
        {
            "id": "unlaunch-dsi",
            "title": "No DSi — instalar Unlaunch",
            "where": "DSi",
            "bodyKind": "unlaunch_dsi",
        },
        {
            "id": "unlaunch-opts",
            "title": "No DSi — arranque automático no menu",
            "where": "DSi",
            "bodyKind": "unlaunch_opts",
        },
        {
            "id": "hiya-install",
            "title": "hiyaCFW — sistema no cartão (recomendado)",
            "where": "PC",
            "bodyKind": "hiya",
        },
        {
            "id": "roms-opt",
            "title": "Organizar jogos (opcional)",
            "where": "PC",
            "bodyKind": "roms_opt",
        },
        {
            "id": "done-sd",
            "title": "Instalação concluída",
            "where": "PC",
            "bodyKind": "done",
            "doneLines": [
                "Ejete o SD com segurança.",
                "Insira-o no slot lateral do DSi e ligue a console.",
                "Se instalou hiyaCFW: Unlaunch A+B → OPTIONS → NO BUTTON → hiyaCFW.",
                "Sem hiya: deve arrancar no TWiLight (NO BUTTON → BOOT.NDS).",
            ],
        },
    ]


def _sd_update_steps() -> List[Step]:
    return [
        {
            "id": "select-lateral",
            "title": "Selecione o SD do slot lateral",
            "where": "PC",
            "bodyKind": "drive_inspect",
            "warning": "Cartão do slot lateral com Unlaunch/TWiLight já instalados.",
        },
        {
            "id": "backup",
            "title": "Backup recomendado",
            "where": "PC",
            "bodyKind": "backup",
        },
        {
            "id": "update-twl",
            "title": "Atualizar TWiLight Menu++",
            "where": "PC",
            "bodyKind": "stage2",
        },
        {
            "id": "hiya-install",
            "title": "hiyaCFW (instalar ou atualizar)",
            "where": "PC",
            "bodyKind": "hiya",
        },
        {
            "id": "roms-opt",
            "title": "Organizar jogos / limpar (opcional)",
            "where": "PC",
            "bodyKind": "roms_clean",
        },
        {
            "id": "done-upd",
            "title": "Atualização concluída",
            "where": "PC",
            "bodyKind": "done",
            "doneLines": [
                "Ejete o SD com segurança e volte a colocá-lo no DSi.",
                "Não é necessário reinstalar o Unlaunch se a console já arranca no menu.",
            ],
        },
    ]


def _dspico_sd_steps() -> List[Step]:
    return [
        {
            "id": "select-card",
            "title": "MicroSD do DSPico",
            "where": "PC",
            "bodyKind": "drive",
            "warning": "MicroSD que vai dentro do cartucho DSPico (Slot-1).",
        },
        {
            "id": "kernel-install",
            "title": "Instalar pacote LNH",
            "where": "PC",
            "bodyKind": "kernel_install",
        },
        {
            "id": "roms-opt",
            "title": "Jogos (opcional)",
            "where": "PC",
            "bodyKind": "dspico_games",
        },
        {
            "id": "done",
            "title": "Pacote pronto",
            "where": "PC",
            "bodyKind": "done",
            "doneLines": [
                "Ejete o MicroSD e coloque-o no DSPico.",
                "Firmware UF2 grava-se em modo BOOTSEL (hub → Instalar DSPico).",
            ],
        },
    ]


def _dspico_fw_steps() -> List[Step]:
    return [
        {
            "id": "bootsel",
            "title": "Entrar em modo BOOTSEL",
            "where": "PC",
            "bodyKind": "bootsel",
        },
        {
            "id": "flash",
            "title": "Gravar firmware UF2",
            "where": "PC",
            "bodyKind": "flash_uf2",
        },
        {
            "id": "done",
            "title": "Firmware gravado",
            "where": "PC",
            "bodyKind": "done",
            "doneLines": [
                "O volume RPI-RP2 deve desaparecer após a gravação.",
                "Volte a inserir o microSD com o pacote LNH no cartucho.",
            ],
        },
    ]
