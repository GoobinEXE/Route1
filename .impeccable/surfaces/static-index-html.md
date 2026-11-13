---
version: 1
slug: "static-index-html"
primary_target: "static/index.html"
related_targets: ["static/app.css","static/style.css","static/themes.css","static/theme.js"]
---

# Route Pico — shell da app (todas as vistas)

Scope: static/index.html e as suas vistas (Início, DSPico, Mais ferramentas, Definições). Visitor mode: Operate.

Audience/job: fãs de consolas Nintendo a preparar e manter o microSD do DSPico; tarefas curtas com o cartão ligado. Constraints: UI offline, PT, navegação e controlos padrão inalterados, contraste AA em 21 combinações (7 temas × 3 modos). Direção fixada pelo utilizador (sem roll): menus de consolas como inspiração, DS Lite padrão, Catppuccin nos modos claro/noturno.

## Direction contract

THESIS: Cada tema é a sala de estar de uma consola: o mesmo app de trabalho, mas com o chão, o vidro dos painéis e o gesto de seleção daquela consola. Recusa o "dashboard cinzento com um acento" e recusa o costume (bezel, botões falsos, cópia de menus).

OWN-WORLD: Nunito arredondada em toda a UI; raios generosos; um chão material por tema (papel quadriculado DS, risca fina Wii, cubos em relevo 3DS, grelha escura GameCube, cinza liso Switch); painéis claros com brilho subtil; a seleção é a assinatura: moldura azul dupla (Dupla Tela), etiqueta com bico (Câmera Dupla), anel ciano (Canais), cartão realçado (Tablet de Sala), moldura dourada (Cubo), cantos verdes (Estéreo 3D), anel duplo (Híbrido).

STORY: O visitante reconhece "a sua" consola no primeiro olhar, encontra o cartão e as ações sem reaprender nada, e troca de tema ou modo em dois cliques.

FIRST VIEWPORT: Barra lateral com marca e as quatro vistas; barra de cima com cartão, progresso e seletor de tema; conteúdo com dois painéis de ação (DSPico em destaque, Mais ferramentas) sobre o chão do tema; o item ativo da navegação mostra a seleção-assinatura.

FORM: Shell de produto padrão (rail + topbar + abas), mundo só em tipo, paleta, densidade e um gesto de seleção. Lista ordenada: 1. seleção-assinatura por tema. Origem: direção fixada pelo utilizador (sete temas, Catppuccin claro e noturno); sem sorteio de conceitos.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
