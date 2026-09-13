"""Receitas de instalação/configuração por app (guias GameBrew / README).

Cada receita aplica o que o cartão precisa além de copiar o ``.nds``/``.dsi``:
pastas, ficheiros de config (só se ainda não existirem) e cópias extra.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from core.cache import PINNED_SHA256
from core.logging_util import emit_log
from core.sdio import copy_verified

# databases.txt oficial (GameBrew / README Kekatsu-DS) — UDB Universal-DB.
_KEKATSU_DATABASES_TXT = (
    "UDB-Kekatsu-DS="
    "https://gist.githubusercontent.com/cavv-dev/"
    "3c0cbc1b63ac8ca0c1d9f549403afbf1/raw/\n"
)

# Destino principal relativo à raiz do SD (sempre sob /roms/apps/).
APPS_REL = os.path.join("roms", "apps")


def _join_mount(mount_path: str, *parts: str) -> str:
    return os.path.join(mount_path, *parts)


def _ensure_dir(path: str, log) -> None:
    os.makedirs(path, exist_ok=True)


def _write_text_if_missing(path: str, content: str, log, *, label: str) -> bool:
    """Escreve ficheiro de config só se não existir (não sobrescreve o utilizador)."""
    if os.path.isfile(path):
        log(f"Mantido (já existia): {label}")
        return False
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.partial"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
    log(f"Criado: {label}")
    return True


# Notas curtas em PT para a UI (pós-instalação / card).
SETUP_NOTES: Dict[str, List[str]] = {
    "godmode9i": [
        "Abra pelo TWiLight em /roms/apps/GodMode9i.dsi.",
        "Para dump de cartucho: inserir o jogo Slot-1 e usar o menu do GodMode9i.",
    ],
    "ntm": [
        "Requer Unlaunch. Use SysNAND com extremo cuidado (risco de brick).",
        "Backups de títulos ficam em /_nds/ntm/backup/.",
        "Prefira modo SDNAND (hiyaCFW) para testes.",
    ],
    "cart_flasher": [
        "Só em hardware real (não emulador). Logs em /cart-backups/.",
        "Não altere banner da flashcart em DSi/3DS sem CFW — pode bloquear o cartucho.",
    ],
    "dsfetch": [
        "Não coloque em /_nds/ (a wiki pede outro sítio; /roms/apps/ está OK).",
    ],
    "rocket_video": [
        "Converta vídeos para .rvid com Vid2RVID (PC) e coloque em /videos/.",
        "No console, abra o player e navegue até ao ficheiro .rvid.",
    ],
    "fastvideo_ds": [
        "Converta vídeos para .fv com FastVideoDS Encoder e coloque em /videos/fv/.",
        "Argv / TWiLight: pode abrir um .fv directamente a partir do menu.",
    ],
    "ftpd": [
        "Configure Wi‑Fi no DSi (definições do sistema) antes de abrir o ftpd.",
        "No PC, ligue por FTP ao IP mostrado (porta por omissão 5000).",
        "START sai · SELECT liga/desliga backlight.",
    ],
    "kekatsu": [
        "Config em /Kekatsu/databases.txt (UDB pré-preenchida se era a primeira instalação).",
        "No app: menu Databases → escolher UDB-Kekatsu-DS → carregar.",
        "Requer Wi‑Fi no DSi.",
    ],
    "dsidl": [
        "Ligue o Wi‑Fi nas definições do DSi (WPA2; WEP/aberto costuma falhar).",
        "Se ficar preso ao ligar, reabra segurando SELECT para ver o log.",
        "O QR deve conter um URL HTTPS directo (ou script JSON).",
    ],
    "ds_micpassthrough": [
        "Precisa de cabo áudio macho–macho 3,5 mm entre o DS e o PC.",
        "Não há configuração no cartão — só hardware + app.",
    ],
    "ndsi_savedumper": [
        "Insira o cartucho Slot-1, abra o app: A = dump · B = restaurar.",
        "Saves ficam no cartão SD (pode renomear com X / teclado táctil).",
    ],
    "pkmn_chest": [
        "Cópia extra em /_nds/pkmn-chest/ evita o erro nitroFSInit() failed.",
        "Bancos/saves do app usam /_nds/pkmn-chest/.",
        "SELECT no menu principal abre a configuração.",
    ],
}


def recipe_dirs(app_id: str) -> List[Tuple[str, ...]]:
    """Pastas relativas à raiz do SD a criar para o app."""
    common_apps = [(APPS_REL,)]
    extra: Dict[str, List[Tuple[str, ...]]] = {
        "ntm": [("_nds", "ntm", "backup")],
        "cart_flasher": [("cart-backups",)],
        "rocket_video": [("videos",)],
        "fastvideo_ds": [("videos", "fv")],
        "kekatsu": [("Kekatsu",)],
        "pkmn_chest": [("_nds", "pkmn-chest")],
        "dsidl": [("downloads",)],
    }
    return common_apps + extra.get(app_id, [])


def apply_install_recipe(
    mount_path: str,
    app: Dict[str, Any],
    src_path: str,
    *,
    log_callback=None,
) -> Tuple[bool, str, List[str]]:
    """
    Instala binário + estrutura/config da guia oficial.

    Retorna (ok, mensagem, notes).
    """
    log = lambda msg: emit_log(log_callback, msg)
    app_id = app["id"]
    key = app["install_key"]
    dest_name = app["dest_filename"]
    pinned = PINNED_SHA256.get(key)
    if not pinned:
        return False, f"Sem pin SHA-256 para {app['title']}.", []

    notes = list(SETUP_NOTES.get(app_id, []))
    created: List[str] = []

    try:
        for parts in recipe_dirs(app_id):
            path = _join_mount(mount_path, *parts)
            _ensure_dir(path, log)
            created.append("/" + "/".join(parts))

        primary = _join_mount(mount_path, APPS_REL, dest_name)
        copy_verified(
            src_path, primary, expected_sha256=pinned, log_callback=log_callback
        )
        created.append(f"/roms/apps/{dest_name}")

        # --- extras por guia ---
        if app_id == "pkmn_chest":
            # GameBrew: se nitroFSInit falhar, copiar também para /_nds/pkmn-chest/
            nitro = _join_mount(mount_path, "_nds", "pkmn-chest", "pkmn-chest.nds")
            copy_verified(
                src_path, nitro, expected_sha256=pinned, log_callback=log_callback
            )
            created.append("/_nds/pkmn-chest/pkmn-chest.nds")
            log("Cópia nitroFS (guia pkmn-chest) aplicada.")

        elif app_id == "kekatsu":
            db_path = _join_mount(mount_path, "Kekatsu", "databases.txt")
            wrote = _write_text_if_missing(
                db_path,
                _KEKATSU_DATABASES_TXT,
                log,
                label="/Kekatsu/databases.txt",
            )
            if wrote:
                created.append("/Kekatsu/databases.txt")
            else:
                notes.append(
                    "databases.txt já existia — não foi alterado (config pessoal preservada)."
                )

        elif app_id == "rocket_video":
            readme = _join_mount(mount_path, "videos", "LEIA-ME.txt")
            _write_text_if_missing(
                readme,
                (
                    "Coloque aqui ficheiros .rvid convertidos com Vid2RVID.\n"
                    "Abra RocketVideoPlayer.dsi no TWiLight e navegue até /videos/.\n"
                    "Guia: https://wiki.ds-homebrew.com/ds-index/rocketvideo\n"
                ),
                log,
                label="/videos/LEIA-ME.txt",
            )

        elif app_id == "fastvideo_ds":
            readme = _join_mount(mount_path, "videos", "fv", "LEIA-ME.txt")
            _write_text_if_missing(
                readme,
                (
                    "Coloque aqui ficheiros .fv (FastVideoDS Encoder 2).\n"
                    "Abra FastVideoDS.nds no TWiLight ou associe .fv no menu.\n"
                ),
                log,
                label="/videos/fv/LEIA-ME.txt",
            )

        elif app_id == "ntm":
            # pasta de backup já criada; nada mais a escrever
            pass

        elif app_id == "cart_flasher":
            readme = _join_mount(mount_path, "cart-backups", "LEIA-ME.txt")
            _write_text_if_missing(
                readme,
                (
                    "Backups e logs do Cart-Flasher.\n"
                    "Em caso de problema: pressione Y até DEBUG e guarde cart_flasher.log.\n"
                    "AVISO: alterar banner pode bloquear a flashcart em DSi/3DS stock.\n"
                ),
                log,
                label="/cart-backups/LEIA-ME.txt",
            )

    except Exception as e:
        return False, f"Falha ao configurar {app['title']}: {e}", notes

    msg = (
        f"{app['title']} instalado em /roms/apps/{dest_name}"
        + (f" (+ {len(created) - 1} itens de configuração)" if len(created) > 1 else "")
    )
    return True, msg, notes


def notes_for(app_id: str) -> List[str]:
    return list(SETUP_NOTES.get(app_id, []))
