# Paridade de UI — Route 1 Kit v2

Gate de cada iteração da Fase 2+. Nenhuma funcionalidade de utilizador pode desaparecer; só mudar de sítio.

## Orçamento de performance

| Métrica | Alvo |
|---------|------|
| Arranque até interactivo | &lt; 1,5 s |
| Troca de vista | só `hidden` / mount preguiçoso |
| Listas &gt; 200 itens | virtualizadas |
| Logs / busy em idle | push (`web_events`), sem polling |
| CSS total | &lt; 40 KB (Tailwind purge + `app.css`) |
| Scripts | `defer`; módulos na 1.ª visita à vista |

## Navegação alvo

| Vista sidebar | Destino |
|---------------|---------|
| Início | Hero DSPico + Softmod; atalhos Utilidades; estado do cartão |
| DSPico | Flagship (prioridade máxima) |
| Softmod DSi | Wizard + extras |
| Utilidades | Emuladores / Apps / Capas·Ícones / Temas |
| Cartão SD | Manutenção + explorador `/roms/` |
| Outros flashcards | GEi / R4 (despromovido) |
| Definições e Sobre | Aparência (7 temas), About, logs |

## Métodos `Api` → destino

| Método | Destino |
|--------|---------|
| `get_disks` | Barra superior (volume) — global |
| `get_logs` / `clear_logs` | Gaveta Atividade + Definições |
| `get_about` / `open_external_url` | Definições e Sobre |
| `get_homebrew_catalog` | Utilidades → Apps |
| `inspect_sd` / `probe_kernels` / `quarantine_dcim` | Softmod / Cartão / Outros |
| `setup_nand_dump` / `setup_unlaunch` / `setup_hiya` | Softmod DSi |
| `setup_godmode9i` / `install_cheats` / `copy_nand_backup` | Softmod → Extras |
| `install_boxarts` / `fetch_rom_artwork` / `set_rom_artwork` | Softmod extras + Utilidades → Capas + Cartão |
| `setup_dspico` / `inspect_dspico` / `get_dspico_official_links` | DSPico |
| `browse_dspico_games` / `import_dspico_games` / `delete_dspico_games` / `move_dspico_games` / `mkdir_dspico_games` / `organize_dspico` | DSPico → Jogos |
| `get/search/apply/set_dspico_artwork` / `get_dspico_game_artwork` | DSPico → Capas + Utilidades |
| `ensure_dspico_emunand` / `import_dspico_bios` / `import_dspico_twl_font` | DSPico → Definições |
| `get_dspico_settings` / `set_dspico_settings` | DSPico → Definições |
| `list_dspico_emulators` / `install_dspico_emulators` | DSPico → Emuladores + Utilidades |
| `list_rp2_volumes` / `flash_dspico_firmware` | DSPico → Firmware |
| `pick_dspico_*` / `pick_rom_files` / `pick_folder` / `pick_image_file` | Diálogos (FilePickerPort) |
| `setup_gei` / `setup_r4` | Outros flashcards |
| `organize_roms` / `browse_roms` / `list_roms` / `list_rom_dir` / `list_rom_tree` / `rom_details` / `mkdir_rom_dir` / `move_roms` / `import_roms` / `delete_roms` / `default_saves_backup_dir` | Cartão SD |
| `sd_report` / `backup` / `clean_sd` / `format_sd` | Cartão SD → Manutenção |
| `install_homebrew` | Utilidades → Apps |
| `check_dspico_updates` / `install_dspico_component` | Início + DSPico (Verificar Atualizações) |
| `list/set/import/create_pico_*_theme` | Utilidades → Temas |
| `install_dspico_usb_apps` | Utilidades → Apps |
| `generate_dspico_covers_batch` | Utilidades → Capas |
| `get_prefs` / `set_prefs` | Definições |

## Secções legadas (`static/index.html` antigo) → destino

| Secção legada | Destino |
|--------------|---------|
| Identificar o DSi | Softmod → Identificar |
| Slot lateral — softmod (exploit / Unlaunch / hiya) | Softmod wizard |
| Flashcard Slot-1 (GEi) | Outros flashcards |
| Pacote DSPico (card antigo) | DSPico |
| Jogos no cartão / explorador ROMs | Cartão SD |
| Conteúdo (capas, cheats, …) | Softmod extras + Utilidades |
| Manutenção (backup / limpar / formatar) | Cartão SD |
| Softmod extra | Softmod → Extras |
| Apps homebrew | Utilidades → Apps |
| Atividade (logs) | Gaveta Atividade global |
| view-dspico | DSPico |
| view-about | Definições e Sobre |
| Temas (theme.js, 7 temas) | Definições → Aparência |

## Checklist de gate (por entrega)

- [x] Todos os métodos `Api` da tabela têm UI alcançável
- [x] Confirmação tipada `FORMATAR` preservada (prompt); `APAGAR` nas mensagens de limpeza
- [x] 7 temas da app funcionam (Definições + theme picker)
- [x] `pytest -q` verde (201)
- [x] Orçamento: virtual grid >200; push `web_events`; CSS tailwind+app ≈ 21 KB; shell sidebar
