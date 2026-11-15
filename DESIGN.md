---
name: Route Pico
description: App de desktop que prepara e mantém o microSD do DSPico com um menu inicial de console em sete temas.
colors:
  bg: "#f3f4f5"
  surface: "#ffffff"
  surface-2: "#f2f3f4"
  line: "#d6d9dc"
  line-strong: "#90959b"
  fg: "#2a2d31"
  fg-soft: "#45494f"
  fg-mute: "#5d6269"
  accent: "#3384e1"
  accent-strong: "#2c72c2"
  accent-fg: "#256ec3"
  on-accent: "#191b1d"
  select: "#2e8cf0"
  select-fill: "#2e8cf0"
  on-select: "#141414"
  ok: "#1b8038"
  warn: "#a65c09"
  danger: "#cf2f3d"
  chrome: "#ffffff"
  chrome-fg: "#5d6269"
  hero: "#ffffff"
  hero-fg: "#2a2d31"
  tile-1: "#df6a12"
  tile-2: "#2f9e3a"
  tile-3: "#2a6fdb"
  tile-4: "#12928d"
  tile-5: "#d93a3a"
  tile-6: "#b98100"
  tile-7: "#8a4fd6"
typography:
  display:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "40px"
    fontWeight: 800
    letterSpacing: "0.02em"
  headline:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "21px"
    fontWeight: 800
    letterSpacing: "-0.015em"
  title-sm:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "17.5px"
    fontWeight: 800
    letterSpacing: "-0.01em"
  item:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 800
  body:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 800
  hint:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 700
  key:
    fontFamily: "Geist, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "11px"
    fontWeight: 800
    lineHeight: 1
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
  key: "6px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  gutter: "24px"
  status-h: "52px"
  dock-h: "64px"
  hints-h: "30px"
  content-max: "1080px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.62rem 1.25rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.on-accent}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg}"
    rounded: "{rounded.pill}"
    padding: "0.5rem 1rem"
  button-ghost-hover:
    backgroundColor: "{colors.surface-2}"
  screen-back:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "8px 14px 8px 8px"
  tab-shelf:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg-soft}"
    typography: "{typography.label}"
    rounded: "{rounded.md}"
    padding: "0.55rem 0.95rem"
  tab-shelf-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg}"
  tile:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg}"
    typography: "{typography.item}"
    rounded: "{rounded.sm}"
    padding: "10px 14px"
    height: "72px"
  dock-button:
    backgroundColor: "{colors.chrome}"
    textColor: "{colors.chrome-fg}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "8px 14px"
  status-bar:
    backgroundColor: "{colors.chrome}"
    textColor: "{colors.chrome-fg}"
    height: "{spacing.status-h}"
  hint-bar:
    backgroundColor: "{colors.chrome}"
    textColor: "{colors.chrome-fg}"
    typography: "{typography.hint}"
    height: "{spacing.hints-h}"
  key-cap:
    textColor: "{colors.chrome-fg}"
    typography: "{typography.key}"
    rounded: "{rounded.key}"
    height: "20px"
    padding: "0 6px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg}"
    rounded: "{rounded.lg}"
---

# Design System: Route Pico

## Overview

**Creative North Star: "O Menu Inicial do Seu Console"**

O Route Pico abre como o menu inicial de um console portátil ou de mesa: uma barra de status em cima com o cartão e a hora, as tarefas organizadas em blocos no meio, e uma barra de ícones embaixo. Os sete temas tomaram como referência menus iniciais de consoles reais e reproduzem a gramática de cada um (arranjo dos blocos, moldura, gesto de seleção, desenho das barras), sem copiar logotipos, ícones, fontes, sons ou nomes de marca. A navegação, o conteúdo e os controles são idênticos em todos os temas; muda o mundo material em volta deles.

