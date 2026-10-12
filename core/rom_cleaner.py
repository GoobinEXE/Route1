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

# Layouts de organização (escolha do utilizador)
LAYOUT_CONSOLE = "console"  # /roms/<plat>/jogo — padrão TWiLight
LAYOUT_FRANCHISE = "franchise"  # /roms/<franquia>/jogo
LAYOUT_BOTH = "both"  # /roms/<plat>/<franquia>/jogo
LAYOUT_MODES = frozenset({LAYOUT_CONSOLE, LAYOUT_FRANCHISE, LAYOUT_BOTH})
LAYOUT_ALIASES = {
    "platform": LAYOUT_CONSOLE,
    "plataforma": LAYOUT_CONSOLE,
    "franquia": LAYOUT_FRANCHISE,
    "series": LAYOUT_FRANCHISE,
    "ambos": LAYOUT_BOTH,
    "console_franchise": LAYOUT_BOTH,
    "platform_then_franchise": LAYOUT_BOTH,
}
UNKNOWN_FRANCHISE = "Outros"

# Franquia por Game Code NDS (quando o título limpo não chega)
FRANCHISE_BY_CODE = {
    "AMCE": "Mario",
    "A2DE": "Mario",
    "CSME": "Mario",
    "CLJE": "Mario",
    "ARME": "Mario",
    "APAE": "Pokemon",
    "ADAE": "Pokemon",
    "CPUE": "Pokemon",
    "IPKE": "Pokemon",
    "IPGE": "Pokemon",
    "IRAE": "Pokemon",
    "IRBO": "Pokemon",
    "B3RE": "Pokemon",
    "AZLE": "Zelda",
    "BKIE": "Zelda",
    "ADME": "Animal Crossing",
    "ACVE": "Castlevania",
    "YF4E": "Final Fantasy",
    "AXFE": "Final Fantasy",
    "AFXE": "Final Fantasy",
    "AWRE": "Advance Wars",
    "CRFE": "Chrono",
    "YLGE": "LEGO",
    "YLJE": "LEGO",
    "CR8P": "Crash",
    "AQJP": "Crash",
    "YAHE": "Assassins Creed",
    "AGEE": "James Bond",
    "ABME": "Bomberman",
    "ABMP": "Bomberman",
    "ANDE": "Brain Training",
    "AYAE": "Brain Training",
    "YYKE": "Trauma Center",
    "YQ3H": "Shrek",
    "AS3P": "Shrek",
}

