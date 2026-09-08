# DSi SD Studio

**DSi SD Studio** é um app desktop multiplataforma (macOS, Windows e Linux) para automatizar e gerenciar a preparação de cartões SD para o **Nintendo DSi** e flashcards (como o **GEi / AceKard / R4**).

A interface abre em uma **janela nativa** via [pywebview](https://pywebview.flowrl.com/) — sem navegador e sem servidor HTTP.

---

## Recursos principais

1. **Detecção de cartões SD:** lista unidades externas montadas (capacidade, formato e espaço livre).
2. **Passo 1 — Exploit & backup da NAND:** Memory Pit + dumpTool como `boot.nds`.
3. **Passo 2 — TWiLight Menu++ & Unlaunch:** prepara o menu e o Safe Unlaunch Installer.
4. **Organizador de ROMs:** limpa nomes, sincroniza saves e separa por plataforma em `/roms/<nds|dsi|gba|…>/`.
5. **Modo Flashcard GEi:** instala o kernel Galaxy Eagle i.
6. **Utilitários:** backup do SD, limpeza de metadados e formatação FAT32.

---

## Requisitos

- Python 3.9+
- Dependências: `pywebview` e `py7zr` (veja `requirements.txt`)
- UI 100% offline (Tailwind e fontes embutidos em `static/`)

### Extras por sistema

| SO | Notas |
|----|--------|
| **macOS** | Usa `diskutil` / `dot_clean`; lista apenas volumes USB/SD removíveis |
| **Windows** | Formatação FAT32 pode exigir executar como Administrador; HD interno não é listado |
| **Linux** | Formatação usa `mkfs.vfat` (`dosfstools`); pode precisar de permissões elevadas |

Para regenerar o CSS Tailwind após alterar classes na UI:

```bash
npx --yes tailwindcss@3.4.17 -i ./static/tailwind.input.css -o ./static/tailwind.css --minify
```

---

## Instalação

Recomenda-se um ambiente virtual (necessário no macOS com Python do Homebrew):

```bash
cd /caminho/para/DSi-SD-Studio
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Os scripts `start.command` / `start.bat` criam o `.venv` automaticamente se ainda não existir.

---

## Como iniciar

### macOS — dois cliques
Abra a pasta no Finder e dê dois cliques em `start.command`.

### Windows — dois cliques
Execute `start.bat`.

### Terminal (qualquer SO)

```bash
cd /caminho/para/DSi-SD-Studio
source .venv/bin/activate   # se ainda não estiver ativo
python app.py
```

A janela do app abre automaticamente. Feche a janela para encerrar.

---

## Tecnologias

- **App shell:** Python 3 + pywebview (janela nativa)
- **UI:** HTML5, Tailwind CSS (compilado local), fontes locais, JavaScript
- **Lógica:** módulos em `core/` (discos, exploits, TWiLight, ROMs, limpeza, cache)
