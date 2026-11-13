# Licenças de terceiros

| Ficheiro | Projeto | Licença | Uso no Route Pico |
|---|---|---|---|
| `PicoDex-LICENSE.txt` | [rasalopa/picodex](https://github.com/rasalopa/picodex) | MIT | `core/routedex.py` e `tools/gen_pico_manifest.py` portam as regras e formatos do PicoDex (gamedata.json, resolução de arte, banner.bnr, saúde do cartão, capturas, identificação do loader). |
| `PicoLauncherEnhanced-LICENSE.txt` | [rasalopa/pico-launcher-enhanced](https://github.com/rasalopa/pico-launcher-enhanced) (fork de LNH-team/pico-launcher) | Zlib | Variantes opcionais descarregadas e pinadas em `core/cache_pins.py`; a fórmula de `tools/make_night_bg.py` está em `routedex._night_tint`. |

Os binários do Pico Launcher, Pico Loader e das variantes Enhanced são descarregados das releases originais e mantêm as respetivas licenças; não são redistribuídos com o código do Route Pico.
