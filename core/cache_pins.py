"""Tabelas pinadas de cache (SHA-256, URLs, nomes, tamanhos).

Carregadas sob demanda via ``core.cache`` (PEP 562) — não importar no arranque
se só precisar de ``CACHE_DIR`` / ``USER_AGENT``.
"""

from __future__ import annotations

from typing import Sequence, Union

# Valor em URLS: uma URL HTTPS ou lista ordenada de mirrors (primeira = preferida).
UrlEntry = Union[str, Sequence[str]]

PINNED_SHA256 = {
    "pit_facebook": "ca4c197ef81283ad0c802fdc39bcb6c880e2e182cb7ac5c456a68368e50bbe14",
    "pit_no_facebook": "9f2b97bfb9569723ed5c0c48f314ab8c94e56e855acb468db727b8ecf059342b",
    "dumptool": "313b255a754bda4d06d6f761a7490b4f1675c957c41676119330520cb09a47ea",
    "unlaunch": "14ba0b4af84e801206e20cffdf55002e3b4b5dd8be18abf3c0977011b23f1aeb",
    "twilight_7z": "c04fc66305ce8dc80e69aa4070d3ce966f04868881663f57b91f68d687a2bb90",
    "twilight_vc_7z": "0b205be813a8c86ecde6755cd34c8117ce8e61349314173256e52a1d085d5ff4",
    "godmode9i": "7fcf94f3b840ed240175a386c0a28c246bd40bcc791e8505c100ca78ba49b6e1",
    "ftpd": "63cf06c4e13772544630f60c91921c9fd616ad507b55174cb057fc3125fa8423",
    "pkmn_chest": "7e06166b565e89492a8489bfbf4d4c30e7e537de1517faa1ab2da5ec5f6ebf13",
    "ndsi_savedumper": "528df32883ca0380c37d81368eed8c40bb1346cae24e441c2fc28c2c9a9e9690",
    "ntm": "2563f8c0481c92ad361eccf7849f4bfeb1d6e6af3c88337f08d14ba2353b8797",
    "rocket_video": "f085152c1dde9d2b372fb0137b224c73d516cae4ba833f2f9fdda994e4bdf6e8",
    "ds_micpassthrough": "fba5e4725d73ee96117fddca4d67d029659b6a76b15db25eddb3d6dd936c6d3e",
    "dsfetch": "13b2022c0603ac7b60e8903526bb8487d22a37a72a61f7c8d56e62227c5fbac4",
    "cart_flasher": "03145f84957afdee5c27ba1cada7fcd1e9b887fd39da8c5967ae60d6b787b59a",
    "fastvideo_ds": "09e480591acd63073319e9dd191d32d8a3d85543c82037f7d1c966941b039f61",
    "dsidl": "23f56f0c6b9d0780f6b8306b25879c0ae2c1cc87fbb020d0fa4a1cd1897db30b",
    "kekatsu": "7e298996478fe22ffd1209a82aa153b859d104c0afae12aef77e716b0992aa87",
    "hiyacfw_7z": "1ba6d06b5fdbbf144d283dbdc63fd7975282c60adba1409c91b778aa8ce028b8",
    "twlmagician_macos": "e58afa025734dc74d8d98c49a51360841fe1aa671cbbd0bf036076afbee5e828",
    "twlmagician_linux": "7f037a5f34f7699b092930308f506f422ff524a812b1fe2d3acf1a86e7b80ff2",
    "twlmagician_win": "969ebb6a36cc7f1d875dbfd0a03f48f218d07d00d0326bc1ae5115267b695b87",
    "pico_launcher": "b4ed7f2cf2713e0c74985764536a0bfb7381566c67b0f85dc8b83375bcfc495d",
    "pico_loader_dspico": "b589797da9aa24882bd8a80119d90373a915df26ded9cc4c5a3708321ea29aa3",
    "hiya_launcher_usa": "8efbed489e9e5fa1c7b98035d56c708402468ad96d98fc5556f420809e418ee2",
    "hiya_launcher_eur": "a36d915f096952db7b1b9c3cd6b59cc67baf78946fa34589ed837417ab4e8b6a",
    "hiya_launcher_jpn": "4c388bed2df210aee798dcadc53f8a98fb57dd285cada53d6ff33a4945cde0d0",
    "hiya_launcher_aus": "484f5016928bf78af9e0e38a1dec03d45b9156c0aaa1d9c79ea109d111b13806",
    "hiya_launcher_chn": "d89ec8b964ca249bed77892edaa8140f0e0c1cab63aa0b917dc601d013c8a162",
    "hiya_launcher_kor": "1b35b08524e7837a9434be1e9d9286bfb806bf957ac4f7231992e092c28a29bd",
    # Tools TWLMagician (repo R-YaTian/TWLMagician) — o zip macOS é só o GUI PyInstaller
    "twlm_twltool_darwin": "34f968229bb40828f5ea0e5cc9ef705365dc7a8338a95d1b01f051262fb77340",
    "twlm_7za_darwin": "c078ca13bfef2e954d19b2232df09f5d0b1bd893a1c28fe95892a7d84388d0d6",
    "twlm_ndsblc_darwin": "cabf4072221e8e94890c838ea4c6175ab3dda68dc649c4b5fdf1f9274f99cafa",
    "twlm_twltool_linux": "6784e0f2d89470c784e90c7acde5b498782f3d28dc5e7dfe1508d29e16050deb",
    "twlm_7za_linux": "6199da759c562bd66e1e65aa9bd37c316a5e3bfaea779317de5ff736109b5b4e",
    "twlm_ndsblc_linux": "d45e82760b4f0a1f36bf087c98199eb2303a6586c653b9d3a1b181daab748adf",
    "twlm_twltool_win": "a1d35ed51dd893ed65e2bf68eb73e40482fd60858b9de8b88b32caa7dc83769c",
    "twlm_7z_win": "b1e06a424f2e7e3b9a5bf676665bd14bc39785fbc48cfdcc54ab63c574de0b01",
    "twlm_7z_dll_win": "51075af59f6696d5dc5446ba39fabfd0022628cdcfa41c80e7cb66e3bf4ee55d",
    "twlm_fatcat_darwin": "b5e96931f46c032abd26b8554c2593d8742f1a9783d0f51d26f6ebceea9e4495",
    "twlm_fatcat_linux": "81b31a304cb9e61c9c43cd03137f2faadb3e536b10f70bd9abaca8444ada1d79",
    "twlm_fatcat_win": "44ffbcb2924b17d72e9059acbcf34be100ba358ec3a4e9ebec00ae93dbb3a1b6",
    # Emuladores DSPico / Pico-Launcher (pins 2026-10-08)
    "emu_gbarunner3": "59c85c0598ed44c53b3fdf6281f61faf32eaa697bb88972ac80743a4f46ed92a",
    "emu_gbarunner2": "992ab26fa4f2eecfca260092a0077996b0064888518687f073d6a822d81d43e4",
    "emu_gameyob": "917ba6db5e14d04c98adfaa53268236c42b9820b5a50b354a4692478cdea5697",
    "emu_nesds": "746bd85d0cd040e37e44438f06f9027a3221c57df0f8135abd46e6e2a6864da8",
    "emu_stellads": "a5bea4e4e3af79fe940d2229767664a2a7cbf8096916bc94aea302c7da3cec1b",
    "emu_a5200ds": "9cc3859a34c1ebd6652cad864e5d9e18087321a64348baf531c4765a86346a81",
    "emu_a7800ds": "dbe7706bfafeffb283c1435cfd46a1c4e492dfc8e699684da8fcf32d33599bef",
    "emu_a8ds": "dcc3d3cdb1445d4377e7d58b766790168a361744504b2e9d44b4dd1f96a98a7c",
    "emu_picodrive_twl": "0db239d3e1000af21493d0fbaaae170d4133e93e697da124bd88c3702cafd36a",
    "emu_s8ds": "01e5312f2af0685c5e64fd8d4fc5e4d460df9de03b8f97b1df6eaa76c2d702f6",
    "emu_ngpds": "7e8981155fa6ed01657334127a013cdb8d910d4747cf0ce0ea70a1281010711d",
    "emu_ngpds_settings": "2967052b827417d6df655c275b7c96c595d85ac097306c474b3c627080e67ecf",
    "emu_nitrografx": "702a461490d3009ca3a463d93d055ae400f11318ef80617229e230d583342c35",
    "emu_colecods": "8b479a92051864e8e02ba22bee1e560aee5cb483b7a7e9b82e522f621adc7219",
    "emu_nintv_ds": "fe7f510c9947220da315bb23a85c7d59baf02e6eb42bda0323ab87705a8b75cb",
    "emu_snemulds_06a": "a34d2626ecaa8f8c12ac5c88434ca79dcaee353bb71b90f5f0d6c7fbdeb9dbd5",
    "emu_snemulds_06d": "001de2f70b9f54e0dd97c459079b53ceecee90b21b889aa3801a46a0e3e3ee3b",
    "emu_jenesisds": "74b5015414f06c8420e8cb198329bda294800838b4c7b707801f7a899e608d0f",
    "emu_neods": "7ea35938b4ca56c153585f1b63db2b5227dfb272f4861841d3459f7df82478ef",
    "emu_neods_ini": "4954c41e923b9dcd2b7a9d579beb6b9371b173b2e1670f76f14cca699a38710d",
}

