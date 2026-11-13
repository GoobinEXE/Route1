---
name: Route Pico
description: App de secretária para preparar e manter o microSD do DSPico, com sete temas inspirados em menus de consoles.
colors:
  ground: "#e2e6ea"
  surface: "#ffffff"
  surface-2: "#f1f3f5"
  line: "#cdd3da"
  line-strong: "#8d959e"
  ink: "#1d2126"
  ink-soft: "#3b424a"
  ink-mute: "#59616b"
  accent: "#2f7de1"
  accent-strong: "#286cc2"
  accent-fg: "#2766b8"
  on-accent: "#111417"
  select: "#2f7de1"
  select-fill: "#2f7de1"
  on-select: "#141414"
  ok: "#197633"
  warn: "#995508"
  danger: "#c12c39"
typography:
  display:
    fontFamily: "Nunito, ui-rounded, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "34px"
    fontWeight: 800
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Nunito, ui-rounded, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "26px"
    fontWeight: 800
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Nunito, ui-rounded, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 800
    letterSpacing: "0"
  body:
    fontFamily: "Nunito, ui-rounded, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Nunito, ui-rounded, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 700
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
rounded:
  sm: "10px"
  md: "14px"
  lg: "18px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
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
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.5rem 1rem"
  button-ghost-hover:
    backgroundColor: "{colors.surface-2}"
  tab-pill:
    backgroundColor: "{colors.surface-2}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0.5rem 1rem"
  tab-pill-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
  tab-quiet-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
  nav-item:
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.md}"
    padding: "10px 14px"
  nav-item-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "24px"
  list-row:
    textColor: "{colors.ink}"
    padding: "12px 6px"
  list-row-hover:
    backgroundColor: "{colors.surface-2}"
  step-badge:
    backgroundColor: "{colors.select-fill}"
    textColor: "{colors.on-select}"
    rounded: "{rounded.pill}"
    size: "30px"
  field-select:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
---

# Design System: Route Pico

## Overview

**Creative North Star: "A Sala de Estar do Console"**

Route Pico é uma ferramenta de trabalho com um só esqueleto: barra lateral, barra de cima, abas em cápsula e painéis claros. Por cima desse esqueleto, cada um dos sete temas troca três coisas e só três: o chão (o padrão de fundo do `body`), o acabamento dos painéis e o gesto de seleção. Layout, navegação, controlos e tipografia são iguais em todos os temas; quem muda de tema reconhece a seu console sem reaprender o app.

O sistema tem dois eixos independentes. O tema (`data-family`: Dupla Tela, Câmera Dupla, Canais, Tablet de Sala, Cubo, Estéreo 3D, Híbrido) e o modo (`data-mode`: Original, Claro = Catppuccin Latte, Noturno = Catppuccin Mocha; Sistema resolve para Claro ou Noturno). O `theme.js` deriva um terceiro atributo, `data-scheme` (light/dark), que escolhe as sombras. As 21 combinações saem de um gerador que falha a construção se alguma não passar em WCAG AA. A densidade é média: painéis com 22 a 28px de respiro, linhas de lista planas, nada de cartão dentro de cartão.

As rejeições confirmadas pelo usuário são duas. Nada de logotipos, ícones, fontes, sons ou nomes de marca da Nintendo; os temas têm nomes genéricos. E nada de traje de console: sem moldura de hardware, botões falsos ou cópia literal de menus. A inspiração vive no chão, no vidro dos painéis e no gesto de seleção.

**Key Characteristics:**
- Um só seletor compartilhado de seleção-assinatura, redefinido por tema em `static/skins.css`.
- Cores só por tokens em triplas RGB, geradas e verificadas contra WCAG AA.
- Nunito variável embutida em toda a UI, títulos em 800, rótulos de seção em minúsculas de frase.
- Cápsulas para ações e abas; raios generosos nos painéis, variáveis por tema.
- Foco (contorno da cor do texto) separado da seleção (cor `select`).

## Colors

Neutros frios e claros com um acento de ação e uma cor de seleção por tema; os valores do frontmatter são os do tema padrão (Dupla Tela, modo Original), e cada combinação tema × modo redefine os mesmos 18 papéis.

