# Licenças de terceiros

| Arquivo | Projeto | Licença | Uso no Route Pico |
|---|---|---|---|
| `PicoDex-LICENSE.txt` | [rasalopa/picodex](https://github.com/rasalopa/picodex) | MIT | `core/routedex.py` e `core/picodex_rules.py` portam as regras e formatos da PicoDex (gamedata.json, sistemas e pastas, destino da arte, escolha de capas, banner.bnr, saúde do cartão, capturas, identificação do loader). `core/data/picodex/loaderReleases.json` é o arquivo de dados da PicoDex, copiado sem alterações na tag fixada em `core/data/upstreams.lock.json`. |
| `PicoLauncherEnhanced-LICENSE.txt` | [rasalopa/pico-launcher-enhanced](https://github.com/rasalopa/pico-launcher-enhanced) (fork de LNH-team/pico-launcher) | Zlib | Variantes opcionais (Launcher Enhanced e, em [rasalopa/pico-loader](https://github.com/rasalopa/pico-loader), o Loader Enhanced) baixadas das releases e fixadas em `core/data/upstreams.lock.json`; a fórmula de `tools/make_night_bg.py` está em `routedex._night_tint`. |
| `DSPico-logo-CC-BY-SA-4.0.txt` | [LNH-team/dspico-hardware](https://github.com/LNH-team/dspico-hardware) | CC BY-SA 4.0 | A framboesa do logo do DSPico está nos ícones do programa (`static/assets/logo*.svg` e os PNG/ICO/ICNS gerados); esses ícones são obras derivadas sob CC BY-SA 4.0. |
| `Geist-OFL.txt` | [Geist](https://github.com/vercel/geist-font) | SIL OFL 1.1 | Fonte da interface, embutida em `static/assets/fonts/geist-latin-var.woff2` (subconjunto latino, arquivo variável do pacote `@fontsource-variable/geist` 5.2.8). |

Os binários do Pico Launcher, Pico Loader e das variantes Enhanced são baixados das releases originais e mantêm as respectivas licenças; não são redistribuídos com o código do Route Pico.
