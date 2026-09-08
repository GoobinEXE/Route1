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
    """Lê o cabeçalho de uma ROM .nds/.dsi para extrair título, Game Code e unitcode."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(0x200)
            if len(header) < 0x20:
                return None, None, None
            raw_title = header[0:12].decode("latin1", errors="ignore").rstrip("\x00").strip()
            game_code = header[12:16].decode("latin1", errors="ignore").strip()
            unitcode = header[0x12]
            return raw_title, game_code, unitcode
    except Exception:
        return None, None, None


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


def detect_platform(file_path, filename, ext, header_info=None):
    """
    Detecta a pasta de plataforma TWiLight para um arquivo de jogo.
    .nds com unitcode DSi Exclusive (2) → dsi; demais .nds → nds.
    Extensões ambíguas (.bin/.rom) usam a pasta de origem se já for uma plataforma conhecida.

    header_info: tupla opcional (raw_title, game_code, unitcode) para evitar
    releitura do cabeçalho NDS.
    """
    parent = os.path.basename(os.path.dirname(file_path)).lower()

    if ext in (".nds", ".ids"):
        if header_info is None:
            header_info = get_nds_header_info(file_path)
        unitcode = header_info[2] if header_info else None
        # 0 = NDS, 1 = DSi Enhanced (ainda vai em nds), 2 = DSi Exclusive / DSiWare
        if unitcode == 2:
            return "dsi"
        return "nds"

    if ext in (".dsi", ".app"):
        return "dsi"

    mapped = PLATFORM_BY_EXT.get(ext)
    if mapped:
        return mapped

    # Extensões ambíguas: respeitar pasta de origem se já for plataforma conhecida
    known_folders = set(PLATFORM_BY_EXT.values()) - {None}
    known_folders |= {"dsiware", "nds", "gba", "gb", "gbc", "nes", "snes", "gen", "sms", "gg"}
    if parent in known_folders:
        return "dsi" if parent == "dsiware" else parent

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
    Varre o cartão SD, identifica a plataforma de cada jogo e organiza em
    /roms/<plataforma>/ (padrão TWiLight Menu++), com saves ao lado ou em /saves/.
    """
    log = lambda msg: emit_log(log_callback, msg)

    log(f"=== Organização por plataforma em: {mount_path} ===")

    if not os.path.exists(mount_path):
        return False, f"Diretório {mount_path} não existe."

    roms_root = os.path.join(mount_path, "roms")
    os.makedirs(roms_root, exist_ok=True)

    # Coletar ROMs, saves e lixo em um único walk
    rom_candidates = []  # (name, full_path, ext, platform, game_code)
    sav_candidates = []
    junk_paths = []
    empty_dir_candidates = []

    for root, dirs, files in os.walk(mount_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")]

        under_roms = root.startswith(roms_root)
        skip_root = _is_under_skip(root, mount_path) and root != mount_path

        for f in files:
            full_path = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()

            # Lixo: coletar agora (evita segundo walk)
            if f.startswith("._") or f == ".DS_Store" or ext in JUNK_EXTS:
                if under_roms or (
                    root != mount_path and not skip_root and not _is_under_skip(full_path, mount_path)
                ):
                    junk_paths.append(full_path)
                continue

            if skip_root or _is_under_skip(full_path, mount_path):
                continue

            low_name = f.lower()
            if root.rstrip("/\\") == mount_path.rstrip("/\\"):
                if low_name in {
                    "boot.nds",
                    "dumptool.nds",
                    "twilightmenu.nds",
                    "unlaunch-installer.dsi",
                    "_ds_menu.dat",
                    "_ds_mshl.nds",
                }:
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
                if ext in (".nds", ".dsi", ".ids", ".app"):
                    header_info = get_nds_header_info(full_path)
                    game_code = header_info[1]
                platform = detect_platform(full_path, f, ext, header_info=header_info)
                if platform:
                    rom_candidates.append((f, full_path, ext, platform, game_code))

        # Marcar pastas potencialmente vazias para limpeza posterior
        for d in list(dirs):
            empty_dir_candidates.append(os.path.join(root, d))

    by_plat = {}
    for _, _, _, plat, _ in rom_candidates:
        by_plat[plat] = by_plat.get(plat, 0) + 1

    summary = ", ".join(f"{n} {p}" for p, n in sorted(by_plat.items())) or "nenhum"
    log(f"Encontrados: {len(rom_candidates)} jogos ({summary}) e {len(sav_candidates)} saves.")

    saves_by_stem = {}
    for sav_name, sav_path, sav_ext in sav_candidates:
        stem = os.path.splitext(sav_name)[0]
        saves_by_stem.setdefault(stem.lower(), []).append((sav_name, sav_path, sav_ext))

    handled_saves = set()
    organized_count = 0
    matched_saves_count = 0
    counts_moved = {}

    for original_name, full_path, ext, platform, game_code in rom_candidates:
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
            if os.path.abspath(full_path) != os.path.abspath(new_rom_path):
                log(f"🎮 [{platform}] {original_name} ➔ /roms/{platform}/{os.path.basename(new_rom_path)}")
            else:
                log(f"🎮 [{platform}] {os.path.basename(new_rom_path)} (já no lugar)")
            organized_count += 1
            counts_moved[platform] = counts_moved.get(platform, 0) + 1
        except Exception as e:
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
            pass

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

    log("✅ Organização por plataforma finalizada!")
    if counts_moved:
        for plat, n in sorted(counts_moved.items()):
            log(f"   - /roms/{plat}/ → {n} jogo(s)")
    log(f"   - {organized_count} jogos organizados no total.")
    log(f"   - {matched_saves_count} saves sincronizados com os jogos.")
    if orphan_count > 0:
        log(f"   - {orphan_count} saves avulsos em /roms/saves/.")
    log(f"   - {deleted_junk} arquivos inúteis removidos.")

    detail = ", ".join(f"{n} {p}" for p, n in sorted(counts_moved.items())) or "0"
    return True, f"{organized_count} jogos organizados por plataforma ({detail}); {matched_saves_count} saves sincronizados."