# Padrões no nome (ordem = prioridade). Pastas FAT-safe.
_FRANCHISE_PATTERN_SPECS = (
    (r"pok[eé]mon|pkmn|vers[aã]o\s*(azul|vermelha?|amarela|cristal|ouro|prata)|rede\s*de\s*batalha", "Pokemon"),
    (r"mario\s*&\s*luigi|new\s*super\s*mario|super\s*mario|mario\s*kart|mario\s*party|\bmario\b|\bluigi\b|yoshi|wario(?!\s*ware)|donkey\s*kong", "Mario"),
    (r"wario\s*ware|warioware", "WarioWare"),
    (r"zelda|phantom\s*hourglass|spirit\s*tracks|minish\s*cap|link'?s?\s*awakening|oracle\s*of\s*(ages|seasons)|a\s*link\s*to\s*the\s*past", "Zelda"),
    (r"kirby", "Kirby"),
    (r"metroid", "Metroid"),
    (r"animal\s*crossing", "Animal Crossing"),
    (r"castlevania", "Castlevania"),
    (r"final\s*fantasy", "Final Fantasy"),
    (r"fire\s*emblem", "Fire Emblem"),
    (r"mega\s*man|rockman|battle\s*network", "Mega Man"),
    (r"\bsonic\b", "Sonic"),
    (r"dragon\s*quest", "Dragon Quest"),
    (r"ace\s*attorney|phoenix\s*wright|gyakuten", "Ace Attorney"),
    (r"professor\s*layton|\blayton\b", "Professor Layton"),
    (r"harvest\s*moon|story\s*of\s*seasons|rune\s*factory", "Harvest Moon"),
    (r"\blego\b", "LEGO"),
    (r"\bcrash\b", "Crash"),
    (r"\bspyro\b", "Spyro"),
    (r"tony\s*hawk", "Tony Hawk"),
    (r"need\s*for\s*speed|\bnfs\b", "Need for Speed"),
    (r"grand\s*theft\s*auto|\bgta\b", "Grand Theft Auto"),
    (r"call\s*of\s*duty|\bcod\b", "Call of Duty"),
    (r"assassin'?s?\s*creed", "Assassins Creed"),
    (r"resident\s*evil|biohazard", "Resident Evil"),
    (r"silent\s*hill", "Silent Hill"),
    (r"kingdom\s*hearts", "Kingdom Hearts"),
    (r"chrono\s*trigger|chrono\s*cross", "Chrono"),
    (r"bomberman", "Bomberman"),
    (r"advance\s*wars", "Advance Wars"),
    (r"brain\s*age|brain\s*training|dr\.?\s*kawashima", "Brain Training"),
    (r"nintendogs", "Nintendogs"),
    (r"cooking\s*mama", "Cooking Mama"),
    (r"style\s*savvy|girls\s*mode", "Style Savvy"),
    (r"trauma\s*center", "Trauma Center"),
    (r"yu-?gi-?oh", "Yu-Gi-Oh"),
    (r"digimon", "Digimon"),
    (r"\bnaruto\b", "Naruto"),
    (r"one\s*piece", "One Piece"),
    (r"dragon\s*ball", "Dragon Ball"),
    (r"\bshrek\b", "Shrek"),
    (r"\bbarbie\b", "Barbie"),
    (r"ben\s*10", "Ben 10"),
    (r"spider-?man|spiderman", "Spider-Man"),
    (r"\bbatman\b", "Batman"),
    (r"star\s*wars", "Star Wars"),
    (r"james\s*bond|goldeneye|\b007\b", "James Bond"),
    (r"the\s*sims|\bsims\b", "The Sims"),
    (r"\btetris\b", "Tetris"),
    (r"pac-?man", "Pac-Man"),
    (r"\brayman\b", "Rayman"),
    (r"prince\s*of\s*persia", "Prince of Persia"),
    (r"tomb\s*raider", "Tomb Raider"),
    (r"metal\s*gear", "Metal Gear"),
    (r"\bdisney\b", "Disney"),
)

FRANCHISE_PATTERNS = tuple(
    (re.compile(pat, re.IGNORECASE), name) for pat, name in _FRANCHISE_PATTERN_SPECS
)

# Extensão → pasta TWiLight Menu++ (/roms/<plataforma>/)
# Pastas alinhadas ao add-on Virtual Console (DSi/Flashcard) + base TWiLight
PLATFORM_BY_EXT = {
    ".nds": "nds",
    ".dsi": "dsi",
    ".ids": "nds",
    ".srl": "nds",
    ".app": "dsi",
    ".gba": "gba",
    ".agb": "gba",
    ".mb": "gba",
    ".gb": "gb",
    ".gbc": "gbc",
    ".sgb": "gb",
    ".nes": "nes",
    ".fds": "nes",  # Famicom Disk System — pasta oficial é /roms/nes/
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
    ".pce": "tg16",  # PC Engine / TurboGrafx-16 (pasta oficial do VC)
    ".sgx": "tg16",
    ".a26": "a26",
    ".a52": "a52",
    ".a78": "a78",
    ".col": "col",
    ".msx": "msx",
    ".m5": "m5",
    ".int": "int",
    ".dsk": "cpc",
    ".min": "min",  # Pokémon Mini (PokeMini)
    ".rom": None,  # ambíguo
    ".ngp": "ngp",
    ".ngc": "ngp",
    ".ws": "ws",
    ".wsc": "ws",
    ".xex": "xex",
    ".atr": "xex",
}

