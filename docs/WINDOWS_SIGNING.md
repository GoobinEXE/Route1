# Assinatura Windows (Authenticode) — Dark Room

O Windows **não** tem notarização como a Apple. Builds oficiais usam **Authenticode**
(Azure Artifact Signing, antigo Trusted Signing) com publisher **Dark Room**.

Sem certificado configurado, o CI continua a publicar ZIP + `setup.exe` **não assinados**
(SmartScreen pode avisar).

## O que já está no repo

| Peça | Papel |
|------|--------|
| `tools/build_windows_release.sh` | Fases `build` / `package` / `all`; assinatura local opcional via `.pfx` |
| `packaging/windows/Route1Kit.iss` | `AppPublisher=Dark Room`; `SignTool` se `ROUTE1_SIGN` |
| `.github/workflows/release.yml` | Assina `dist\Route1Kit` e o `setup.exe` se os secrets Azure existirem |

## Passos que só tu podes fazer

1. Conta Azure + recurso **Artifact Signing** (Trusted Signing).
2. Validação de identidade da organização/pessoa (**Dark Room** como nome no certificado).
3. App registration (ou managed identity) com papel
   **Artifact Signing Certificate Profile Signer**.
4. Federated credential OIDC para o GitHub
   (`repo:OWNER/REPO:ref:refs/tags/v*` e/ou `environment:…`).
5. Secrets / variáveis no repositório GitHub (abaixo).

## Secrets e variáveis (GitHub)

**Secrets** (Settings → Secrets and variables → Actions):

| Nome | Conteúdo |
|------|----------|
| `AZURE_CLIENT_ID` | Application (client) ID |
| `AZURE_TENANT_ID` | Directory (tenant) ID |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID |

**Variables** (Actions variables):

| Nome | Exemplo |
|------|---------|
| `AZURE_TRUSTED_SIGNING_ENDPOINT` | `https://eus.codesigning.azure.net/` (região da conta) |
| `AZURE_TRUSTED_SIGNING_ACCOUNT` | nome da Artifact Signing Account |
| `AZURE_TRUSTED_SIGNING_PROFILE` | nome do Certificate Profile |

Quando os três secrets **e** as três variables estiverem definidos, o job Windows do
`release.yml` faz login OIDC e assina `.exe` / `.dll` do onedir e o `*-setup.exe`.

## Assinatura local (PFX / OV)

Só para testes numa máquina Windows com Windows SDK:

```bash
export WINDOWS_PFX_PATH="/c/path/to/DarkRoom.pfx"
export WINDOWS_PFX_PASSWORD="…"   # se o PFX tiver password
./tools/build_windows_release.sh
```

Ou comando custom:

```bash
export WINDOWS_SIGNTOOL_CMD='signtool sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f …'
./tools/build_windows_release.sh
```

**Não** commits `.pfx` nem passwords.

## Fases do script (CI)

```bash
# 1) PyInstaller → dist/Route1Kit/
ROUTE1KIT_WIN_PHASE=build ./tools/build_windows_release.sh

# 2) (CI) azure/artifact-signing-action → Route1Kit.exe
# 3) ZIP + Inno
ROUTE1KIT_WIN_PHASE=package ./tools/build_windows_release.sh

# 4) (CI) assinar o setup.exe gerado
```

No CI assinamos só `Route1Kit.exe` e o `*-setup.exe` (não todas as DLLs do PyInstaller),
para não esgotar a quota do Artifact Signing.

## Verificar

Numa máquina Windows:

```bat
signtool verify /pa /v Route1Kit.exe
signtool verify /pa /v Route-1-Kit-*-windows-x64-setup.exe
```

O publisher deve aparecer como **Dark Room** (ou o Subject do certificado Azure).

## SmartScreen

Mesmo assinado, publishers novos podem ainda ver o aviso durante algum tempo.
Distribuição pela [página de Releases](https://github.com/GoobinEXE/Route1/releases) ajuda a reputação.
