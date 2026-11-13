# Manual do utilizador — Route Pico no console

*(Fase 1: gestor local. Os ecrãs podem mudar; a ligação USB ao Route Pico no PC chega na fase 2.)*

## O que faz

O **Route Pico** também tem um programa para o teu Nintendo DS/DSi (recomendado **DSPico**) que:

1. Deixa-te **ver e organizar** ficheiros no cartão microSD
2. Liga-se ao **Route Pico** no computador por **USB** para copiar jogos e ficheiros com verificação

Não descarrega jogos da internet. Não substitui o menu Pico Launcher: abres o Route Pico a partir dele (pasta `Apps/`).

## Requisitos

- Consola DS / DSi / 3DS com flashcart compatível (**DSPico** para USB)
- microSD preparado (o Route Pico no PC faz isso em DSPico → Preparar SD)
- Pico Launcher / loader conforme guia oficial LNH
- Cabo USB do DSPico + computador com o Route Pico

## Instalação (previsto)

1. No PC, com o cartão acessível, o Route Pico instala `RoutePico.nds` em `Apps/`.
2. No console, abre o Pico Launcher → Apps → **Route Pico**.
3. Na primeira abertura, lê o aviso sobre ops destrutivas (apagar ficheiros).

## Usar o gestor de ficheiros

1. Abre o Route Pico no console.
2. Navega com o D-Pad / toque (conforme UI final).
3. Pastas úteis: `Games/` (jogos), `Apps/` (programas), `_pico/` (sistema do launcher — **cuidado**).
4. Para apagar ou mover: confirma no diálogo.
5. Não apagues `_picoboot.nds` nem a pasta `_pico` a menos que saibas o que fazes — o cartão pode deixar de arrancar o menu.

## Transferir com o PC (USB)

### Ideia geral

O caminho mais seguro e rápido é: **console em modo USB** + **Route Pico no PC** a copiar com verificação.

1. No console, escolhe **Ligar USB / Modo PC**.
2. Liga o cabo USB do DSPico ao computador.
3. Abre o Route Pico no PC; espera que detete o cartão.
4. Escolhe ficheiros no PC e envia para a pasta desejada no SD.
5. Espera a barra chegar a 100 % e a mensagem de **verificado**.
6. Só então ejeta / desliga com segurança e sai do modo USB no DSi.

### Se o cabo desligar a meio

- O Route Pico (PC e console) indica a falha.
- Pode ficar um ficheiro temporário (extensão `.r1partial`) — não uses como jogo.
- Volta a ligar e **retoma** ou apaga o parcial e copia de novo.

### Boas práticas

- Não tires o cartão nem resets a consola a meio da cópia.
- Mantém o console acordado durante a transferência.
- Prefere pastas claras (`Games/nds/…`) em vez da raiz cheia.

## O que este app *não* faz

- Não é loja de jogos online
- Não formata o cartão (usa o Route Pico no PC)
- Não instala Unlaunch / softmod (Route Pico no PC, em Mais ferramentas)

## Problemas frequentes

| Sintoma | O que tentar |
|---------|----------------|
| PC não vê o cartão | Cabo dados (não só carga); modo USB activo no DSi; drivers; outro porto |
| Após USB a consola “trava” | Bug conhecido em alguns firmware DSPico: desliga USB, reset, ciclo de energia (ver notas LNH) |
| Ficheiro não corre | Confirma extensão/pasta; verifica se a cópia terminou com hash OK |
| Sem espaço | Liberta espaço no gestor ou no PC antes de copiar |

## Privacidade

Tudo corre no teu hardware local. Não há conta na cloud nem envio de telemetria.