PIN_META = {
    "unlaunch": {
        "repo": "edo9300/unlaunch-installer",
        "tag": "v2.6",
        "asset": "unlaunch-installer.dsi",
    },
    "twilight_7z": {
        "repo": "DS-Homebrew/TWiLightMenu",
        "tag": "v27.24.1",
        "asset": "TWiLightMenu-DSi.7z",
    },
    "twilight_vc_7z": {
        "repo": "DS-Homebrew/TWiLightMenu",
        "tag": "v27.24.1",
        "asset": "AddOn-VirtualConsole-DSi-Flashcard.7z",
    },
    "godmode9i": {
        "repo": "DS-Homebrew/GodMode9i",
        "tag": "v3.9.0",
        "asset": "GodMode9i.dsi",
    },
    "ftpd": {"repo": "mtheall/ftpd", "tag": "v3.2.1", "asset": "ftpd.nds"},
    "pkmn_chest": {
        "repo": "Universal-Team/pkmn-chest",
        "tag": "v2.2",
        "asset": "pkmn-chest.nds",
    },
    "ndsi_savedumper": {
        "repo": "edo9300/ndsi-savedumper",
        "tag": "1.2",
        "asset": "savedumper.nds",
    },
    "ntm": {"repo": "Epicpkmn11/NTM", "tag": "v0.5.1", "asset": "NTM.dsi"},
    "rocket_video": {
        "repo": "RocketRobz/RocketVideoPlayer",
        "tag": "v2.3.0",
        "asset": "RocketVideoPlayer.dsi",
    },
    "ds_micpassthrough": {
        "repo": "korbosoft/ds-micpassthrough",
        "tag": "v3.0.0",
        "asset": "ds-micpassthrough.nds",
    },
    "dsfetch": {
        "repo": "xPsycho999/DSFetch",
        "tag": "v1.0.0",
        "asset": "DSFetch.nds",
    },
    "cart_flasher": {
        "repo": "tasken/cart-flasher",
        "tag": "v0.8-tinkatuff",
        "asset": "cart_flasher.nds",
    },
    "fastvideo_ds": {
        "repo": "Mathos42/FastVideoDSPlayer-2",
        "tag": "v1.7",
        "asset": "FastVideoDS.nds",
    },
    "dsidl": {"repo": "Epicpkmn11/dsidl", "tag": "v0.1.1", "asset": "dsidl.dsi"},
    "kekatsu": {
        "repo": "cavv-dev/Kekatsu-DS",
        "tag": "v1.2.0",
        "asset": "Kekatsu.nds",
    },
    "hiyacfw_7z": {
        "repo": "DS-Homebrew/hiyaCFW",
        "tag": "v1.6.2",
        "asset": "hiyaCFW.7z",
    },
    "twlmagician_macos": {
        "repo": "R-YaTian/TWLMagician",
        "tag": "v1.6.3",
        "asset": "TWLMagician_macOS_universal2_v1.6.3.zip",
    },
    "twlmagician_linux": {
        "repo": "R-YaTian/TWLMagician",
        "tag": "v1.6.3",
        "asset": "TWLMagician_Linux_Py3_v1.6.3.zip",
    },
    "twlmagician_win": {
        "repo": "R-YaTian/TWLMagician",
        "tag": "v1.6.3",
        "asset": "TWLMagician_Win_v1.6.3_x64.msi",
    },
    "pico_launcher": {
        "repo": "LNH-team/pico-launcher",
        "tag": "v1.3.0",
        "asset": "Pico_Launcher.zip",
    },
    "pico_loader_dspico": {
        "repo": "LNH-team/pico-loader",
        "tag": "v1.6.0",
        "asset": "Pico_Loader_DSPICO.zip",
    },
}

