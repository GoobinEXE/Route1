import os
import re
import shutil

from core.logging_util import emit_log

# Dicionário de títulos oficiais conhecidos por Game Code (4 caracteres no cabeçalho NDS)
KNOWN_GAME_CODES = {
    "AMCE": "Mario Kart DS",
    "YLGE": "LEGO Star Wars - The Complete Saga",
    "YLJE": "LEGO Indiana Jones - The Original Adventures",
    "ACVE": "Castlevania - Dawn of Sorrow",
    "ADME": "Animal Crossing - Wild World",
    "AWRE": "Advance Wars - Dual Strike",
    "AEKE": "Age of Empires - The Age of Kings",
    "YF4E": "Final Fantasy IV",
    "AXFE": "Final Fantasy XII - Revenant Wings",
    "AFXE": "Final Fantasy Crystal Chronicles - Rings of Fate",
    "ANDE": "Brain Age",
    "AYAE": "Big Brain Academy",
    "ABME": "Bomberman (US)",
    "ABMP": "Bomberman (EU)",
    "CR8P": "Crash - Mind Over Mutant",
    "AQJP": "Crash of the Titans",
    "YKFH": "Kung Fu Panda",
    "YQ3H": "Shrek - Ogres & Dronkeys",
    "AS3P": "Shrek SuperSlam",
    "ASQP": "Sudoku Master",
    "YWZP": "Zubo",
    "BEGP": "Jewel Master - Cradle of Egypt",
    "CRAX": "Jewel Master - Cradle of Rome",
    "YJQX": "Jewel Quest - Expeditions",
    "AU5P": "Uno 52",
    "AGEE": "GoldenEye - Rogue Agent",
    "AI8E": "Brothers in Arms DS",
    "YAHE": "Assassins Creed - Altairs Chronicles",
    "YYKE": "Trauma Center - Under the Knife 2",
    "YISE": "My Spanish Coach",
    "A2WE": "The Chronicles of Narnia",
    "AHBE": "4 Game Fun Pack - Monopoly, Boggle, Yahtzee, Battleship",
    "CEOD": "Emergency DS",
    "YKTJ": "Taiko no Tatsujin DS",
    "CW8E": "Winter Sports 2 - The Next Challenge",
    "CM5P": "Monster Jam - Urban Assault",
    "CMLE": "Major League Baseball 2K9",
    "YTLH": "THINK - Train Your Brain",
    "A2DE": "New Super Mario Bros",
    "APAE": "Pokemon Pearl",
    "ADAE": "Pokemon Diamond",
    "CPUE": "Pokemon Platinum",
    "IPKE": "Pokemon HeartGold",
    "IPGE": "Pokemon SoulSilver",
    "IRAE": "Pokemon Black",
    "IRBO": "Pokemon White",
    "AZLE": "The Legend of Zelda - Phantom Hourglass",
    "BKIE": "The Legend of Zelda - Spirit Tracks",
    "CSME": "Super Mario 64 DS",
    "CLJE": "Mario & Luigi - Bowsers Inside Story",
    "ARME": "Mario & Luigi - Partners in Time",
    "B3RE": "Pokemon Ranger",
    "CRFE": "Chrono Trigger",
}

# Extensão → pasta TWiLight Menu++ (/roms/<plataforma>/)
# Pastas alinhadas ao padrão do TWiLight / Universal-DB
PLATFORM_BY_EXT = {
    ".nds": "nds",
    ".dsi": "dsi",
    ".ids": "nds",
    ".app": "dsi",
    ".gba": "gba",
    ".agb": "gba",
    ".mb": "gba",
    ".gb": "gb",
    ".gbc": "gbc",
    ".sgb": "gb",
    ".nes": "nes",
    ".fds": "fds",
    ".unf": "nes",
    ".smc": "snes",
    ".sfc": "snes",
    ".fig": "snes",
    ".md": "gen",
    ".gen": "gen",
    ".smd": "gen",
    ".bin": None,  # ambíguo — resolvido por pasta de origem
    ".sms": "sms",
    ".gg": "gg",
    ".sg": "sg",
    ".pce": "pce",
    ".sgx": "pce",
    ".a26": "a26",
    ".a52": "a52",
    ".a78": "a78",
    ".col": "col",
    ".msx": "msx",
    ".rom": None,  # ambíguo
    ".ngp": "ngp",
    ".ngc": "ngp",
    ".ws": "ws",
    ".wsc": "ws",
    ".xex": "xex",
    ".atr": "xex",
}

