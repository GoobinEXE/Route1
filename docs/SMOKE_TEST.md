# Smoke test — Route 1 Kit

Checklist manual **antes** de uma release futura. Use um **cartão MicroSD dedicado a testes** (dados descartáveis).

## Preparação

- [ ] Python 3.9+ e dependências (`requirements.lock.txt` + `requirements-dev.txt`)
- [ ] `pytest -q` passa na máquina local
- [ ] Cartão de teste montado; anotar capacidade e letra/caminho
- [ ] Backup de qualquer conteúdo que ainda queira conservar (o format apaga tudo)

## Arranque

- [ ] macOS: `start.command` / Windows: `start.bat` / Linux: `./start.sh`
- [ ] Janela abre; versão visível no log/terminal (`0.9.x` ou superior)
- [ ] Lista de discos mostra só o SD de teste (não o disco do sistema)

## Assistente

- [ ] Escolher um objetivo (ex.: SD-direct) e avançar sem saltar avisos de NAND
- [ ] Etapa 1 (Memory Pit + dumpTool): conclui com sucesso no SD de teste
- [ ] Etapa 2 (TWiLight + Unlaunch installer no SD): conclui; ficheiros esperados presentes
- [ ] Aviso de brick / Unlaunch aparece antes da fase crítica na consola

## Modo avançado / utilitários

- [ ] **Formatar FAT32** só no SD de teste; diálogo de confirmação; volume legível depois
- [ ] **GEi** ou **R4** (conforme kernel disponível): instalação sem crash
- [ ] **Organizar ROMs**: confirmação; pastas `/roms/...` coerentes
- [ ] **Backup do SD** e **limpar metadados** (se aplicável) concluem com mensagem clara
- [ ] Segunda operação enquanto a primeira corre: rejeitada (“já em andamento”)

## UI

- [ ] Alternar tema (Studio / Catppuccin / etc.) e recarregar: preferência persiste
- [ ] Logs atualizam durante uma operação; limpar logs funciona

## Encerramento

- [ ] Fechar a janela encerra o processo sem orphan óbvio
- [ ] Anotar falhas com SO, versão do app e passo exato

Não execute Unlaunch na NAND de uma consola de produção só para este checklist; o foco é o PC + cartão de teste.