# Pastas /roms/ a criar no SD (base TWiLight + Virtual Console + extras)
# Fonte: AddOn-VirtualConsole-DSi-Flashcard + TWiLightMenu-DSi + emuladores no add-on
TWILIGHT_ROM_FOLDERS = (
    # Base
    "nds",
    "gba",
    "dsi",
    # Game Boy (oficial mistura GB/GBC/SGB em gb; gbc fica como alias útil)
    "gb",
    "gbc",
    # Virtual Console (pastas do add-on oficial)
    "nes",
    "snes",
    "gen",
    "gg",
    "sms",
    "sg",
    "a26",
    "a52",
    "a78",
    "col",
    "cpc",
    "m5",
    "ngp",
    "tg16",
    "ws",
    # Emuladores no add-on sem pasta no zip / aliases
    "int",
    "msx",
    "xex",
    "min",
    "pce",  # alias legado → preferir tg16 ao organizar
    "fds",
    # Utilitários
    "apps",
    "bios",
    "saves",
)

# Pastas do sistema / CFW que nunca devem ser varridas como “jogos soltos”
SKIP_DIR_NAMES = {
    "_nds",
    "_pico",
    "_SYSTEM_",
    "MOONSHL",
    "title",
    "ticket",
    "sys",
    "shared1",
    "shared2",
    "hiya",
    "photo",
    "private",
    "DCIM",
    "Nintendo DSi",
    "System Volume Information",
    ".Trash",
    ".Trashes",
    ".fseventsd",
    ".Spotlight-V100",
}

# Saves de bateria / SRAM (NDS, GBA, GameYob, nesDS, SNEmulDS, jEnesis, …)
SAVE_EXTS = {
    ".sav",
    ".srm",
    ".sa1",
    ".sa2",
    ".duc",
    ".dss",
    ".dsv",
    ".mcr",
    ".eep",
    ".fla",
    ".rtc",
    ".pub",  # DSiWare
    ".prv",
    # GameYob save states (ao lado da ROM)
    ".yss",
    ".ys0",
    ".ys1",
    ".ys2",
    ".ys3",
    ".ys4",
    ".ys5",
    ".ys6",
    ".ys7",
    ".ys8",
    ".ys9",
}

# Sidecars com o mesmo stem (cheats, hashes, configs) — movidos com a ROM
EXTRA_SIDECAR_EXTS = frozenset({".sha1", ".md5", ".cht", ".xml", ".dpi", ".cfg"})

JUNK_EXTS = {".nfo", ".sfv", ".diz", ".jpg", ".jpeg", ".png", ".cc", ".db", ".txt", ".url", ".html", ".htm"}


def is_save_ext(ext: str) -> bool:
    """True para saves/SRAM/estados de emulador (incl. GameYob .yss / .ysN)."""
    if not ext or not isinstance(ext, str):
        return False
    low = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    if low in SAVE_EXTS:
        return True
    # .ysN futuros / variantes
    if len(low) == 4 and low.startswith(".ys") and low[3].isdigit():
        return True
    return False


def is_companion_ext(ext: str) -> bool:
    """Save ou sidecar que deve seguir a ROM na organização."""
    if not ext or not isinstance(ext, str):
        return False
    low = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    return is_save_ext(low) or low in EXTRA_SIDECAR_EXTS


def companion_index_keys(filename: str):
    """
    Pares (stem_lower, suffix) para indexar um sidecar.
    Cobre S8DS: Pokemon.gg.sav ↔ ROM Pokemon.gg (suffix .sav) e Pokemon (suffix .gg.sav).
    """
    if not filename or not isinstance(filename, str):
        return []
    stem, ext = os.path.splitext(filename)
    ext_l = ext.lower()
    if not is_companion_ext(ext_l):
        return []
    keys = [(stem.lower(), ext_l)]
    inner, mid = os.path.splitext(stem)
    mid_l = mid.lower()
    if mid_l and PLATFORM_BY_EXT.get(mid_l):
        keys.append((inner.lower(), mid_l + ext_l))
    return keys


# Pastas de utilidade sob /roms/ — nunca apagar mesmo vazias.
UTILITY_ROM_FOLDERS = frozenset({"apps", "saves", "bios"})


def ensure_twilight_rom_folders(mount_path: str) -> list[str]:
    """Cria /roms/<pasta>/ para todas as plataformas do kit. Devolve pastas criadas."""
    roms_root = os.path.join(mount_path, "roms")
    created = []
    for name in TWILIGHT_ROM_FOLDERS:
        path = os.path.join(roms_root, name)
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            created.append(name)
        else:
            os.makedirs(path, exist_ok=True)
    return created


