# Política de segurança — Route Pico

## Versões suportadas

| Versão | Suportada |
|--------|-----------|
| 1.2.x  | Sim |
| 1.0.x e anteriores | Não (atualize para a 1.2) |

Correções de segurança serão aplicadas na linha suportada atual (`1.2.x`). A versão 1.1 não chegou a ser publicada.

## Como reportar uma vulnerabilidade

**Não** abra issues públicas com detalhes exploráveis (path traversal, bypass de montagem, escrita em disco interno, etc.).

1. Se o repositório tiver **GitHub Security Advisories** ativados, use *Report a vulnerability*.
2. Caso contrário, contacte o maintainer em privado (canal indicado no perfil do repositório quando existir remote) e inclua:
   - versão do app (`Route Pico x.y.z` na inicialização / `core.__version__`);
   - SO e como reproduzir;
   - impacto esperado (ex.: formatar volume não removível, ler paths fora do SD).

Resposta esperada: confirmação em até **14 dias**; correção ou mitigação documentada quando possível.

## Âmbito (in-scope)

- Escrita ou formatação em volumes que **não** deveriam passar em `is_safe_mount_path` / preflight
- Path traversal a partir de `mount_path` ou caminhos vindos da UI
- Bypass de `OP_LOCK` / operações concorrentes que corrompam o SD
- Comprometimento da verificação SHA-256 dos downloads pinados
- Fuga de dados sensíveis em logs (paths de utilizador sem redação)

## Fora de âmbito (out-of-scope)

- Risco de brick por Unlaunch / CFW na consola (comportamento esperado e avisado)
- Conteúdo ilegal de ROMs fornecidas pelo utilizador
- Vulnerabilidades apenas em binários upstream (TWiLight, Unlaunch Installer, etc.) — reporte aos projetos originais
- Engenharia social ou phishing genéricos

## Práticas relevantes

Ver também a secção [Aviso legal / Termos de uso](README.md#aviso-legal--termos-de-uso) e os pins em `core/cache.py`.
