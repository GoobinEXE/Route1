# Licenças de terceiros

| Ficheiro | Projeto | Licença | Uso no Route Pico |
|---|---|---|---|
| `PicoDex-LICENSE.txt` | [rasalopa/picodex](https://github.com/rasalopa/picodex) | MIT | `core/routedex.py` e `core/picodex_rules.py` portam as regras e formatos da PicoDex (gamedata.json, sistemas e pastas, destino da arte, escolha de capas, banner.bnr, saúde do cartão, capturas, identificação do loader). `core/data/picodex/loaderReleases.json` é o ficheiro de dados da PicoDex, copiado sem alterações na tag fixada em `core/data/upstreams.lock.json`. |
| `PicoLauncherEnhanced-LICENSE.txt` | [rasalopa/pico-launcher-enhanced](https://github.com/rasalopa/pico-launcher-enhanced) (fork de LNH-team/pico-launcher) | Zlib | Variantes opcionais (Launcher Enhanced e, em [rasalopa/pico-loader](https://github.com/rasalopa/pico-loader), o Loader Enhanced) descarregadas das releases e fixadas em `core/data/upstreams.lock.json`; a fórmula de `tools/make_night_bg.py` está em `routedex._night_tint`. |

Os binários do Pico Launcher, Pico Loader e das variantes Enhanced são descarregados das releases originais e mantêm as respetivas licenças; não são redistribuídos com o código do Route Pico.
