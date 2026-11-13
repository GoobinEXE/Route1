---
version: 1
slug: "static-index-html"
primary_target: "static/index.html"
related_targets: ["static/app.css","static/skins.css","static/themes.css","static/theme.js","static/js/shell.js"]
---

# Route Pico — shell da app (todas as telas)

Scope: static/index.html e as suas telas (Início em forma de menu de console, telas do DSPico, Mais ferramentas, Configurações). Visitor mode: Operate.

Audience/job: fãs de consoles Nintendo preparando e mantendo o microSD do DSPico; tarefas curtas com o cartão conectado. Constraints: UI offline, pt-BR, todas as funções mantidas, contraste AA em 21 combinações (7 temas × 3 modos), sem logotipos, ícones, fontes ou nomes da Nintendo. Direção fixada pelo usuário (sem sorteio): redesign integral a partir das sete imagens de referência (DS Lite, DSi, Wii, Wii U, GameCube, 3DS, Switch); navegação "menu de console"; cada tema com o seu próprio arranjo do Início.

Tradução do modo Operate: o usuário fixou a navegação vinda dos menus; ela vale para o Início, a barra de status, a barra de ícones e a barra de dicas. As telas de trabalho continuam com controles web padrão (botões, abas, campos, listas), só vestidos pelo tema.

## Direction contract

THESIS: O app abre como o menu inicial de um console: o cartão em cima, as tarefas como blocos, uma barra de ícones embaixo e dicas de tecla. Cada tema reproduz a gramática do seu menu (arranjo, moldura, seleção, barra). Recusa a barra lateral de dashboard e o "mesmo layout com outra cor".

OWN-WORLD: Nunito arredondada; ícones SVG próprios coloridos por tarefa. Dupla Tela: papel quadriculado branco, caixas cinza de borda dupla, cantos azuis de seleção, duas telas empilhadas. Câmera Dupla: faixa listrada cinza-escura, tela de cima menta, balão com bico sobre a fileira de ícones, moldura azul com "Abrir". Canais: risca fina prata, canais brancos arredondados em grade 4×, barra curva com fio ciano, botões redondos e relógio grande. Tablet de Sala: vidro branco, quadrados de moldura grossa, bloco ciano selecionado com "Abrir", pontos de página, fileira de ícones coloridos. Cubo: preto com grade, painéis índigo-violeta biselados, títulos azuis espaçados, botão dourado, dicas com teclas coloridas. Estéreo 3D: lavanda de cubos macios, status grande, bandeja bege com blocos brancos e cantos menta. Híbrido: cinza claro, círculo do cartão, fileira de blocos quadrados grandes, doca redonda numa pílula com anel ciano duplo, "Enter OK".

STORY: O visitante reconhece "o seu" console no primeiro olhar, vê o estado do cartão, escolhe a tarefa com o mouse ou com as setas e Enter, e volta com Esc ou com o botão Voltar.

FIRST VIEWPORT: Barra de status (marca, seletor do microSD, progresso, hora, medidor de espaço como bateria); área do Início no arranjo do tema com o cartão em destaque e 12 blocos (6 DSPico, 5 Mais ferramentas, Configurações); legenda do item selecionado; barra de ícones (Início, Atividade, Tema, Configurações) e barra de dicas (setas Mover, Enter Abrir, Esc Voltar). Nas telas internas: cabeçalho com Voltar, ícone e título; abas irmãs como prateleira de ícones.

FORM: Menu de console, por tema. Lista ordenada: 1. arranjo do Início por tema; 2. barra de ícones e barra de dicas; 3. seleção-assinatura. Direção fixada pelo usuário (imagens de referência e respostas à pergunta estruturada); o sorteio rodou e a direção fixada venceu, como manda a regra de pin. seed:17efd0e5f2fba12e

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