def ensure_layout_rom_folders(mount_path: str, layout=LAYOUT_CONSOLE) -> list[str]:
    """
    Garante pastas base conforme o layout de organização.
    - console / both: conjunto TWiLight completo (plataformas + utilitários)
    - franchise: só apps / saves / bios (franquias criadas ao mover jogos)
    """
    mode = normalize_layout(layout) or LAYOUT_CONSOLE
    if mode in (LAYOUT_CONSOLE, LAYOUT_BOTH):
        return ensure_twilight_rom_folders(mount_path)
    roms_root = os.path.join(mount_path, "roms")
    os.makedirs(roms_root, exist_ok=True)
    created = []
    for name in sorted(UTILITY_ROM_FOLDERS):
        path = os.path.join(roms_root, name)
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            created.append(name)
        else:
            os.makedirs(path, exist_ok=True)
    return created


def prune_empty_dirs(mount_path: str, layout=LAYOUT_CONSOLE, log_callback=None) -> int:
    """
    Remove pastas vazias sob o cartão (após organizar).
    Conserva /roms/, pastas de utilidade e — em layout console/both —
    pastas canónicas de plataforma directamente sob /roms/.
    Em layout franchise, pastas de consola vazias (nds, gba, …) são removidas.
    Nunca toca em pastas de sistema (SKIP_DIR_NAMES / ocultas).
    """
    log = (lambda msg: emit_log(log_callback, msg)) if log_callback else (lambda _msg: None)
    mode = normalize_layout(layout) or LAYOUT_CONSOLE

    try:
        mount_real = os.path.realpath(mount_path)
        roms_root = os.path.realpath(os.path.join(mount_path, "roms"))
    except OSError:
        return 0

    keep_roms_children = set(UTILITY_ROM_FOLDERS)
    if mode in (LAYOUT_CONSOLE, LAYOUT_BOTH):
        keep_roms_children |= set(TWILIGHT_ROM_FOLDERS)

    candidates = []
    for root, dirs, _files in os.walk(mount_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES and not d.startswith(".")]
        for d in dirs:
            candidates.append(os.path.join(root, d))

    removed = 0
    for path in sorted(candidates, key=lambda p: p.count(os.sep), reverse=True):
        if not os.path.isdir(path):
            continue
        base = os.path.basename(path)
        if base.startswith(".") or base in SKIP_DIR_NAMES:
            continue
        try:
            real = os.path.realpath(path)
            parent = os.path.realpath(os.path.dirname(path))
        except OSError:
            continue
        if real == mount_real or real == roms_root:
            continue
        # Só proteger pastas canónicas como filhos directos de /roms/
        if parent == roms_root and base in keep_roms_children:
            continue
        try:
            if os.listdir(path):
                continue
            os.rmdir(path)
            removed += 1
            try:
                rel = os.path.relpath(path, mount_path).replace("\\", "/")
            except ValueError:
                rel = base
            log(f"🧹 Pasta vazia removida: {rel}/")
        except OSError:
            pass
    return removed


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
        "hiya",
        "nandtitlemanager",
        "ntm",
        "picoboot",
        "picolauncher",
        "dspico",
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


def normalize_layout(layout):
    """Normaliza o modo de organização; default = console. None se inválido."""
    if layout is None or layout == "":
        return LAYOUT_CONSOLE
    if not isinstance(layout, str):
        return None
    low = layout.strip().lower()
    if low in LAYOUT_MODES:
        return low
    return LAYOUT_ALIASES.get(low)


def _sanitize_folder_name(name):
    """Nome de pasta seguro para FAT (sem path separators / chars inválidos)."""
    if not name or not isinstance(name, str):
        return UNKNOWN_FRANCHISE
    cleaned = re.sub(r'[<>:"/\\|?*\x00]', "", name).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60] if cleaned else UNKNOWN_FRANCHISE


def _match_franchise_patterns(text):
    if not text or not isinstance(text, str):
        return None
    for pattern, franchise in FRANCHISE_PATTERNS:
        if pattern.search(text):
            return franchise
    return None