URLS = {
    "pit_facebook": "https://dsi.cfw.guide/assets/files/memory_pit/768_1024/pit.bin",
    "pit_no_facebook": "https://dsi.cfw.guide/assets/files/memory_pit/256/pit.bin",
    "dumptool": "https://dsi.cfw.guide/assets/files/dumptool/boot.nds",
    "unlaunch": (
        "https://github.com/edo9300/unlaunch-installer/releases/download/v2.6/"
        "unlaunch-installer.dsi"
    ),
    "twilight_7z": (
        "https://github.com/DS-Homebrew/TWiLightMenu/releases/download/v27.24.1/"
        "TWiLightMenu-DSi.7z"
    ),
    "twilight_vc_7z": (
        "https://github.com/DS-Homebrew/TWiLightMenu/releases/download/v27.24.1/"
        "AddOn-VirtualConsole-DSi-Flashcard.7z"
    ),
    "godmode9i": (
        "https://github.com/DS-Homebrew/GodMode9i/releases/download/v3.9.0/"
        "GodMode9i.dsi"
    ),
    "ftpd": "https://github.com/mtheall/ftpd/releases/download/v3.2.1/ftpd.nds",
    "pkmn_chest": (
        "https://github.com/Universal-Team/pkmn-chest/releases/download/v2.2/"
        "pkmn-chest.nds"
    ),
    "ndsi_savedumper": (
        "https://github.com/edo9300/ndsi-savedumper/releases/download/1.2/"
        "savedumper.nds"
    ),
    "ntm": "https://github.com/Epicpkmn11/NTM/releases/download/v0.5.1/NTM.dsi",
    "rocket_video": (
        "https://github.com/RocketRobz/RocketVideoPlayer/releases/download/v2.3.0/"
        "RocketVideoPlayer.dsi"
    ),
    "ds_micpassthrough": (
        "https://github.com/korbosoft/ds-micpassthrough/releases/download/v3.0.0/"
        "ds-micpassthrough.nds"
    ),
    "dsfetch": (
        "https://github.com/xPsycho999/DSFetch/releases/download/v1.0.0/DSFetch.nds"
    ),
    "cart_flasher": (
        "https://github.com/tasken/cart-flasher/releases/download/v0.8-tinkatuff/"
        "cart_flasher.nds"
    ),
    "fastvideo_ds": (
        "https://github.com/Mathos42/FastVideoDSPlayer-2/releases/download/v1.7/"
        "FastVideoDS.nds"
    ),
    "dsidl": (
        "https://github.com/Epicpkmn11/dsidl/releases/download/v0.1.1/dsidl.dsi"
    ),
    "kekatsu": (
        "https://github.com/cavv-dev/Kekatsu-DS/releases/download/v1.2.0/Kekatsu.nds"
    ),
    "hiyacfw_7z": (
        "https://github.com/DS-Homebrew/hiyaCFW/releases/download/v1.6.2/hiyaCFW.7z"
    ),
    "twlmagician_macos": (
        "https://github.com/R-YaTian/TWLMagician/releases/download/v1.6.3/"
        "TWLMagician_macOS_universal2_v1.6.3.zip"
    ),
    "twlmagician_linux": (
        "https://github.com/R-YaTian/TWLMagician/releases/download/v1.6.3/"
        "TWLMagician_Linux_Py3_v1.6.3.zip"
    ),
    "twlmagician_win": (
        "https://github.com/R-YaTian/TWLMagician/releases/download/v1.6.3/"
        "TWLMagician_Win_v1.6.3_x64.msi"
    ),
    "pico_launcher": (
        "https://github.com/LNH-team/pico-launcher/releases/download/v1.3.0/"
        "Pico_Launcher.zip"
    ),
    "pico_loader_dspico": (
        "https://github.com/LNH-team/pico-loader/releases/download/v1.6.0/"
        "Pico_Loader_DSPICO.zip"
    ),
    "hiya_launcher_usa": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/launchers/USA"
    ),
    "hiya_launcher_eur": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/launchers/EUR"
    ),
    "hiya_launcher_jpn": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/launchers/JPN"
    ),
    "hiya_launcher_aus": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/launchers/AUS"
    ),
    "hiya_launcher_chn": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/launchers/CHN"
    ),
    "hiya_launcher_kor": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/launchers/KOR"
    ),
    "twlm_twltool_darwin": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Darwin/twltool"
    ),
    "twlm_7za_darwin": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Darwin/7za"
    ),
    "twlm_ndsblc_darwin": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Darwin/ndsblc"
    ),
    "twlm_twltool_linux": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Linux/twltool"
    ),
    "twlm_7za_linux": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Linux/7za"
    ),
    "twlm_ndsblc_linux": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Linux/ndsblc"
    ),
    "twlm_twltool_win": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Windows/twltool.exe"
    ),
    "twlm_7z_win": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Windows/7z.exe"
    ),
    "twlm_7z_dll_win": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Windows/7z.dll"
    ),
    "twlm_fatcat_darwin": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Darwin/fatcat"
    ),
    "twlm_fatcat_linux": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Linux/fatcat"
    ),
    "twlm_fatcat_win": (
        "https://raw.githubusercontent.com/R-YaTian/TWLMagician/main/Windows/fatcat.exe"
    ),
    "emu_gbarunner3": "https://files.deletecat.com/GBARunner3-hicode.zip",
    "emu_gbarunner2": (
        "https://github.com/unresolvedsymbol/GBARunner2-DSL-Enhanced/releases/"
        "download/v20201019-DSL_97447fe/GBARunner2_arm9dldi_ds.nds"
    ),
    "emu_gameyob": (
        "https://github.com/Stewmath/GameYob/releases/download/v0.5.2/gameyob.zip"
    ),
    "emu_nesds": (
        "https://github.com/DS-Homebrew/NesDS/releases/download/v2.1/nesDS.nds"
    ),
    "emu_stellads": (
        "https://github.com/wavemotion-dave/StellaDS/releases/download/8.4a/"
        "StellaDS.nds"
    ),
    "emu_a5200ds": (
        "https://github.com/wavemotion-dave/A5200DS/releases/download/3.9/"
        "A5200DS.nds"
    ),
    "emu_a7800ds": (
        "https://github.com/wavemotion-dave/A7800DS/releases/download/5.2c/"
        "A7800DS.nds"
    ),
    "emu_a8ds": (
        "https://github.com/wavemotion-dave/A8DS/releases/download/4.2/A8DS.nds"
    ),
    "emu_picodrive_twl": (
        "https://github.com/DS-Homebrew/PicoDriveTWL/releases/download/v2.0.2/"
        "PicoDriveTWL.nds"
    ),
    "emu_s8ds": (
        "https://github.com/FluBBaOfWard/S8DS/releases/download/v1.1.8/S8DS.zip"
    ),
    "emu_ngpds": (
        "https://github.com/FluBBaOfWard/NGPDS/releases/download/v0.6.0/NGPDS.zip"
    ),
    "emu_ngpds_settings": (
        "https://raw.githubusercontent.com/Sanrax/flashcart-guides/master/"
        "docs/assets/NGPDS/settings.cfg"
    ),
    "emu_nitrografx": (
        "https://github.com/FluBBaOfWard/NitroGrafx/releases/download/v0.9.0/"
        "NitroGrafx0_9_0.zip"
    ),
    "emu_colecods": (
        "https://github.com/wavemotion-dave/ColecoDS/releases/download/11.0/"
        "ColecoDS.nds"
    ),
    "emu_nintv_ds": (
        "https://github.com/wavemotion-dave/NINTV-DS/releases/download/6.3/"
        "NINTV-DS.nds"
    ),
    "emu_snemulds_06a": (
        "https://raw.githubusercontent.com/Sanrax/flashcart-guides/master/"
        "docs/assets/snemulds_0.6a.zip"
    ),
    "emu_snemulds_06d": (
        "https://raw.githubusercontent.com/Sanrax/flashcart-guides/master/"
        "docs/assets/SNEmulDS-0.6d-NTR-TGDS1.65.zip"
    ),
    "emu_jenesisds": (
        "https://raw.githubusercontent.com/Sanrax/flashcart-guides/master/"
        "docs/assets/jenesisds_0.7.4.zip"
    ),
    "emu_neods": (
        "https://raw.githubusercontent.com/flashcarts/AOS/refs/heads/master/"
        "extras/APP/NeoDS.nds"
    ),
    "emu_neods_ini": (
        "https://raw.githubusercontent.com/Sanrax/flashcart-guides/master/"
        "docs/assets/_NeoDS.ini"
    ),
}

