# Licenças de terceiros

| Arquivo | Projeto | Licença | Uso no Route Pico |
|---|---|---|---|
| `PicoDex-LICENSE.txt` | [rasalopa/picodex](https://github.com/rasalopa/picodex) | MIT | `core/routedex.py`, `core/picodex_rules.py`, `core/loader_compat.py`, `core/art_picker.py`, `core/library_views.py` e `static/js/picodex-ui.js` portam as regras, formatos e telas da PicoDex (gamedata.json, sistemas e pastas, destino da arte, escolha de capas, banner.bnr, saúde do cartão, capturas, identificação do loader). `core/data/picodex/loaderReleases.json` é o arquivo de dados da PicoDex, copiado sem alterações na tag fixada em `core/data/upstreams.lock.json`. |
| `PicoLauncherEnhanced-LICENSE.txt` | [rasalopa/pico-launcher-enhanced](https://github.com/rasalopa/pico-launcher-enhanced) (fork de LNH-team/pico-launcher) | Zlib | Variantes opcionais (Launcher Enhanced e, em [rasalopa/pico-loader](https://github.com/rasalopa/pico-loader), o Loader Enhanced) baixadas das releases e fixadas em `core/data/upstreams.lock.json`; a fórmula de `tools/make_night_bg.py` está em `routedex._night_tint`. |
| `DSPico-logo-CC-BY-SA-4.0.txt` | [LNH-team/dspico-hardware](https://github.com/LNH-team/dspico-hardware) | CC BY-SA 4.0 | A framboesa do logo do DSPico está nos ícones do programa (`static/assets/logo*.svg` e os PNG/ICO/ICNS gerados); esses ícones são obras derivadas sob CC BY-SA 4.0. |
| `THIRD_PARTY_NOTICES.txt` | Runtime do Python e bibliotecas empacotadas (pywebview, PyObjC, py7zr e dependências, psutil, bottle…) | PSF, MIT, BSD, Apache-2.0, LGPL-2.1+ | Gerado por `tools/gen_third_party_notices.py` em cada build, com o texto da licença de cada pacote instalado; vai dentro do app junto com `LICENSE`. As bibliotecas LGPL são usadas sem modificação. |
| `IBM-Plex-OFL.txt` | [IBM Plex](https://github.com/IBM/plex) | SIL OFL 1.1 | Fonte monoespaçada da interface (`static/assets/fonts/ibm-plex-mono-latin-*.woff2`). |
| `Geist-OFL.txt` | [Geist](https://github.com/vercel/geist-font) | SIL OFL 1.1 | Fonte da interface, embutida em `static/assets/fonts/geist-latin-var.woff2` (subconjunto latino, arquivo variável do pacote `@fontsource-variable/geist` 5.2.8). |

Os binários do Pico Launcher, Pico Loader e das variantes Enhanced são baixados das releases originais e mantêm as respectivas licenças; não são redistribuídos com o código do Route Pico.

O pacote GEi (kernel e MoonShell do fabricante do cartucho) não é distribuído: não há licença que permita redistribuí-lo. O usuário baixa o pacote oficial (ver `vendor/README.md`).
