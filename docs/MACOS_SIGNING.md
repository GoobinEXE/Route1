# Assinatura e notarização no macOS

Para um app baixado da internet abrir com dois cliques no macOS, sem o aviso de "desenvolvedor não identificado", ele precisa de duas coisas: estar **assinado** com um certificado **Developer ID Application** e estar **notarizado** pela Apple (a Apple confere o app e devolve um "tíquete" que fica grampeado nele com `stapler`).

O Route Pico é assinado com o certificado Developer ID da conta de desenvolvedor do mantenedor, que aparece como autor no aviso do macOS. O nome de estúdio **Dark Room** vale só para o Windows (Authenticode, ver [`WINDOWS_SIGNING.md`](WINDOWS_SIGNING.md)); a Apple mostra o nome cadastrado na conta de desenvolvedor.

## O que já está pronto no repositório

| Peça | Papel |
|------|-------|
| [`packaging/RoutePico.spec`](../packaging/RoutePico.spec) | Lê `ROUTE_PICO_CODESIGN_IDENTITY`; o PyInstaller assina cada binário de dentro para fora com hardened runtime e timestamp. Versão do Info.plist vem de `core/__init__.py`. |
| [`packaging/macos/entitlements.plist`](../packaging/macos/entitlements.plist) | Única exceção do hardened runtime: `allow-unsigned-executable-memory`, exigida pelo ctypes/libffi do pywebview. Sem sandbox nem outras permissões. |
| [`tools/build_macos_release.sh`](../tools/build_macos_release.sh) | Encontra o certificado, assina, verifica, notariza o app, grampeia o tíquete, gera ZIP e DMG, assina e notariza o DMG e confere com o Gatekeeper (`spctl`). |
| [`.github/workflows/release.yml`](../.github/workflows/release.yml) | Em tags `v*`, importa o certificado num keychain temporário, assina e notariza. Sem os secrets, o build do macOS falha de propósito em vez de publicar um app sem assinatura. |

## Passo 1: criar o certificado Developer ID Application (uma vez)

Os certificados "Apple Development" e "Apple Distribution" não servem: o primeiro é para testes no próprio Mac e o segundo só vale para a App Store. A distribuição fora da App Store exige **Developer ID Application**, e só o **Account Holder** da conta pode criá-lo.

1. Abra o Xcode → **Settings** → **Accounts**, selecione a conta e o time.
2. Clique em **Manage Certificates…**, depois em **+** e escolha **Developer ID Application**.
3. Confira no Terminal:

```bash
security find-identity -v -p codesigning
```

Deve aparecer uma linha `"Developer ID Application: <seu nome> (<TEAM ID>)"`. O script de build usa essa identidade automaticamente.

Guarde uma cópia do certificado com a chave privada: no app **Acesso às Chaves**, clique com o botão direito no certificado → **Exportar…** → formato `.p12`, com senha. Esse arquivo também é o que vai para o CI (passo 4).

## Passo 2: guardar as credenciais de notarização (uma vez)

1. Em [account.apple.com](https://account.apple.com) → **Iniciar sessão e segurança** → **Senhas específicas de apps**, crie uma senha chamada, por exemplo, "notarytool".
2. No Terminal, rode o comando abaixo trocando o e-mail e o Team ID (o código de 10 caracteres entre parênteses no passo 1). Ele pede a senha específica e a guarda no Keychain, com o nome de perfil `RoutePico`:

```bash
xcrun notarytool store-credentials RoutePico --apple-id "SEU_EMAIL_DA_APPLE" --team-id "SEU_TEAM_ID"
```

A senha nunca fica no repositório nem em variáveis de ambiente; o script usa o perfil do Keychain.

## Passo 3: gerar a release assinada no Mac

```bash
source .venv/bin/activate
pip install "pyinstaller>=6.11,<7"
ROUTE_PICO_REQUIRE_SIGNING=1 ./tools/build_macos_release.sh
```

Com `ROUTE_PICO_REQUIRE_SIGNING=1` o script para com erro se faltar o certificado ou as credenciais, em vez de gerar um app sem notarização. A notarização leva de um a alguns minutos por envio (são dois: o app e o DMG). No fim, o `spctl` deve mostrar `accepted` e `source=Notarized Developer ID` para o app e o DMG em `release_artifacts/`.

Para publicar esses arquivos numa release que já existe no GitHub (por exemplo, se o CI ainda não tiver os secrets):

```bash
gh release upload v1.2.0 release_artifacts/Route-Pico-1.2.0-macOS-arm64-*.{zip,dmg} --clobber
```

### Variáveis aceitas pelo script

| Variável | Uso |
|----------|-----|
| `ROUTE_PICO_CODESIGN_IDENTITY` | Força uma identidade. Sem ela, usa a primeira "Developer ID Application" do Keychain. |
| `ROUTE_PICO_NOTARY_PROFILE` | Perfil do `notarytool store-credentials` (padrão `RoutePico`). |
| `ROUTE_PICO_NOTARY_KEY`, `_KEY_ID`, `_ISSUER` | Chave de API do App Store Connect (`.p8`), usada no CI no lugar do perfil. |
| `ROUTE_PICO_REQUIRE_SIGNING=1` | Falha se não puder assinar e notarizar. |
| `ROUTE_PICO_ALLOW_DEV_IDENTITY=1` | Aceita "Apple Development" só para testar o hardened runtime no próprio Mac (não notariza, não serve para distribuir). |

## Passo 4 (opcional): assinar também no GitHub Actions

Com estes secrets, as tags `v*` publicam o app do macOS já assinado e notarizado:

| Secret | Conteúdo |
|--------|----------|
| `MACOS_CERT_P12` | O `.p12` do passo 1 em base64: `base64 -i DeveloperID.p12 \| gh secret set MACOS_CERT_P12` |
| `MACOS_CERT_PASSWORD` | Senha usada ao exportar o `.p12` |
| `MACOS_NOTARY_KEY_P8` | Chave de API do App Store Connect em base64 (App Store Connect → **Usuários e acesso** → **Integrações** → **Chaves da equipe**, papel Developer): `base64 -i AuthKey_XXXX.p8 \| gh secret set MACOS_NOTARY_KEY_P8` |
| `MACOS_NOTARY_KEY_ID` | Key ID da chave de API |
| `MACOS_NOTARY_ISSUER_ID` | Issuer ID mostrado na mesma página |

O workflow cria um keychain temporário, importa o certificado, roda o build com `ROUTE_PICO_REQUIRE_SIGNING=1` e apaga o keychain e a chave no fim, mesmo se o build falhar.

## Problemas comuns

**"Apple Development não serve para distribuir"**: o script encontrou só certificados de desenvolvimento. Crie o Developer ID Application (passo 1).

**Notarização "Invalid"**: o script imprime o relatório da Apple (`notarytool log`). As causas mais comuns são um binário sem hardened runtime ou sem timestamp; o PyInstaller cuida dos dois quando recebe a identidade, então um binário copiado à mão para dentro do `.app` depois do build é o suspeito habitual.

**O app abre e fecha na hora**: falta o entitlement de memória executável no executável principal; o script verifica isso antes de notarizar.

**Mac com processador Intel**: o build sai para a arquitetura do Mac que o gera (`arm64` num Apple Silicon e no runner `macos-latest`). Um build Intel precisa ser gerado num Mac Intel ou num runner Intel, com o mesmo script.