### Primary
- **Azul Moldura** (accent, acento das ações): preenchimento do botão primário. Em Dupla Tela coincide com a cor de seleção; noutros temas é diferente (Câmera Dupla usa azul-petróleo nas ações e azul-céu na seleção; Estéreo 3D, laranja nas ações e verde na seleção; Híbrido, vermelho nas ações e ciano na seleção).
- **Azul Moldura Fundo** (accent-strong): estado hover do botão primário, o acento misturado 14% em direção ao texto.
- **Azul Moldura Texto** (accent-fg): acento usado como texto, ícones de ação e cursor de inserção; garantido a 4.5:1 sobre painel e chão.
- **Tinta sobre Acento** (on-accent): texto dentro do botão primário. O gerador escolhe branco ou tinta escura conforme o contraste; em Dupla Tela Original é tinta escura, porque o branco sobre aquele azul fica abaixo de 4.5:1.

### Secondary
- **Cor de Seleção** (select): a cor-assinatura de cada tema, usada só em anéis, molduras, cantos, barra de uso do cartão e realce de texto selecionado. Mantém o valor da marca do tema mesmo quando não serve como fundo de texto.
- **Seleção Preenchida** (select-fill) e **Tinta sobre Seleção** (on-select): o par para quando a seleção é um preenchimento com texto (etiqueta da Câmera Dupla, números dos Primeiros passos). O preenchimento só escurece o necessário para o texto passar 4.5:1.

### Tertiary
- **Verde Estado** (ok), **Âmbar Estado** (warn), **Vermelho Estado** (danger): estados de presença, aviso e erro, cada um garantido a 4.5:1 sobre os três fundos. Aparecem como cor de texto e de ícone de estado, nunca como fundo de seção.

### Neutral
- **Chão Cinza-Névoa** (ground, `--c-bg`): fundo da janela, por baixo do padrão do tema.
- **Painel Branco** (surface): painéis, barra lateral, barra de cima, botões fantasma e aba ativa.
- **Painel Recolhido** (surface-2): calha das abas, hover de linhas e de botões fantasma, trilho da barra de uso.
- **Fio** (line) e **Fio Forte** (line-strong): divisórias e bordas de painel; o fio forte contorna controlos e é garantido a 3:1 contra o painel (WCAG 1.4.11).
- **Tinta** (ink, `--c-fg`, 7:1), **Tinta Suave** (ink-soft, `--c-fg-soft`) e **Tinta Discreta** (ink-mute, `--c-fg-mute`), estas duas a 4.5:1: hierarquia de texto.

### Named Rules
**The Triplet Rule.** Toda a cor é uma tripla RGB (`--c-accent: 47 125 225`) lida como `rgb(var(--c-accent))` ou `rgb(var(--c-accent) / 0.1)`, e o Tailwind expõe-na como `rgb(var(--c-x) / <alpha-value>)`. Hex literal em um componente é um defeito: não muda com o tema.

**The Generated Palette Rule.** `static/themes.css` e `static/theme-data.js` são gerados por `tools/build_themes.py` e nunca se editam à mão. Uma cor nova entra na paleta do gerador; `python tools/build_themes.py --check` falha se os arquivos estiverem desatualizados, e a geração aborta se uma combinação não passar em AA.

**The Two Colors Rule.** Acento é para agir, seleção é para estar. O botão primário usa `accent`; o item ativo, os anéis e a barra de uso usam `select`. Não trocar um pelo outro, mesmo nos temas onde coincidem.

## Typography

**Display Font:** Nunito variável 400–800, embutida em `static/assets/fonts/nunito-latin-var.woff2` (com ui-rounded, system-ui, -apple-system, Segoe UI)
**Body Font:** Nunito (a mesma família)
**Label/Mono Font:** IBM Plex Mono 400/500, embutida, para caminhos, versões e `<code>`

**Character:** Uma sans arredondada única dá o tom amigável dos consoles; o peso 800 nos títulos e rótulos faz a hierarquia sem precisar de segunda família.

