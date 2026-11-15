# Vendor

## `GEiv4.2_EN` (não distribuído)

O kernel e o MoonShell do flashcard **Galaxy Eagle i (GEi)** são software do fabricante, sem licença que permita redistribuição. Por isso a pasta `vendor/GEiv4.2_EN` **não faz parte do repositório nem do app** (está no `.gitignore` e fora do `packaging/RoutePico.spec`).

O Route Pico procura o pacote, nesta ordem:

1. `~/Downloads/GEiv4.2_EN` (o caminho que o assistente pede ao usuário);
2. `~/.route_1_kit_cache/GEiv4.2_EN`;
3. `vendor/GEiv4.2_EN` numa cópia local de desenvolvimento, se existir.

Arquivos obrigatórios na raiz: `_DS_MENU.DAT` e `_DS_MSHL.NDS`; `_DS_MENU.INI`, `_SYSTEM_/` e `MOONSHL/` são copiados se existirem.