def detect_franchise(clean_name, game_code=None, raw_title=None, original_name=None):
    """
    Infere franquia a partir do game code, título limpo ou nome do ficheiro.
    Retorna None se não houver correspondência (caller decide 'Outros' ou flat).
    """
    code = (game_code or "").replace("\x00", "").strip()
    if code and code in FRANCHISE_BY_CODE:
        return FRANCHISE_BY_CODE[code]
    if code and code in KNOWN_GAME_CODES:
        hit = _match_franchise_patterns(KNOWN_GAME_CODES[code])
        if hit:
            return hit
    for text in (clean_name, raw_title, original_name):
        hit = _match_franchise_patterns(text)
        if hit:
            return hit
    return None


def rom_dest_dir(roms_root, platform, franchise, layout):
    """
    Pasta de destino sob /roms/ conforme o layout.
    Apps ficam sempre em /roms/apps/ (flat).
    - console:   /roms/<plat>/
    - franchise: /roms/<franquia>/  (sem franquia → Outros)
    - both:      /roms/<plat>/<franquia>/  (sem franquia → flat em <plat>/)
    """
    if platform == "apps":
        return os.path.join(roms_root, "apps")

    layout = normalize_layout(layout) or LAYOUT_CONSOLE
    franchise_folder = _sanitize_folder_name(franchise) if franchise else None

    if layout == LAYOUT_FRANCHISE:
        return os.path.join(roms_root, franchise_folder or UNKNOWN_FRANCHISE)

    if layout == LAYOUT_BOTH:
        base = os.path.join(roms_root, platform)
        if franchise_folder:
            return os.path.join(base, franchise_folder)
        return base

    # console (padrão)
    return os.path.join(roms_root, platform)


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
    known_folders = {v for v in PLATFORM_BY_EXT.values() if v}
    known_folders |= set(TWILIGHT_ROM_FOLDERS)
    known_folders |= {"dsiware"}
    if parent in known_folders:
        if parent in ("dsiware", "dsi"):
            return "nds"
        if parent == "pce":
            return "tg16"
        if parent == "fds":
            return "nes"
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