A densidade é a de um menu de console: poucos itens grandes, um item selecionado por vez, legenda do item escolhido e atalhos de teclado (setas, Enter, Esc). As telas internas trocam o Início por um cabeçalho com Voltar, o ícone colorido da tarefa e o título, e as abas irmãs aparecem como uma prateleira de ícones. Todo o trabalho real (formatar, instalar, organizar jogos) acontece em painéis sóbrios dentro dessas telas, porque a ferramenta escreve num cartão do usuário e o tom lúdico para no limite da operação destrutiva.

O sistema recusa a barra lateral de dashboard do mundo anterior e recusa também o tema que só troca a cor de um mesmo layout. Cada tema tem paleta original e variantes clara (Catppuccin Latte) e noturna (Catppuccin Mocha), todas verificadas contra WCAG AA pelo gerador.

**Key Characteristics:**
- Três faixas fixas: barra de status, área do Início ou da tela, barra de ícones.
- Dez blocos no Início (seis DSPico, quatro Mais ferramentas), cada um com ícone SVG sólido próprio, de cantos retos, colorido por tarefa, mais o próximo passo do cartão com um botão.
- Telas de trabalho com uma ação principal no topo e o que é raro em seções recolhíveis (`details.fold`), que herdam a pele de painel do tema.
- Uma seleção-assinatura por tema, aplicada ao bloco atual, à aba ativa, ao item de tema escolhido e ao botão ativo da barra de ícones.
- Tipografia única em Geist, grotesca de cantos retos, com pesos 700 e 800 para tudo o que é rótulo.
- Teclado completo: setas movem a seleção espacialmente no Início, Enter abre, Esc ou Backspace voltam, com histórico por hash.

## Colors

As cores vêm de um único gerador (`tools/build_themes.py`), que escreve 21 combinações (sete temas × original, claro, noturno) como triplas RGB em `--c-*`; os valores do frontmatter são os do tema padrão, Dupla Tela original, e os demais temas reatribuem os mesmos papéis.

### Primary
- **Azul de Ação** (accent): preenche o botão primário e o progresso de operações. O gerador escurece o preenchimento até o texto sobre ele (on-accent) passar de 4,5:1, por isso o azul de ação fica um pouco abaixo do azul de seleção.
- **Azul de Ação Firme** (accent-strong): estado hover do botão primário, misturado 14% em direção ao texto.
- **Azul de Texto** (accent-fg): links, cursor de digitação e textos de destaque; garantido a 4,5:1 sobre painel e fundo.

### Secondary
- **Azul de Seleção** (select): a cor da seleção-assinatura (cantos, anéis, molduras, barra dourada no Cubo). Mantém a cor de marca do tema mesmo quando não serviria para texto; só o preenchimento com texto usa a versão ajustada (select-fill, com on-select por cima). Por tema, a seleção original é azul na Dupla Tela e na Câmera Dupla, ciano em Canais, Tablet de Sala e Híbrido, dourada no Cubo e menta no Estéreo 3D.

### Tertiary
- **Sete Cores de Tarefa** (tile-1 a tile-7: laranja, verde, azul, turquesa, vermelho, amarelo, roxo): pintam o ícone de cada bloco, o ícone do cabeçalho de tela e alguns ícones da barra de ícones. Cada bloco declara a cor pelo atributo `data-hue` (0 usa fg-soft, para ícones neutros). O gerador as ajusta a 3:1 contra o painel; nos modos claro e noturno elas vêm da paleta Catppuccin.