### Hierarchy
- **Display** (800, 34px, -0.02em): título do painel principal do Início. O `.hero-title` fora do Início fica em 28px.
- **Headline** (800, 26px, -0.015em): título de cada vista (`.page-title`); no tema Híbrido desce para 700.
- **Title** (800, 15px): rótulos de seção (`.section-label`), nome do cartão, títulos de passo e de objetivo. Títulos de painel do Início em 18px/800.
- **Body** (400, 14px, 1.5): subtítulos de vista e texto de painel, até 52ch no Início.
- **Label** (700, 13px): navegação (14px/700), abas, botões fantasma; botão primário em 13px/800 com 0.01em.
- **Small** (12px): dicas do seletor de tema, pílulas de estado, texto secundário de linhas.

### Named Rules
**The Sentence-Case Label Rule.** O rótulo de seção é Nunito 15px/800 na cor do texto, em minúsculas de frase, sem tracking e sem maiúsculas. O estilo antigo (11px, maiúsculas, 0.06em, cor discreta) continua em `style.css` e é anulado por `skins.css`; não o reativar.

**The +1px Rule.** A Nunito tem altura-x menor que a fonte anterior, por isso a escala pequena sobe 1px: os utilitários `text-[10px]`, `text-[11px]`, `text-[12px]` e `text-[13px]` renderizam a 11, 12, 13 e 14px. Nenhum texto funcional fica abaixo de 11px.

## Layout

Shell de produto fixo: grelha de duas colunas com a barra lateral (220px) e o conteúdo; a barra de cima (56px) leva o seletor de cartão, o progresso e o seletor de tema. A barra lateral tem a marca e as quatro vistas (Início, DSPico, Mais ferramentas, Configurações); DSPico e Mais ferramentas abrem abas em cápsula. Há um só seletor de cartão (barra de cima) e um só registro (gaveta Atividade).

O Início é uma grelha de duas colunas (1.65fr e 1fr, 16px de intervalo): o painel DSPico domina e contém o estado do cartão (nome, barra de uso, ações); Mais ferramentas fica ao lado como lista de ligações; os Primeiros passos ocupam a largura toda por baixo, em três colunas numeradas.

O ritmo de espaçamento assenta em 4, 8, 12, 16 e 24px; os painéis do Início usam 22 a 28px de padding. A lista de navegação tem 6px de folga negativa para os anéis da seleção-assinatura não serem cortados pelo contentor com scroll.

Pontos de quebra observados: a 1060px a barra lateral passa a 176px, o conteúdo fica com 18px/16px de padding, o distintivo de papel do cartão esconde-se e o Início empilha em uma coluna (os passos também). A 860px a barra lateral passa a 156px, a navegação desce para 13px com 9px/10px de padding e o subtítulo da marca esconde-se; os rótulos ficam inteiros.

## Elevation & Depth

Sistema híbrido: painéis com sombra ambiente muito baixa sobre um chão com padrão, e profundidade adicional só no hover e nos menus. As sombras são tokens trocados pelo `data-scheme`; no esquema escuro somam um fio de luz interior de 1px. Os temas Tablet de Sala e Cubo dão aos painéis um gradiente vertical suave (surface para surface-2) como acabamento; os outros ficam lisos.

### Shadow Vocabulary
- **Painel** (`--shadow-panel`, claro: `0 1px 2px rgb(20 22 26 / 0.05), 0 6px 18px rgb(20 22 26 / 0.06)`): painéis e cartões em repouso.
- **Hover** (`--shadow-hover`, claro: `0 2px 4px rgb(20 22 26 / 0.06), 0 12px 28px rgb(20 22 26 / 0.10)`): painel de ação sob o cursor, com a borda a passar a fio forte.
- **Menu** (`--shadow-menu`, claro: `0 2px 6px rgb(20 22 26 / 0.08), 0 18px 48px rgb(20 22 26 / 0.16)`): menus flutuantes como o seletor de tema.
- **Pressão** (`--shadow-press`, claro: `0 1px 1px rgb(20 22 26 / 0.10)`): botão primário pressionado.

### Named Rules
**The Rings Not Offsets Rule.** A profundidade da seleção faz-se com anéis de espalhamento (`0 0 0 Npx`) e sombras difusas da cor de seleção; não há sombras sólidas deslocadas em nenhum tema.

## Shapes

