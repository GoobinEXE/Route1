# Product

<!-- impeccable:product-schema 1 -->

<!-- Escrito sem entrevista: o usuário pediu autonomia total e saiu do computador.
     Tudo abaixo vem das decisões dele nesta conversa (marcadas "confirmado") ou de
     inferência a partir do código e do README (marcadas "inferido"). -->

## Platform

web

## Users

Quem tem um cartucho DSPico (e, secundariamente, um DSi para softmod ou um flashcard R4/GEi) e prepara o microSD no computador: instala o Pico Launcher e o Pico Loader, organiza jogos, capas e emuladores, e acompanha a biblioteca. Público de fãs de consoles Nintendo, de iniciantes a entusiastas; usa o app em sessões curtas com o cartão ligado ao leitor (inferido do README e dos fluxos do app).

## Product Purpose

Preparar e manter o microSD do DSPico sem montar pastas à mão e sem arriscar o volume errado, com downloads oficiais verificados por SHA-256 (confirmado). O softmod do DSi e os flashcards R4/GEi continuam disponíveis em «Mais ferramentas» (confirmado).

## Positioning

App nativo (pywebview) que junta o pacote oficial do LNH team, as variantes Enhanced opcionais e a biblioteca RouteDex (port nativo das regras da PicoDex) em um só lugar, sempre a partir das cinco fontes oficiais fixadas em `core/data/upstreams.lock.json` (confirmado).

## Operating Context

Desktop macOS, Windows e Linux; janela nativa com UI HTML/CSS/JS offline (sem CDN, sem servidor). O cartão é escolhido na barra de cima; operações de escrita bloqueiam a UI e abrem a gaveta Atividade. Há também um app de console (`nds/`) que conversa com o desktop por USB (confirmado).

## Capabilities and Constraints

- Navegação: menu de console (Início em blocos, telas com Voltar, barra de ícones); Início, DSPico (Cartão, Jogos, RouteDex, Launcher, Emuladores e apps USB, Avançado), Mais ferramentas (Softmod DSi, Flashcards R4/GEi, Biblioteca TWiLight, Apps homebrew, Manutenção), Configurações (confirmado).
- UI 100% offline; fontes embutidas; nada de pedidos remotos a partir da UI (confirmado, AGENTS.md).
- Idioma da UI: português (confirmado).
- Temas: sete temas com nomes genéricos inspirados em menus de consoles (DS Lite é o padrão; DSi, Wii, Wii U, GameCube, 3DS, Switch), cada um com paleta original e modos claro (Catppuccin Latte) e noturno (Catppuccin Mocha) (confirmado).

## Brand Commitments

- Nome: Route Pico (antes Route 1 Kit); publisher Dark Room (confirmado).
- Visual moderno e voltado ao público Nintendo, inspirado nos menus dos consoles, sem copiar: nada de logotipos, ícones, fontes ou sons da Nintendo, e nomes de tema sem marcas registradas (confirmado).
- Catppuccin mantém-se como base dos modos claro e noturno (confirmado).
- Crédito visível à PicoDex (rasalopa, MIT) e às variantes Enhanced (confirmado).

## Evidence on Hand

Logotipo e ícones do app em `static/assets/`; imagens de referência dos menus dos consoles foram mostradas pelo usuário como inspiração e não fazem parte do produto. Não existem screenshots de marketing, testemunhos nem números de utilização: não inventar.

## Product Principles

1. O cartão do usuário primeiro: nenhuma escrita sem verificação, nenhum sucesso sem hash.
2. Oficial por padrão, opcional por escolha, sempre transparente sobre o que é não oficial.
3. Uma coisa em um só lugar: sem funções duplicadas entre vistas.
4. Familiar para quem cresceu com os consoles, mas uma ferramenta séria.

## Accessibility & Inclusion

Contraste WCAG AA em todos os temas e modos; navegação completa por teclado (setas no Início e nas abas, Enter abre, Esc volta, Alt+1…4); respeitar `prefers-reduced-motion` (inferido como requisito mínimo).