### Neutral
- **Chão** (bg): fundo da janela, sob a textura do tema (quadriculado, riscas, cubos).
- **Painel** (surface) e **Painel Recuado** (surface-2): painéis, blocos e o fim dos degradês de blocos e botões.
- **Linha** (line) e **Linha Firme** (line-strong): bordas; a linha firme é forçada a 3:1 contra o painel porque contorna controles.
- **Tinta** (fg, 7:1), **Tinta Suave** (fg-soft, 4,5:1) e **Tinta Discreta** (fg-mute, 4,5:1): os três níveis de texto, todos com contraste garantido sobre painel, painel recuado e chão.
- **Moldura** (chrome) e **Texto da Moldura** (chrome-fg): fundo e texto das barras de status e de ícones.
- **Tela de Destaque** (hero) e **Texto da Tela de Destaque** (hero-fg): a tela de cima menta da Câmera Dupla, o fim do degradê violeta do Cubo e o fundo lavanda do Estéreo 3D.
- **Estados** (ok, warn, danger): verde, âmbar e vermelho, a 4,5:1 sobre o painel.

### Named Rules
**The Gerador Rule.** Nenhuma cor de tema é escrita à mão: toda mudança de paleta passa por `tools/build_themes.py`, que falha se alguma das 21 combinações não passar em WCAG AA. `themes.css` e `theme-data.js` são arquivos gerados.

**The Seleção Separada da Ação Rule.** A cor de seleção marca onde o usuário está; a cor de ação marca o que executa. Botões primários usam accent, a seleção-assinatura usa select, e as duas podem ter matizes diferentes no mesmo tema (Estéreo 3D: ação laranja, seleção menta).

**The Uma Cor Por Tarefa Rule.** A cor de uma tarefa é a mesma no bloco do Início, no cabeçalho da tela e no ícone da aba. Cor de tarefa pinta ícone, nunca texto corrido.

## Typography

**Display Font:** Geist (com system-ui, -apple-system, Segoe UI)
**Body Font:** Geist (mesma família, arquivo variável 100–900 embutido em `static/assets/fonts/geist-latin-var.woff2`, licença OFL)
**Label/Mono Font:** IBM Plex Mono para caminhos, hashes e logs

**Character:** Uma só família grotesca, de cantos retos e desenho atual, carrega o sistema inteiro, com o peso fazendo o papel que outra fonte faria. Os rótulos ficam em 800, o que dá a leitura firme e amigável dos menus de console sem recorrer a uma fonte de exibição.

### Hierarchy
- **Display** (800, 40px, espaçamento 0,02em): relógio grande da tela de cima na Dupla Tela. Outros temas têm seu próprio relógio ou status grande (Canais 34px peso 300 na barra curva; Estéreo 3D 30px na barra de status).
- **Headline** (800, 24px, altura de linha 1,15, −0,015em): título de tela no cabeçalho com Voltar.
- **Title** (800, 21px, −0,015em): título do assistente. Abaixo dele vêm o título de seção do assistente (800, 17,5px, −0,01em) e o título de cada objetivo (800, 15px), que formam a escala de cabeçalhos do assistente 21 / 17,5 / 15.
- **Item** (800, 14–15px): rótulo de bloco do Início, nome do cartão, títulos de painel (section-label, 15px).
- **Body** (400, 14px, altura de linha 1,5): subtítulo de tela e texto de painel; descrições secundárias em 13px.
- **Label** (800, 13px): botões, abas da prateleira, botões da barra de ícones, Voltar.

### Named Rules
**The Piso de 11px Rule.** Nada funcional fica abaixo de 11px. Os tamanhos pequenos herdados do Tailwind sobem 1px no `skins.css`.

**The Peso Faz a Hierarquia Rule.** Dentro de um mesmo tamanho, a hierarquia vem do peso (400 para texto, 700 para dica, 800 para rótulo) e da tinta (fg, fg-soft, fg-mute). Espaçamento largo entre letras é exclusivo do Cubo, onde os títulos azuis espaçados fazem parte do mundo.

## Layout

O shell é uma grade de três linhas que ocupa a janela inteira sem rolagem do corpo: barra de status (52px), área principal com rolagem própria e a barra de ícones (64px). A área principal tem respiro de 22px em cima, 24px nas laterais e 28px embaixo, e o conteúdo das telas internas fica limitado a 1080px. A janela mínima do app é 960 × 640; abaixo de 1120px de largura a data some da barra de status, abaixo de 1040px some o rótulo de onde o usuário está, e abaixo de 720px de altura a barra de dicas cai para 26px e os arranjos altos se compactam.