FILENAMES = {
    "pit_facebook": "pit_facebook.bin",
    "pit_no_facebook": "pit_no_facebook.bin",
    "dumptool": "dumptool.nds",
    "unlaunch": "unlaunch.dsi",
    "twilight_7z": "TWiLightMenu-DSi.7z",
    "twilight_vc_7z": "AddOn-VirtualConsole-DSi-Flashcard.7z",
    "godmode9i": "GodMode9i.dsi",
    "ftpd": "ftpd.nds",
    "pkmn_chest": "pkmn-chest.nds",
    "ndsi_savedumper": "savedumper.nds",
    "ntm": "NTM.dsi",
    "rocket_video": "RocketVideoPlayer.dsi",
    "ds_micpassthrough": "ds-micpassthrough.nds",
    "dsfetch": "DSFetch.nds",
    "cart_flasher": "cart_flasher.nds",
    "fastvideo_ds": "FastVideoDS.nds",
    "dsidl": "dsidl.dsi",
    "kekatsu": "Kekatsu.nds",
    "hiyacfw_7z": "hiyaCFW.7z",
    "twlmagician_macos": "TWLMagician_macOS_universal2_v1.6.3.zip",
    "twlmagician_linux": "TWLMagician_Linux_Py3_v1.6.3.zip",
    "twlmagician_win": "TWLMagician_Win_v1.6.3_x64.msi",
    "pico_launcher": "Pico_Launcher.zip",
    "pico_loader_dspico": "Pico_Loader_DSPICO.zip",
    "hiya_launcher_usa": "hiya_launcher_USA",
    "hiya_launcher_eur": "hiya_launcher_EUR",
    "hiya_launcher_jpn": "hiya_launcher_JPN",
    "hiya_launcher_aus": "hiya_launcher_AUS",
    "hiya_launcher_chn": "hiya_launcher_CHN",
    "hiya_launcher_kor": "hiya_launcher_KOR",
    "twlm_twltool_darwin": "twlm_darwin_twltool",
    "twlm_7za_darwin": "twlm_darwin_7za",
    "twlm_ndsblc_darwin": "twlm_darwin_ndsblc",
    "twlm_twltool_linux": "twlm_linux_twltool",
    "twlm_7za_linux": "twlm_linux_7za",
    "twlm_ndsblc_linux": "twlm_linux_ndsblc",
    "twlm_twltool_win": "twlm_win_twltool.exe",
    "twlm_7z_win": "twlm_win_7z.exe",
    "twlm_7z_dll_win": "twlm_win_7z.dll",
    "twlm_fatcat_darwin": "twlm_darwin_fatcat",
    "twlm_fatcat_linux": "twlm_linux_fatcat",
    "twlm_fatcat_win": "twlm_win_fatcat.exe",
    "emu_gbarunner3": "GBARunner3-hicode.zip",
    "emu_gbarunner2": "GBARunner2_arm9dldi_ds.nds",
    "emu_gameyob": "gameyob.zip",
    "emu_nesds": "nesDS.nds",
    "emu_stellads": "StellaDS.nds",
    "emu_a5200ds": "A5200DS.nds",
    "emu_a7800ds": "A7800DS.nds",
    "emu_a8ds": "A8DS.nds",
    "emu_picodrive_twl": "PicoDriveTWL.nds",
    "emu_s8ds": "S8DS.zip",
    "emu_ngpds": "NGPDS.zip",
    "emu_ngpds_settings": "ngpds_settings.cfg",
    "emu_nitrografx": "NitroGrafx0_9_0.zip",
    "emu_colecods": "ColecoDS.nds",
    "emu_nintv_ds": "NINTV-DS.nds",
    "emu_snemulds_06a": "snemulds_0.6a.zip",
    "emu_snemulds_06d": "SNEmulDS-0.6d-NTR-TGDS1.65.zip",
    "emu_jenesisds": "jenesisds_0.7.4.zip",
    "emu_neods": "NeoDS.nds",
    "emu_neods_ini": "_NeoDS.ini",
}

