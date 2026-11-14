# Teste manual antes de uma release

Roteiro para conferir cada build antes de publicar. Use um **microSD de teste** (ou faça antes o backup em Manutenção e confira que terminou sem erro): alguns passos gravam no cartão e a formatação apaga tudo.

## 1. Preparação

- [ ] `pytest -q` passa na máquina que gera o build, e o CI do GitHub está verde nos três sistemas.
- [ ] `docs/licenses/THIRD_PARTY_NOTICES.txt` foi gerado pelo build (data de hoje) e lista os pacotes desta plataforma.
- [ ] A versão em `core/__init__.py` é a mesma da entrada mais nova do `CHANGELOG.md` e da tag que vai ser criada.

## 2. Instalação e assinatura

- [ ] **macOS:** `spctl -a -vvv -t exec "/Applications/Route Pico.app"` responde `accepted` e `source=Notarized Developer ID`; o DMG passa em `spctl -a -vvv -t open --context context:primary-signature`.
- [ ] **macOS:** baixado do GitHub (com quarentena), o app abre com dois cliques e só pergunta se quer abrir um app da internet.
- [ ] **Windows:** o `setup.exe` instala e cria o atalho; se a assinatura Authenticode estiver ativa, as propriedades do arquivo mostram o publicador Dark Room.
- [ ] **Linux:** o `.tar.gz` portátil abre; o script do instalável cria o atalho `.desktop`.
- [ ] Configurações → Sobre mostra a versão certa e as novidades desta versão.

## 3. Início e cartão

- [ ] A lista de cartões mostra só o microSD de teste: nem o disco do sistema nem um DMG montado aparecem.
- [ ] O Início mostra o próximo passo certo para o estado do cartão.
- [ ] Cartão → Saúde do cartão identifica o launcher e o loader (com a versão da API) e não aponta problemas num cartão recém-preparado.

## 4. DSPico

- [ ] Jogos → Adicionar jogos com **Cada sistema na sua pasta** marcado: cada ROM vai para `Games/<sistema>/`, ganha capa quando há uma certa e o quadro de resultado aparece. Desmarcado, a ROM vai para a pasta aberta.
- [ ] RouteDex → Biblioteca mostra os sistemas e a galeria; a janela de capa e ícone sugere a capa da região certa, gera o ícone a partir da capa e grava os dois.
- [ ] RouteDex → Capas busca só as capas que faltam e deixa sem capa os jogos sem par exato.
- [ ] RouteDex → Estatísticas, Associações (adicionar e salvar uma extensão), Capturas, Saúde do cartão, Pastas (banner com ícone procurado) e Cheats abrem sem erro.
- [ ] A ficha **Loader** de um jogo de DS comercial mostra save e correções; a de um homebrew diz que o loader pula esses passos.
- [ ] Verificar atualizações lista as versões do cartão, do app e do GitHub.

## 5. Mais ferramentas

- [ ] Softmod DSi: o assistente avança até o Passo 1 num SD de teste e não deixa pular o backup da NAND.
- [ ] Flashcards R4/GEi: sem a pasta `GEiv4.2_EN` em Downloads, o assistente explica onde colocar o pacote oficial; com ela, instala.
- [ ] Biblioteca TWiLight e Manutenção (relatório, backup, limpeza) concluem com mensagem clara.
- [ ] Uma segunda operação enquanto outra grava é recusada com "Outra operação já está em andamento".

## 6. Aparência e encerramento

- [ ] Trocar o tema e o modo (claro, noturno, sistema) em Configurações → Aparência e reabrir o app: a escolha fica salva.
- [ ] Fechar a janela durante uma gravação é bloqueado; fechar parado encerra o processo.
- [ ] Anote qualquer falha com sistema, versão do app e o passo exato.

Não execute o Unlaunch na NAND de um console de uso diário só para este roteiro: o foco é o computador e o cartão de teste.