Raios generosos e variáveis por tema, em três degraus (`--radius-sm`, `--radius`, `--radius-lg`): Dupla Tela 10/14/18px, Câmera Dupla, Tablet de Sala e Estéreo 3D 12/16/22px, Canais 14/18/26px, Cubo 6/10/14px (o mais anguloso), Híbrido 10/14/20px. Painéis usam o raio grande; itens de navegação, notas e campos o médio. Botões, abas, chips, calhas de abas, barra de uso e números de passo são cápsulas (999px). Bordas de 1px no fio; Canais engrossa a borda dos painéis para 2px. A barra de uso tem 12px de altura em cápsula.

## Components

### Buttons
Cápsulas firmes, como os botões dos menus de console.
- **Shape:** cápsula completa (999px) em todas as variantes, primária, fantasma e ícone.
- **Primary:** preenchimento `accent`, texto `on-accent`, 13px/800, padding 0.62rem 1.25rem, com brilho interior de 1px no topo e sombra curta (`0 1px 0 rgb(255 255 255 / 0.18) inset, 0 2px 5px rgb(0 0 0 / 0.16)`).
- **Hover / Active:** hover passa a `accent-strong` com sombra mais funda; active desce 1px e usa `--shadow-press`. Transições de 180ms com `cubic-bezier(0.22, 1, 0.36, 1)`.
- **Ghost:** painel com borda de fio forte, texto `ink`, 13px/700, padding 0.5rem 1rem; hover em `surface-2` com a borda na cor de seleção.
- **Icon:** cápsula de 2.1rem com borda de fio forte.
- **Disabled:** opacidade 0.5, cursor bloqueado, sem deslocamento.

### Chips
- **Style:** cápsulas de 12px para estados e etiquetas (pílulas de estado na barra de cima, tags Recomendado / Não oficial). O estilo herdado em maiúsculas e tracking ainda existe em `style.css`; ver Do's and Don'ts.

### Cards / Containers
- **Corner Style:** raio grande do tema (`--radius-lg`).
- **Background:** `surface`, com o acabamento do tema (gradiente em Tablet de Sala e Cubo).
- **Shadow Strategy:** Painel em repouso, Hover no painel de ação (ver Elevation & Depth).
- **Border:** 1px `line` (2px em Canais; fio forte em Cubo); o painel DSPico do Início leva a borda no acento a 45%.
- **Internal Padding:** 24px (28px no painel principal do Início, 22px nos secundários).

### Inputs / Fields
- **Style:** borda de fio forte, fundo `surface`, raio médio, peso 600; o cursor de inserção usa `accent-fg`; placeholders em `ink-mute` com opacidade total.
- **Focus:** borda passa à cor de seleção com halo de 3px a 25%.

### Navigation
- **Barra lateral:** itens de 14px/700 em `ink-soft`, raio médio, padding 10px 14px; hover em `surface-2`. Em Canais os itens são cápsulas.
- **Abas principais:** calha em cápsula (`surface-2`, borda de fio, 4px de padding e intervalo) com abas de 13px/700.
- **Abas internas do RouteDex:** a mesma cápsula, mas a aba ativa é discreta, painel com contorno de 1px em fio forte. A seleção-assinatura fica reservada à navegação principal, às abas de vista e ao seletor de tema.
- **Teclado:** setas nas abas, Alt+1 a Alt+4 nas vistas.

### Seleção-Assinatura (Signature Component)
Um só seletor compartilhado vale para `.nav-item--active`, `.adv-tab--active`, `.theme-item[aria-checked="true"]` e `.theme-mode[aria-checked="true"]`. A base é painel, texto `ink` e anel de 2px na cor de seleção; cada tema substitui só a decoração:
- **Dupla Tela:** moldura azul dupla (anel interior de 2px, espaço de 2px na cor do painel, anel exterior de 2px) sobre fundo da seleção a 10%. Chão: papel quadriculado de 16px.
- **Câmera Dupla:** etiqueta preenchida (`select-fill` com `on-select`) e um bico de 12×7px que aponta para baixo nas abas e para a direita na navegação. Chão: faixas horizontais suaves de 22px.
- **Canais:** anel ciano interior de 2px com halo difuso. Chão: risca fina horizontal a cada 4px.
- **Tablet de Sala:** cartão realçado com anel exterior de 4px, sombra da seleção e subida de 1px. Chão: losangos finos de 44px.
- **Cubo:** moldura dourada interior de 2px sobre gradiente dourado vertical. Chão: grelha de 24px sobre índigo.
- **Estéreo 3D:** quatro cantos verdes de 14×4px desenhados com gradientes, raio de 4px e fundo da seleção a 10%. Chão: xadrez de blocos de 96px na cor de seleção a 7%.
- **Híbrido:** anel duplo (1px interior, 3px de espaço, 3px exterior) sobre fundo da seleção a 14%. Chão: cinza liso.