MIN_SIZES = {
    "pit_facebook": 48032,
    "pit_no_facebook": 48032,
    "dumptool": 1024,
    "unlaunch": 1024,
    "twilight_7z": 1024 * 100,
    "twilight_vc_7z": 1024 * 100,
    "godmode9i": 1024,
    "ftpd": 1024,
    "pkmn_chest": 1024 * 100,
    "ndsi_savedumper": 1024,
    "ntm": 1024,
    "rocket_video": 1024,
    "ds_micpassthrough": 1024,
    "dsfetch": 1024,
    "cart_flasher": 1024,
    "fastvideo_ds": 1024,
    "dsidl": 1024,
    "kekatsu": 1024,
    "hiyacfw_7z": 1024 * 50,
    "twlmagician_macos": 1024 * 100,
    "twlmagician_linux": 1024 * 100,
    "twlmagician_win": 1024 * 100,
    "pico_launcher": 1024 * 50,
    "pico_loader_dspico": 1024 * 10,
    "hiya_launcher_usa": 1024,
    "hiya_launcher_eur": 1024,
    "hiya_launcher_jpn": 1024,
    "hiya_launcher_aus": 1024,
    "hiya_launcher_chn": 1024,
    "hiya_launcher_kor": 1024,
    "twlm_twltool_darwin": 1024 * 50,
    "twlm_7za_darwin": 1024 * 100,
    "twlm_ndsblc_darwin": 1024 * 10,
    "twlm_twltool_linux": 1024 * 50,
    "twlm_7za_linux": 1024 * 100,
    "twlm_ndsblc_linux": 1024 * 10,
    "twlm_twltool_win": 1024 * 50,
    "twlm_7z_win": 1024 * 100,
    "twlm_7z_dll_win": 1024 * 100,
    "twlm_fatcat_darwin": 1024 * 100,
    "twlm_fatcat_linux": 1024 * 50,
    "twlm_fatcat_win": 1024 * 100,
    "emu_gbarunner3": 1024 * 50,
    "emu_gbarunner2": 1024 * 50,
    "emu_gameyob": 1024 * 50,
    "emu_nesds": 1024 * 50,
    "emu_stellads": 1024 * 100,
    "emu_a5200ds": 1024 * 50,
    "emu_a7800ds": 1024 * 50,
    "emu_a8ds": 1024 * 50,
    "emu_picodrive_twl": 1024 * 50,
    "emu_s8ds": 1024 * 50,
    "emu_ngpds": 1024 * 10,
    "emu_ngpds_settings": 64,
    "emu_nitrografx": 1024 * 50,
    "emu_colecods": 1024 * 100,
    "emu_nintv_ds": 1024 * 50,
    "emu_snemulds_06a": 1024 * 50,
    "emu_snemulds_06d": 1024 * 50,
    "emu_jenesisds": 1024 * 50,
    "emu_neods": 1024 * 50,
    "emu_neods_ini": 8,
}