# Pastas do sistema / CFW que nunca devem ser varridas como “jogos soltos”
SKIP_DIR_NAMES = {
    "_nds",
    "_SYSTEM_",
    "MOONSHL",
    "title",
    "private",
    "DCIM",
    "Nintendo DSi",
    "System Volume Information",
    ".Trash",
    ".Trashes",
    ".fseventsd",
    ".Spotlight-V100",
}

SAVE_EXTS = {".sav", ".srm", ".sa1", ".sa2", ".duc", ".dss", ".dsv", ".mcr", ".eep", ".fla", ".rtc"}

JUNK_EXTS = {".nfo", ".sfv", ".diz", ".jpg", ".jpeg", ".png", ".cc", ".db", ".txt", ".url", ".html", ".htm"}


def get_nds_header_info(file_path):
    """
    Lê o cabeçalho NDS: título, Game Code, unitcode, maker code.
    Retorna (raw_title, game_code, unitcode, maker_code) ou Nones.
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(0x200)
            if len(header) < 0x20:
                return None, None, None, None
            raw_title = header[0:12].decode("latin1", errors="ignore").rstrip("\x00").strip()
            game_code = header[12:16].decode("latin1", errors="ignore").rstrip("\x00")
            maker_code = header[0x10:0x12].decode("latin1", errors="ignore").rstrip("\x00")
            unitcode = header[0x12]
            return raw_title, game_code, unitcode, maker_code
    except Exception:
        return None, None, None, None


# Bootloaders / instaladores na raiz do SD — nunca reorganizar.
SYSTEM_ROOT_NAMES = frozenset(
    {
        "boot.nds",
        "dumptool.nds",
        "twilightmenu.nds",
        "unlaunch-installer.dsi",
        "unlaunch.dsi",
        "_ds_menu.dat",
        "_ds_mshl.nds",
        "godmode9i.nds",
        "godmode9i.dsi",
    }
)

# Nomes tipicamente homebrew/utilitário (comparação sem extensão, lower).
KNOWN_APP_STEMS = frozenset(
    {
        "godmode9i",
        "godmode9",
        "ftpd",
        "nds-hb-menu",
        "hbmenu",
        "dumptool",
        "nitrohax",
        "wooddumper",
        "twlmagick",
        "hiyacfw",
        "nandtitlemanager",
        "ntm",
        "cart_flasher",
        "cart-flasher",
        "dsfetch",
        "rocketvideoplayer",
        "fastvideods",
        "kekatsu",
        "dsidl",
        "ds-micpassthrough",
        "dsmicpassthrough",
        "savedumper",
        "ndsi-savedumper",
        "pkmn-chest",
        "pkmnchest",
    }
)


def _is_nullish_code(code: str) -> bool:
    if not code:
        return True
    cleaned = code.replace("\x00", "").strip()
    if not cleaned:
        return True
    low = cleaned.lower()
    return low in ("####", "0000", "00", "0", "null", "home")


def classify_nds_kind(title, game_code, maker_code, filename, *, at_sd_root=False):
    """
    Classifica um .nds/.dsi: 'system' | 'app' | 'game'.
    system = bootloaders na raiz; app = homebrew; game = comercial / DSiWare.
    """
    base = os.path.basename(filename or "")
    low = base.lower()
    stem = os.path.splitext(low)[0]

    if at_sd_root and low in SYSTEM_ROOT_NAMES:
        return "system"
    if low in SYSTEM_ROOT_NAMES or stem in KNOWN_APP_STEMS:
        # GodMode9i etc. na raiz = system; noutros sítios = app.
        if at_sd_root and low.startswith("godmode9i"):
            return "system"
        if stem in KNOWN_APP_STEMS or low.startswith("godmode9i"):
            return "app"

    maker = (maker_code or "").replace("\x00", "").strip()
    code = (game_code or "").replace("\x00", "").strip()

    if _is_nullish_code(maker) or _is_nullish_code(code):
        return "app"

    # Maker / game code tipicamente comerciais: alfanuméricos ASCII.
    if (
        len(code) == 4
        and code.isalnum()
        and code.isascii()
        and len(maker) == 2
        and maker.isalnum()
        and maker.isascii()
    ):
        return "game"

    # Códigos estranhos → tratar como app para não misturar com a lista de jogos.
    return "app"


def clean_rom_filename(filename, game_code=None):
    """
    Limpa o nome de arquivo de uma ROM, removendo tags de cena,
    números de lançamento e propagandas de sites.
    """
    if game_code and game_code in KNOWN_GAME_CODES:
        return KNOWN_GAME_CODES[game_code]

    name, _ = os.path.splitext(filename)

    name = re.sub(r"^\d{4}\s*-\s*", "", name)
    name = re.sub(r"\[.*?\]", "", name)
    name = re.sub(r"\((?:U|E|US|EU|J|PROPER|REPACK|v\d+\.\d+)\)", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    # Caracteres inválidos em FAT
    name = re.sub(r'[<>:"/\\|?*]', "", name).strip(" .")

    return name if name else os.path.splitext(filename)[0]


def detect_platform(file_path, filename, ext, header_info=None, kind=None):
    """
    Detecta a pasta de plataforma TWiLight para um arquivo de jogo.
    Jogos NDS/DSi → sempre 'nds' (lista flat, acesso rápido).
    Apps NDS → 'apps'.
    Extensões ambíguas (.bin/.rom) usam a pasta de origem se já for uma plataforma conhecida.

    header_info: tupla (raw_title, game_code, unitcode, maker_code).
    kind: 'game' | 'app' | None (não-NDS).
    """
    parent = os.path.basename(os.path.dirname(file_path)).lower()

    if ext in (".nds", ".ids", ".dsi", ".app"):
        if kind == "app":
            return "apps"
        # Jogos (incluindo DSiWare / unitcode 2) → /roms/nds/ flat
        return "nds"

    mapped = PLATFORM_BY_EXT.get(ext)
    if mapped:
        return mapped

    # Extensões ambíguas: respeitar pasta de origem se já for plataforma conhecida
    known_folders = set(PLATFORM_BY_EXT.values()) - {None}
    known_folders |= {"dsiware", "nds", "gba", "gb", "gbc", "nes", "snes", "gen", "sms", "gg", "apps"}
    if parent in known_folders:
        if parent == "dsiware":
            return "nds"
        if parent == "dsi":
            return "nds"
        return parent

    if ext == ".bin":
        return "gen"  # comum em dumps de Mega Drive
    if ext == ".rom":
        return "msx"

    return None


def _is_under_skip(path, mount_path):
    """True se o caminho passa por pasta de sistema/CFW que não deve ser reorganizada."""
    try:
        rel = os.path.relpath(path, mount_path)
    except ValueError:
        return True
    parts = rel.replace("\\", "/").split("/")
    for part in parts[:-1]:  # ignora o nome do arquivo
        if part in SKIP_DIR_NAMES or part.startswith("."):
            return True
    return False


def _unique_path(dest_path):
    """Evita sobrescrever: adiciona (2), (3)... se já existir."""
    if not os.path.exists(dest_path):
        return dest_path
    base, ext = os.path.splitext(dest_path)
    n = 2
    while True:
        candidate = f"{base} ({n}){ext}"
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _safe_move(src, dst):
    if os.path.abspath(src) == os.path.abspath(dst):
        return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    dst = _unique_path(dst)
    shutil.move(src, dst)
    return dst


def organize_roms_directory(mount_path, log_callback=None):
    """
    Varre o cartão SD: jogos NDS/DSi → /roms/nds/ (flat); homebrew → /roms/apps/;
    outras plataformas → /roms/<plat>/; saves ao lado ou em /roms/saves/.
    """
    log = lambda msg: emit_log(log_callback, msg)

    log(f"=== Organização (jogos flat + apps) em: {mount_path} ===")

    if not os.path.exists(mount_path):
        return False, f"Diretório {mount_path} não existe."

    roms_root = os.path.join(mount_path, "roms")
    os.makedirs(roms_root, exist_ok=True)

    # Coletar ROMs, saves e lixo em um único walk
    # (name, full_path, ext, platform, game_code, kind)
    rom_candidates = []
    sav_candidates = []
    junk_paths = []
    empty_dir_candidates = []

    mount_norm = mount_path.rstrip("/\\")

    for root, dirs, files in os.walk(mount_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")]

        under_roms = root.startswith(roms_root)
        skip_root = _is_under_skip(root, mount_path) and root != mount_path
        at_sd_root = root.rstrip("/\\") == mount_norm

        for f in files:
            full_path = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()

            # Lixo: apenas dentro de /roms/ (nunca apagar .txt/.jpg fora dali)
            if f.startswith("._") or f == ".DS_Store" or ext in JUNK_EXTS:
                if under_roms:
                    junk_paths.append(full_path)
                continue

            if skip_root or _is_under_skip(full_path, mount_path):
                continue

            low_name = f.lower()
            if at_sd_root and low_name in SYSTEM_ROOT_NAMES:
                continue

            if ext in SAVE_EXTS:
                sav_candidates.append((f, full_path, ext))
                continue

            if ext in (".bin", ".rom"):
                try:
                    rel = os.path.relpath(full_path, roms_root)
                    if rel.startswith(".."):
                        continue
                except ValueError:
                    continue

            if ext in PLATFORM_BY_EXT:
                header_info = None
                game_code = None
                kind = None
                if ext in (".nds", ".dsi", ".ids", ".app"):
                    header_info = get_nds_header_info(full_path)
                    game_code = header_info[1]
                    maker_code = header_info[3]
                    title = header_info[0]
                    kind = classify_nds_kind(
                        title, game_code, maker_code, f, at_sd_root=at_sd_root
                    )
                    if kind == "system":
                        continue
                platform = detect_platform(
                    full_path, f, ext, header_info=header_info, kind=kind
                )
                if platform:
                    rom_candidates.append((f, full_path, ext, platform, game_code, kind))

        # Marcar pastas potencialmente vazias para limpeza posterior
        for d in list(dirs):
            empty_dir_candidates.append(os.path.join(root, d))

    by_plat = {}
    for _, _, _, plat, _, _ in rom_candidates:
        by_plat[plat] = by_plat.get(plat, 0) + 1

    summary = ", ".join(f"{n} {p}" for p, n in sorted(by_plat.items())) or "nenhum"
    log(f"Encontrados: {len(rom_candidates)} ficheiros ({summary}) e {len(sav_candidates)} saves.")

    saves_by_stem = {}
    for sav_name, sav_path, sav_ext in sav_candidates:
        stem = os.path.splitext(sav_name)[0]
        saves_by_stem.setdefault(stem.lower(), []).append((sav_name, sav_path, sav_ext))

    handled_saves = set()
    organized_count = 0
    matched_saves_count = 0
    move_failures = 0
    counts_moved = {}

    for original_name, full_path, ext, platform, game_code, kind in rom_candidates:
        if not os.path.exists(full_path):
            continue

        clean_name = clean_rom_filename(original_name, game_code)
        out_ext = ext if ext else ".nds"
        if out_ext == ".ids":
            out_ext = ".nds"
        if out_ext == ".app":
            out_ext = ".dsi"

        platform_dir = os.path.join(roms_root, platform)
        os.makedirs(platform_dir, exist_ok=True)

        target_rom = os.path.join(platform_dir, f"{clean_name}{out_ext}")
        try:
            new_rom_path = _safe_move(full_path, target_rom)
            label = "app" if platform == "apps" or kind == "app" else "jogo"
            if os.path.abspath(full_path) != os.path.abspath(new_rom_path):
                log(
                    f"🎮 [{platform}/{label}] {original_name} ➔ "
                    f"/roms/{platform}/{os.path.basename(new_rom_path)}"
                )
            else:
                log(f"🎮 [{platform}] {os.path.basename(new_rom_path)} (já no lugar)")
            organized_count += 1
            counts_moved[platform] = counts_moved.get(platform, 0) + 1
        except Exception as e:
            move_failures += 1
            log(f"⚠️ Falha ao mover {original_name}: {e}")
            continue

        stem_original = os.path.splitext(original_name)[0]
        final_stem = os.path.splitext(os.path.basename(new_rom_path))[0]
        for key in {stem_original.lower(), clean_name.lower(), final_stem.lower()}:
            for sav_name, sav_path, sav_ext in saves_by_stem.get(key, []):
                if sav_path in handled_saves or not os.path.exists(sav_path):
                    continue
                target_sav = os.path.join(platform_dir, f"{final_stem}{sav_ext}")
                try:
                    _safe_move(sav_path, target_sav)
                    handled_saves.add(sav_path)
                    matched_saves_count += 1
                    log(f"💾 Save ➔ /roms/{platform}/{final_stem}{sav_ext}")
                except Exception as e:
                    move_failures += 1
                    log(f"⚠️ Falha ao mover save {sav_name}: {e}")

    orphan_dir = os.path.join(roms_root, "saves")
    orphan_count = 0
    for sav_name, sav_path, sav_ext in sav_candidates:
        if sav_path in handled_saves or not os.path.exists(sav_path):
            continue
        try:
            rel = os.path.relpath(sav_path, roms_root)
            parts = rel.replace("\\", "/").split("/")
            if len(parts) == 2 and parts[0] != "saves":
                continue
        except ValueError:
            pass
        os.makedirs(orphan_dir, exist_ok=True)
        try:
            _safe_move(sav_path, os.path.join(orphan_dir, sav_name))
            orphan_count += 1
        except Exception:
            move_failures += 1

    deleted_junk = 0
    for p in junk_paths:
        if not os.path.exists(p):
            continue
        try:
            os.remove(p)
            deleted_junk += 1
        except Exception:
            pass

    # Remover pastas vazias (mais profundas primeiro)
    for p in sorted(empty_dir_candidates, key=lambda x: x.count(os.sep), reverse=True):
        if not os.path.isdir(p):
            continue
        base = os.path.basename(p)
        if base in SKIP_DIR_NAMES or base.startswith("."):
            continue
        try:
            os.rmdir(p)
        except Exception:
            pass

    log("✅ Organização finalizada!")
    if counts_moved:
        for plat, n in sorted(counts_moved.items()):
            log(f"   - /roms/{plat}/ → {n} ficheiro(s)")
    log(f"   - {organized_count} organizados no total.")
    log(f"   - {matched_saves_count} saves sincronizados.")
    if orphan_count > 0:
        log(f"   - {orphan_count} saves avulsos em /roms/saves/.")
    log(f"   - {deleted_junk} arquivos inúteis removidos.")
    if move_failures:
        log(f"   - ⚠️ {move_failures} falha(s) ao mover (cartão pode estar parcialmente organizado).")

    detail = ", ".join(f"{n} {p}" for p, n in sorted(counts_moved.items())) or "0"
    msg = (
        f"{organized_count} itens organizados ({detail}); "
        f"{matched_saves_count} saves sincronizados. "
        "Jogos em /roms/nds/; apps em /roms/apps/."
    )
    if move_failures and organized_count == 0 and rom_candidates:
        return False, f"Organização falhou ({move_failures} erro(s)). {msg}"
    if move_failures:
        return True, f"{msg} ({move_failures} item(ns) falharam — verifique o log.)"
    return True, msg