Com `prefers-reduced-motion`, a seleção não anima nem se desloca.

### Foco
O foco de teclado é um contorno de 2px na cor do texto (`ink`), com 3px de afastamento (4px nos controlos com seleção-assinatura). Nunca usa a cor de seleção, para o item focado continuar distinguível do item ativo em todos os temas.

### Linhas de lista
Listas planas sem cartão: ligações de Mais ferramentas e objetivos do assistente são linhas de largura total com fio de 1px em cima e em baixo, texto 14–15px/800, chevron SVG de 16px em `ink-mute` à direita que passa a `ink` no hover, e hover em `surface-2`. Os objetivos do assistente juntam uma linha de "o que faz" (13px, `ink-soft`) e "quando" (12px, `ink-mute`).

### Ícones de estado
SVG inline de 16px, traço de 2px, pontas e junções redondas, `currentColor`, sempre acompanhados de texto `sr-only` ("Presente:" / "Faltando:"). A cor vem da linha (`ok` ou `ink-mute`). As marcas do RouteDex (favorito, concluído) usam o mesmo traço dentro de botões redondos; o favorito ativo preenche o coração.

### Primeiros passos
Lista ordenada em três colunas com o número em um círculo de 30px em `select-fill` / `on-select`, título de 15px/800 e texto de 13px.

## Do's and Don'ts

### Do:
- **Do** usar cores só como `rgb(var(--c-x))` ou `rgb(var(--c-x) / alfa)`, ou pelas classes Tailwind que as envolvem (`bg-accent/10`, `text-fg-mute`).
- **Do** acrescentar ou ajustar cores em `tools/build_themes.py` e regenerar com `python tools/build_themes.py`; confirmar com `--check` e `tests/test_themes.py`.
- **Do** colocar a assinatura de um tema (chão, acabamento, seleção) em `static/skins.css`, sob `html[data-family="…"]`, e mais nada.
- **Do** aplicar a seleção-assinatura através do seletor compartilhado; um controlo novo de "item escolhido" entra nessa lista em vez de inventar o seu próprio estado ativo.
- **Do** manter o foco como contorno de 2px na cor do texto, separado da seleção.
- **Do** usar cápsulas (999px) para botões, abas e chips, e o raio do tema (`--radius`, `--radius-lg`) para itens e painéis.
- **Do** escrever rótulos de seção em minúsculas de frase, Nunito 15px/800.
- **Do** desenhar ícones como SVG inline com `currentColor`, traço de 2px e pontas redondas.

### Don't:
- **Don't** editar `static/themes.css` ou `static/theme-data.js` à mão.
- **Don't** usar logotipos, ícones, fontes, sons ou nomes de marca da Nintendo, nem dar nomes de console aos temas.
- **Don't** imitar hardware: sem bezel, botões falsos ou cópia literal de menus de console.
- **Don't** mudar layout, navegação, tamanhos ou controlos por tema; um tema só troca chão, acabamento e gesto de seleção.
- **Don't** usar a assinatura nas abas internas do RouteDex nem em sub-abas; a seleção discreta mantém a hierarquia.
- **Don't** pôr texto sobre `select` cru; texto sobre a seleção usa `select-fill` com `on-select`.
- **Don't** pôr texto funcional abaixo de 11px nem voltar aos rótulos em maiúsculas com tracking.
- **Don't** pôr um cartão dentro de outro; subpassos e listas ficam planos dentro do painel, separados por fios.