def organize_roms_directory(mount_path, log_callback=None, layout=LAYOUT_CONSOLE):
    """
    Varre o cartão SD e organiza ROMs conforme o layout:
    - console:   jogos em /roms/<plat>/; apps em /roms/apps/
    - franchise: jogos em /roms/<franquia>/; apps em /roms/apps/
    - both:      jogos em /roms/<plat>/<franquia>/; apps em /roms/apps/
    Cria as pastas de destino em falta, sincroniza saves/sidecars e
    remove pastas vazias (em franchise, limpa pastas de consola vazias).
    Saves / estados GameYob (.sav, .yss, .ysN) e sidecars (.cht, …) ao lado da ROM
    ou em /roms/saves/.
    """
    log = lambda msg: emit_log(log_callback, msg)

    mode = normalize_layout(layout)
    if mode is None:
        return False, f"Layout de organização inválido: {layout!r}."

    layout_labels = {
        LAYOUT_CONSOLE: "por consola (flat)",
        LAYOUT_FRANCHISE: "por franquia",
        LAYOUT_BOTH: "consola → franquia",
    }
    log(f"=== Organização ({layout_labels.get(mode, mode)}) em: {mount_path} ===")

    if not os.path.exists(mount_path):
        return False, f"Diretório {mount_path} não existe."

    roms_root = os.path.join(mount_path, "roms")
    os.makedirs(roms_root, exist_ok=True)
    created_folders = ensure_layout_rom_folders(mount_path, mode)
    if created_folders:
        log(f"📁 Pastas base criadas: {', '.join(created_folders)}")

    # Coletar ROMs, saves/sidecars e lixo em um único walk
    # (name, full_path, ext, platform, game_code, kind, raw_title)
    rom_candidates = []
    companion_candidates = []  # (name, full_path)
    junk_paths = []

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

            if is_companion_ext(ext):
                companion_candidates.append((f, full_path))
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
                raw_title = None
                if ext in (".nds", ".dsi", ".ids", ".app", ".srl"):
                    header_info = get_nds_header_info(full_path)
                    game_code = header_info[1]
                    maker_code = header_info[3]
                    raw_title = header_info[0]
                    kind = classify_nds_kind(
                        raw_title, game_code, maker_code, f, at_sd_root=at_sd_root
                    )
                    if kind == "system":
                        continue
                platform = detect_platform(
                    full_path, f, ext, header_info=header_info, kind=kind
                )
                if platform:
                    rom_candidates.append(
                        (f, full_path, ext, platform, game_code, kind, raw_title)
                    )

    by_plat = {}
    for _, _, _, plat, _, _, _ in rom_candidates:
        by_plat[plat] = by_plat.get(plat, 0) + 1

    summary = ", ".join(f"{n} {p}" for p, n in sorted(by_plat.items())) or "nenhum"
    log(
        f"Encontrados: {len(rom_candidates)} ficheiros ({summary}) e "
        f"{len(companion_candidates)} saves/sidecars."
    )

    from core.progress import ProgressTracker

    total_bytes = 0
    for _c in rom_candidates:
        try:
            total_bytes += max(0, int(os.path.getsize(_c[1])))
        except OSError:
            pass
    tracker = ProgressTracker(
        "organize_roms",
        label="A organizar…",
        total_items=len(rom_candidates),
        total_bytes=total_bytes,
    )
    tracker.set_phase("move", label="A organizar ROMs…")

    companions_by_stem = {}
    for comp_name, comp_path in companion_candidates:
        for key, suffix in companion_index_keys(comp_name):
            companions_by_stem.setdefault(key, []).append((comp_name, comp_path, suffix))

    handled_companions = set()
    organized_count = 0
    matched_companions_count = 0
    move_failures = 0
    counts_moved = {}

    for original_name, full_path, ext, platform, game_code, kind, raw_title in rom_candidates:
        if not os.path.exists(full_path):
            tracker.advance_item(label=original_name, skipped=True)
            continue
        try:
            item_size = max(0, int(os.path.getsize(full_path)))
        except OSError:
            item_size = 0

        clean_name = clean_rom_filename(original_name, game_code)
        out_ext = ext if ext else ".nds"
        if out_ext == ".ids":
            out_ext = ".nds"
        if out_ext == ".app":
            out_ext = ".dsi"

        franchise = None
        if platform != "apps" and mode in (LAYOUT_FRANCHISE, LAYOUT_BOTH):
            franchise = detect_franchise(
                clean_name,
                game_code=game_code,
                raw_title=raw_title,
                original_name=original_name,
            )

        dest_dir = rom_dest_dir(roms_root, platform, franchise, mode)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except OSError as e:
            move_failures += 1
            log(f"⚠️ Falha ao criar pasta de destino para {original_name}: {e}")
            tracker.advance_item(
                bytes_delta=item_size, label=original_name, failed=True
            )
            continue

        target_rom = os.path.join(dest_dir, f"{clean_name}{out_ext}")
        try:
            new_rom_path = _safe_move(full_path, target_rom)
            try:
                rel_dest = os.path.relpath(new_rom_path, roms_root).replace("\\", "/")
            except ValueError:
                rel_dest = os.path.basename(new_rom_path)
            label = "app" if platform == "apps" or kind == "app" else "jogo"
            if os.path.abspath(full_path) != os.path.abspath(new_rom_path):
                log(f"🎮 [{platform}/{label}] {original_name} ➔ /roms/{rel_dest}")
            else:
                log(f"🎮 [{platform}] {rel_dest} (já no lugar)")
            organized_count += 1
            if platform == "apps":
                bucket = "apps"
            elif mode == LAYOUT_FRANCHISE:
                bucket = franchise or UNKNOWN_FRANCHISE
            elif mode == LAYOUT_BOTH and franchise:
                bucket = f"{platform}/{franchise}"
            else:
                bucket = platform
            counts_moved[bucket] = counts_moved.get(bucket, 0) + 1
            tracker.advance_item(
                bytes_delta=item_size, label=original_name, written=True
            )
        except Exception as e:
            move_failures += 1
            log(f"⚠️ Falha ao mover {original_name}: {e}")
            tracker.advance_item(
                bytes_delta=item_size, label=original_name, failed=True
            )
            continue

        rom_dir = os.path.dirname(new_rom_path)
        stem_original = os.path.splitext(original_name)[0]
        final_stem = os.path.splitext(os.path.basename(new_rom_path))[0]
        for key in {stem_original.lower(), clean_name.lower(), final_stem.lower()}:
            for comp_name, comp_path, suffix in companions_by_stem.get(key, []):
                if comp_path in handled_companions or not os.path.exists(comp_path):
                    continue
                target_comp = os.path.join(rom_dir, f"{final_stem}{suffix}")
                try:
                    new_comp = _safe_move(comp_path, target_comp)
                    handled_companions.add(comp_path)
                    matched_companions_count += 1
                    try:
                        comp_rel = os.path.relpath(new_comp, roms_root).replace("\\", "/")
                    except ValueError:
                        comp_rel = os.path.basename(new_comp)
                    kind_label = "Save" if is_save_ext(os.path.splitext(comp_name)[1]) else "Sidecar"
                    log(f"💾 {kind_label} ➔ /roms/{comp_rel}")
                except Exception as e:
                    move_failures += 1
                    log(f"⚠️ Falha ao mover {comp_name}: {e}")

    orphan_dir = os.path.join(roms_root, "saves")
    orphan_count = 0
    for comp_name, comp_path in companion_candidates:
        if comp_path in handled_companions or not os.path.exists(comp_path):
            continue
        # Só órfãos de save (não mover .cht/.sha1 soltos para saves/)
        if not is_save_ext(os.path.splitext(comp_name)[1].lower()):
            continue
        try:
            rel = os.path.relpath(comp_path, roms_root)
            parts = rel.replace("\\", "/").split("/")
            # Já sob /roms/<plat>/… (flat ou franquia) — não tratar como órfão
            if len(parts) >= 2 and parts[0] != "saves":
                continue
        except ValueError:
            pass
        os.makedirs(orphan_dir, exist_ok=True)
        try:
            _safe_move(comp_path, os.path.join(orphan_dir, comp_name))
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

    # Re-varrer e remover pastas vazias (incl. restos do layout anterior)
    removed_empty = prune_empty_dirs(mount_path, layout=mode, log_callback=log_callback)

    log("✅ Organização finalizada!")
    if counts_moved:
        for bucket, n in sorted(counts_moved.items()):
            log(f"   - /roms/{bucket}/ → {n} ficheiro(s)")
    log(f"   - {organized_count} organizados no total.")
    log(f"   - {matched_companions_count} saves/sidecars sincronizados.")
    if orphan_count > 0:
        log(f"   - {orphan_count} saves avulsos em /roms/saves/.")
    log(f"   - {deleted_junk} arquivos inúteis removidos.")
    log(f"   - {removed_empty} pasta(s) vazia(s) removida(s).")
    if move_failures:
        log(f"   - ⚠️ {move_failures} falha(s) ao mover (cartão pode estar parcialmente organizado).")

    detail = ", ".join(f"{n} {p}" for p, n in sorted(counts_moved.items())) or "0"
    if mode == LAYOUT_FRANCHISE:
        where = "Jogos em /roms/<franquia>/; apps em /roms/apps/."
    elif mode == LAYOUT_BOTH:
        where = "Jogos em /roms/<consola>/<franquia>/; apps em /roms/apps/."
    else:
        where = "Jogos em /roms/<consola>/ (incl. gb/gbc/nes/…); apps em /roms/apps/."
    msg = (
        f"{organized_count} itens organizados ({detail}); "
        f"{matched_companions_count} saves/sidecars sincronizados; "
        f"{removed_empty} pasta(s) vazia(s) removida(s). {where}"
    )
    if organized_count or matched_companions_count:
        from core.rom_manager import invalidate_rom_dup_index

        invalidate_rom_dup_index(mount_path)

    if move_failures and organized_count == 0 and rom_candidates:
        tracker.finish("Organização falhou")
        return False, f"Organização falhou ({move_failures} erro(s)). {msg}"
    if move_failures:
        tracker.finish(msg)
        return True, f"{msg} ({move_failures} item(ns) falharam — verifique o log.)"
    tracker.finish(msg)
    return True, msg