O Início muda de arranjo por tema, sempre com os mesmos dez blocos na mesma ordem de DOM:

- **Dupla Tela:** duas telas empilhadas. Em cima, relógio (170px) e cartão em caixas brancas; uma dobradiça de borda dupla de 6px separa a tela de baixo, com os blocos em três colunas, cada bloco de 72px de altura com ícone à esquerda.
- **Câmera Dupla:** tela de cima menta com o cartão centralizado, balão de legenda com bico apontando para a fileira, uma só fileira de ícones quadrados (112px) com rolagem lateral e uma barra de rolagem própria com setas embaixo.
- **Canais:** grade de quatro colunas com o cartão ocupando dois canais e os dez blocos 16:9 completando três fileiras.
- **Tablet de Sala:** coluna de 150px com o cartão e grade de cinco quadrados de vidro ao lado.
- **Cubo:** painel do cartão em cima, dois painéis em colunas com as listas DSPico e Mais ferramentas, e uma caixa de descrição embaixo.
- **Estéreo 3D:** estado grande na metade de cima, nome do bloco escolhido em 26px e uma bandeja de seis colunas com os blocos.
- **Híbrido:** cartão num círculo, fileira de blocos quadrados de 176px para DSPico e doca redonda numa pílula para Mais ferramentas, com o rótulo do item selecionado embaixo do anel.

O ritmo de espaçamento observado gira em torno de 8, 14, 18 e 24px; gaps entre blocos ficam entre 14 e 18px.

### Named Rules
**The Mesma Ordem Rule.** Todos os arranjos usam o mesmo HTML; o tema muda grade, tamanhos e visibilidade, nunca a ordem de leitura nem o conjunto de blocos. A navegação por setas é espacial e calcula o vizinho pela posição real na tela.

**The Três Faixas Rule.** Status, conteúdo e ícones existem em todo tema e em toda tela; os atalhos de teclado funcionam sem faixa própria. Um tema pode tornar uma faixa transparente ou curvá-la, mas não pode removê-la.

## Elevation & Depth

O sistema é híbrido. A base usa três sombras suaves por esquema (painel, hover, menu) e uma de pressão, mais fortes no modo noturno. Por cima delas, cada tema define a própria profundidade como parte do mundo: biseis e sombra preta pesada no Cubo, relevo inferior sólido sem desfoque nos blocos do Estéreo 3D (o bloco desce 3px ao ser pressionado), moldura interna branca de 6px no vidro do Tablet de Sala, sombra interna inferior nos canais. O Híbrido é quase plano, com uma sombra de 1–3px.

### Shadow Vocabulary
- **Painel, claro** (`box-shadow: 0 1px 2px rgb(20 22 26 / 0.05), 0 6px 18px rgb(20 22 26 / 0.06)`): painéis das telas de trabalho.
- **Menu, claro** (`box-shadow: 0 2px 6px rgb(20 22 26 / 0.08), 0 18px 48px rgb(20 22 26 / 0.16)`): gaveta Atividade e menu de tema.
- **Pressão** (`box-shadow: 0 1px 1px rgb(20 22 26 / 0.10)`): botão primário pressionado.
- **Relevo do Estéreo 3D** (`box-shadow: 0 5px 0 rgb(var(--c-line-strong) / 0.55), 0 10px 18px rgb(0 0 0 / 0.08)`): blocos e painéis com espessura de peça de brinquedo; é o material do próprio tema.
- **Bisel do Cubo** (`box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.10), 0 6px 22px rgb(0 0 0 / 0.55)`): painéis índigo-violeta sobre o preto.

