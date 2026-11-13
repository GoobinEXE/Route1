# R1USB — protocolo USB entre o app do console e o Route Pico (desktop)

Versão **0.1.0**, estado **rascunho**: não implementar o formato final no fio sem subir a versão.
Os valores numéricos (tipos de mensagem, erros, limites) estão em [`messages.json`](messages.json), que é a fonte única desses números; este documento descreve o comportamento.

O nome R1USB e o magic `R1UB` vêm da fase Route 1 e ficam como estão: mudar seria uma alteração de protocolo.

## Objetivos e princípios

O protocolo procura throughput alto (bulk, chunks grandes) sem abrir mão da integridade (hash, staging, promote), com retoma, cancelamento limpo e versão explícita no handshake.

1. O PC (Route Pico desktop) orquestra as cópias grandes.
2. O console confirma cada commit e pode recusar caminhos inseguros.
3. Nunca há `PUT_DONE` de sucesso sem hash conferido e promote feito.
4. Uma transferência de escrita ativa por sessão no MVP.

## Versões

- `major.minor.patch` em `HELLO.protocol_version` (ASCII, ex. `0.1.0`).
- `major` incompatível: o console recusa a sessão.
- `minor` é compatível para trás dentro do mesmo `major` (só campos opcionais novos).

## Framing

Little-endian.

```
offset  size  campo
0       4     magic = 'R1UB' (0x42553152)
4       2     msg_type (uint16)
6       2     flags
8       4     payload_len (uint32)   // bytes a seguir; máx. limits.max_payload
12      4     seq (uint32)
16      N     payload
```

Na fase 3.1, com `flags & FLAG_CRC`, seguem 4 bytes de CRC32 LE após o payload.

## Sessão

```
PC                         Console
 |---- HELLO (ver) ------->|
 |<--- HELLO_ACK ----------|
 |---- LIST / PUT / GET -->|
 |<--- DATA / STATUS ------|
 |---- PUT_COMMIT -------->|
 |<--- PUT_DONE -----------|
 |---- BYE --------------->|
```

| Mensagem | Direção | Função |
|---|---|---|
| `HELLO` | PC → console | Versão do protocolo, capacidades |
| `HELLO_ACK` | console → PC | Versão aceite, espaço livre, `caps` |
| `LIST` / `LIST_RESULT` | PC → console / volta | Entradas (nome, tipo, tamanho) de um caminho relativo à raiz do SD |
| `PUT_BEGIN` | PC → console | Caminho, tamanho, SHA-256 esperado, `overwrite`, `resume_offset` |
| `PUT_CHUNK` / `PUT_STATUS` | PC → console / volta | Offset + dados; bytes recebidos ou erro |
| `PUT_COMMIT` / `PUT_DONE` | PC → console / volta | Pedido de promote; sucesso ou erro (hash/IO) |
| `GET_BEGIN` / `GET_CHUNK` | PC → console / volta | Leitura de um ficheiro do SD |
| `CANCEL`, `BYE`, `ERROR` | qualquer | Abortar a transferência, fechar sessão, erro com código `E_*` |

### Capacidades (`HELLO_ACK.caps`)

| Bit | Nome | Significado |
|---|---|---|
| 0 | `CAP_PUT` | Recebe ficheiros |
| 1 | `CAP_GET` | Envia ficheiros ao PC |
| 2 | `CAP_RESUME` | Retoma |
| 3 | `CAP_LIST` | Listagem remota |
| 4 | `CAP_MSC_HINT` | O console pode pedir modo MSC em vez de bulk |

## Integridade

- O staging é `<destino>.r1partial` (sufixo em `limits.partial_suffix`), na mesma pasta do destino.
- O receptor calcula SHA-256 em streaming durante `PUT_CHUNK` e compara com o digest de `PUT_BEGIN` antes do promote.
- Em sucesso: rename para o destino e sync do volume. Se o destino existe, só há overwrite com `overwrite=1`.
- Em `CANCEL` ou erro: apaga-se só o `.r1partial`; o destino antigo fica intacto.
- Retoma: `PUT_BEGIN` com `resume_offset > 0`, mesmo SHA-256 e tamanho; se o parcial não tiver esse tamanho, `E_RESUME_MISMATCH` e recomeça do zero.

## Caminhos

Só caminhos relativos à raiz do volume, sem `..`, sem NUL e sem prefixos absolutos de outro volume (`limits.max_path_bytes`). Apagar ou sobrescrever `_picoboot.nds` e apagar a árvore `/_pico` exige confirmação forte no console; sem ela, `E_DENIED`.

## Relação com MSC

O modo mass-storage (fase 2) não usa estas mensagens. Nele, o desktop aplica o mesmo contrato de integridade localmente (`copy_verified`, `OP_LOCK`) e o console só mostra o ecrã "USB ocupado", sem escrever no SD.

## Alterar o protocolo

Qualquer mudança a frames, `msg_type`, erros ou limites exige, no mesmo commit: subir a versão em `messages.json`, `nds/include/route1/version.h` e neste documento, registar a mudança abaixo, e ajustar `tests/test_protocol_messages.py`. Os dois lados vivem neste repositório; o teste falha se divergirem.

## Histórico

| Versão | Notas |
|---|---|
| 0.1.0 | Rascunho inicial (fase Route 1 DSi), unificado neste documento ao juntar os repositórios |
