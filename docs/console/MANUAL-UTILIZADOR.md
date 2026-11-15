# Manual do usuário — Route Pico no console

*(Fase 1: gerenciador local. As telas podem mudar; a conexão USB com o Route Pico no PC chega na fase 2.)*

## O que faz

O **Route Pico** também tem um programa para o seu Nintendo DS/DSi (recomendado **DSPico**) que:

1. Permite **ver e organizar** arquivos no cartão microSD
2. Se conecta ao **Route Pico** no computador por **USB** para copiar jogos e arquivos com verificação

Não baixa jogos da internet. Não substitui o menu Pico Launcher: você abre o Route Pico a partir dele (pasta `Apps/`).

## Requisitos

- Console DS / DSi / 3DS com flashcart compatível (**DSPico** para USB)
- microSD preparado (o Route Pico no PC faz isso em DSPico → Preparar SD)
- Pico Launcher / loader conforme o guia oficial LNH
- Cabo USB do DSPico + computador com o Route Pico

## Instalação (previsto)

1. No PC, com o cartão acessível, o Route Pico instala `RoutePico.nds` em `Apps/`.
2. No console, abra o Pico Launcher → Apps → **Route Pico**.
3. Na primeira abertura, leia o aviso sobre operações destrutivas (apagar arquivos).

## Usar o gerenciador de arquivos

1. Abra o Route Pico no console.
2. Navegue com o direcional / toque (conforme a UI final).
3. Pastas úteis: `Games/` (jogos), `Apps/` (programas), `_pico/` (sistema do launcher — **cuidado**).
4. Para apagar ou mover: confirme no diálogo.
5. Não apague `_picoboot.nds` nem a pasta `_pico` se não souber o que está fazendo: o cartão pode parar de iniciar o menu.

## Transferir com o PC (USB)

### Ideia geral

O caminho mais seguro e rápido é: **console em modo USB** + **Route Pico no PC** copiando com verificação.

1. No console, escolha **Conectar USB / Modo PC**.
2. Conecte o cabo USB do DSPico ao computador.
3. Abra o Route Pico no PC e espere ele detectar o cartão.
4. Escolha os arquivos no PC e envie para a pasta desejada no SD.
5. Espere a barra chegar a 100 % e a mensagem de **verificado**.
6. Só então ejete / desconecte com segurança e saia do modo USB no DSi.

### Se o cabo desconectar no meio

- O Route Pico (PC e console) indica a falha.
- Pode sobrar um arquivo temporário (extensão `.r1partial`); não use como jogo.
- Conecte de novo e **retome**, ou apague o parcial e copie de novo.

### Boas práticas

- Não tire o cartão nem reinicie o console no meio da cópia.
- Mantenha o console ligado durante a transferência.
- Prefira pastas claras (`Games/nds/…`) a uma raiz cheia.

## O que este app *não* faz

- Não é loja de jogos online
- Não formata o cartão (use o Route Pico no PC)
- Não instala Unlaunch / softmod (Route Pico no PC, em Mais ferramentas)

## Problemas frequentes

| Sintoma | O que tentar |
|---------|----------------|
| PC não vê o cartão | Cabo de dados (não só de carga); modo USB ativo no DSi; drivers; outra porta |
| Após USB o console “trava” | Bug conhecido em alguns firmwares DSPico: desconecte o USB, reinicie, desligue e ligue (ver notas LNH) |
| Arquivo não roda | Confira extensão/pasta; veja se a cópia terminou com hash OK |
| Sem espaço | Libere espaço no gerenciador ou no PC antes de copiar |

## Privacidade

Tudo roda no seu hardware local. Não há conta na nuvem nem envio de telemetria.