### Named Rules
**The Profundidade Pertence ao Tema Rule.** Sombras de assinatura (relevo sólido, bisel, brilho de anel) ficam no bloco do tema em `console.css` ou `skins.css`. As sombras base do gerador valem para todos e não carregam identidade.

## Shapes

Cada tema tem sua escala de raio (pequeno / médio / grande) emitida pelo gerador: Dupla Tela e Híbrido 6/10/14, Câmera Dupla 8/12/16, Canais 14/18/24, Tablet de Sala 14/18/22, Cubo 4/6/8, Estéreo 3D 12/16/22. Botões, chips e o Voltar são pílulas (999px) em todos os temas, exceto na Dupla Tela e no Cubo, onde os botões ficam retangulares com o raio do tema. As formas de assinatura são do tema: a borda dupla da dobradiça na Dupla Tela, o balão com bico da Câmera Dupla, a barra curva desenhada por máscara SVG com o fio ciano em Canais, os quadrados de moldura grossa do Tablet de Sala, a doca circular do Híbrido e o círculo do cartão no Híbrido. O medidor de espaço da barra de status tem forma de bateria (38 × 18px, borda de 2px, polo de 3px).

## Components

### Buttons
Botões firmes e arredondados, com o primário reservado para a ação que executa.
- **Shape:** pílula (999px); retangular com raio do tema na Dupla Tela (10px) e no Cubo (6px).
- **Primary:** fundo accent, texto on-accent, 800 a 13px, padding 0,62rem × 1,25rem, brilho interno de 1px e sombra curta. No Cubo vira a barra dourada biselada com texto escuro e espaçamento 0,06em.
- **Hover / Focus:** hover troca para accent-strong; pressão desce 1px com a sombra de pressão; foco por teclado é um contorno de 2px na cor fg com afastamento de 4px.
- **Ghost:** painel com borda line-strong de 1px (2px e degradê claro na Dupla Tela); hover recua para surface-2 e acende a borda em select.
- **Disabled:** opacidade 0,5 e cursor bloqueado.

### Chips
- **Style:** pílula de 12px na barra de status e nos painéis; dentro da barra de status usa o texto da moldura com fundo a 10% e borda a 35%.

### Cards / Containers
- **Corner Style:** raio grande do tema (14px no padrão).
- **Background:** surface, com degradê para surface-2 em Canais e no Tablet de Sala, e degradê surface → surface-2 → hero no Cubo.
- **Shadow Strategy:** sombra de painel base, substituída pela profundidade do tema (ver Elevation & Depth).
- **Border:** 1px line no padrão; 2px na Dupla Tela e no Cubo; 3px em Canais; nenhuma no Híbrido claro.
- **Internal Padding:** entre 14 e 22px, conforme o tema e a densidade do painel.

### Inputs / Fields
- **Style:** seletor com raio médio do tema, borda line-strong, fundo surface, peso 600. O seletor do microSD na barra de status tem 34px de altura e entre 180 e 340px de largura.
- **Focus:** borda em select e halo de 3px em select a 25%.

### Navigation
- **Barra de status:** marca, onde o usuário está, papel do volume, seletor do microSD com botão de atualizar, progresso da operação, data, hora em 800 com números tabulares e o medidor de espaço em forma de bateria (vermelho quando cheio). No Estéreo 3D a barra cresce para 72px, com hora em 30px e bateria de 58 × 28px.
- **Barra de ícones:** Início, Atividade e Configurações. O botão ativo recebe a seleção do tema; Atividade mostra um ponto quando há registro novo. Em Canais os botões são círculos de 58–70px sobre a barra curva com o relógio no centro; no Tablet de Sala e no Estéreo 3D os ícones ganham cores de tarefa.
- **Cabeçalho de tela:** Voltar em pílula com seta, ícone da tarefa num quadrado de 46px com a cor da tarefa a 14% e o título de 24px.
- **Prateleira de abas:** abas irmãs como botões com ícone de 18px, raio médio, borda line; a ativa ganha a seleção-assinatura e o ícone em select. Setas esquerda e direita percorrem as abas.

### Bloco do Início (signature)
O bloco é um botão com ícone colorido e rótulo; a descrição fica oculta visualmente e alimenta a legenda do item selecionado. O bloco atual segue o foco do teclado e o ponteiro e recebe a seleção-assinatura do tema; com foco, o contorno genérico some para não dobrar a seleção. Pressionar reduz o bloco a 98%. Em Câmera Dupla e Tablet de Sala o bloco atual mostra a etiqueta «Abrir» no preenchimento de seleção.

### Seleção-assinatura (signature)
Um gesto de seleção por tema, compartilhado por bloco, aba, item de tema e botão ativo da barra de ícones:
- **Dupla Tela:** quatro cantos azuis retos de 4px, afastados 6px, recortados por máscara.
- **Câmera Dupla:** moldura azul de 3px com o bloco ampliado a 112% e a etiqueta «Abrir» embaixo.
- **Canais:** aro ciano de 2px com brilho de 18px e ampliação a 103%.
- **Tablet de Sala:** moldura ciano larga de 6px com ampliação a 104% e faixa «Abrir» na base.
- **Cubo:** barra dourada biselada (degradê de creme a ouro escuro) com texto escuro.
- **Estéreo 3D:** cantos menta arredondados de 5px com brilho, afastados 8px.
- **Híbrido:** anel ciano duplo, com 3px de painel entre o bloco e o anel.

### Gaveta Atividade
Painel flutuante de até 560px ancorado acima da barra de ícones, com cabeçalho e 240px de registro rolável. Abre com fade e subida de 10px em 200–240ms.

## Do's and Don'ts

### Do:
- **Do** gerar toda cor de tema por `tools/build_themes.py` e rodar `--check`; o gerador bloqueia combinações abaixo de WCAG AA.
- **Do** usar as variáveis `--c-*` em `rgb(var(--c-x) / alfa)` para qualquer cor nova, em `console.css` ou `skins.css`.
- **Do** colocar cada nova assinatura de tema dentro do bloco `html[data-family="…"]` correspondente e manter layout, navegação e controles iguais entre temas.
- **Do** dar a toda tarefa nova um ícone SVG próprio no sprite de `index.html` (forma sólida em `fill`, cantos retos, recortes por `fill-rule: evenodd`, viewBox 24; só a linha de Atividade usa traço, com pontas retas) e uma cor de tarefa por `data-hue`.
- **Do** gerar o ícone do programa a partir de `static/assets/logo.svg` e `logo-small.svg` com `tools/build_icons.py`. O desenho é a framboesa do logo do DSPico (LNH team, CC BY-SA 4.0, crédito em `docs/licenses/`) com a seta de rota branca sobre verde-escuro, e os arquivos derivados seguem a mesma licença.
- **Do** aplicar a seleção do tema ao elemento atual em vez de inventar um estado novo; bloco, aba, item de tema e botão da barra compartilham o mesmo gesto.
- **Do** manter a escala de cabeçalhos do assistente em 21 / 17,5 / 15px.
- **Do** respeitar `prefers-reduced-motion`: sem animação de entrada de tela e sem ampliação do bloco selecionado.

### Don't:
- **Don't** editar `themes.css` ou `theme-data.js` à mão.
- **Don't** usar logotipos, ícones, fontes, sons ou nomes de marca de consoles; os temas usam nomes genéricos.
- **Don't** voltar à barra lateral de dashboard nem criar um tema que só troca a cor do layout de outro.
- **Don't** somar um contorno genérico de foco à seleção do tema em um elemento já selecionado.
- **Don't** usar cor de tarefa em texto corrido nem cor de seleção como cor de ação.
- **Don't** criar pontos de página no Tablet de Sala nem outros indicadores que não correspondam a páginas reais.
- **Don't** deixar texto funcional abaixo de 11px.
