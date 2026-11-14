# Paridade de UI — Route Pico v2

Gate de cada iteração da Fase 2+. Nenhuma funcionalidade de usuário pode desaparecer; só mudar de lugar.

## Orçamento de performance

| Métrica | Alvo |
|---------|------|
| Arranque até interactivo | &lt; 1,5 s |
| Troca de vista | só `hidden` / mount preguiçoso |
| Listas &gt; 200 itens | virtualizadas |
| Logs / busy em idle | push (`web_events`), sem polling |
| Progresso de ops longas | faixa topbar `#r1k-op-progress` (n/total, %, barra, tamanho, velocidade, ETA) via `web_events` `progress` + `core.progress.ProgressTracker` |
| CSS total | &lt; 40 KB (Tailwind purge + `app.css`) |
| Scripts | `defer`; módulos na 1.ª visita à vista |

## Navegação alvo

Menu de console: barra de status (seletor do microSD, progresso, hora, medidor), Início com dez blocos e o próximo passo do cartão, telas com Voltar e abas irmãs, barra de ícones (Início, Atividade, Configurações). Teclado: setas movem no Início e mudam de aba, Enter abre, Esc/Backspace voltam (ou fecham a Atividade), Alt+1…4 vão a Início / DSPico / Mais ferramentas / Configurações. Histórico por hash (`#dspico/games`).

| Vista | Abas |
|-------|------|
| Início | Estado do microSD (nome, espaço usado, próximo passo com botão, primeiros passos sem cartão); blocos Cartão, Jogos, RouteDex, Launcher, Emuladores e apps USB, Avançado, Softmod DSi, Flashcards R4/GEi, Biblioteca TWiLight, Manutenção; selos «Preparar» no Cartão e contagem de jogos em Jogos |
| DSPico | Cartão (estado com uma ação principal; recolhíveis: atualizações + Enhanced, saúde do cartão, reinstalar ou começar do zero, manuais) · Jogos (biblioteca primeiro; organizar pastas recolhido) · RouteDex (biblioteca por sistema → galeria; capas que faltam; estatísticas; capturas; pastas; cheats) · Launcher (`settings.json`, associações de arquivo, temas do launcher, fundos noturnos) · Emuladores e apps USB (emuladores, apps USB LNH) · Avançado (emunand, firmware) |
| Mais ferramentas | Softmod DSi (identificar, assistente só do SD do DSi, passos manuais) · Flashcards R4/GEi (assistente do cartucho: GEi, R4 e DSPico do zero) · Biblioteca TWiLight (`/roms/`, organizar, cheats, capas; recolhível Apps homebrew) · Manutenção (relatório, backup, limpeza, formatação) |
| Configurações (só na barra de ícones) | SteamGridDB, Aparência (tema e modo), Sobre (recolhível) |

## Métodos `Api` → destino

| Método | Destino |
|--------|---------|
| `get_disks` | Barra superior (volume) — global |
| `get_logs` / `clear_logs` | Gaveta Atividade (abre sozinha durante operações) |
| `get_about` / `open_external_url` | Configurações → Sobre |
| `get_homebrew_catalog` | Mais ferramentas → Biblioteca TWiLight → Apps homebrew |
| `inspect_sd` / `probe_kernels` / `quarantine_dcim` | Mais ferramentas → Softmod DSi / Flashcards R4/GEi |
| `setup_nand_dump` / `setup_unlaunch` / `setup_hiya` | Mais ferramentas → Softmod DSi (assistente + passos manuais) |
| `setup_godmode9i` / `install_cheats` / `copy_nand_backup` | Mais ferramentas → Softmod DSi (passos manuais) / Biblioteca TWiLight |
| `install_boxarts` / `fetch_rom_artwork` / `search_rom_artwork` / `apply_rom_artwork_url` / `set_rom_artwork` / `generate_twilight_artwork_batch` | Mais ferramentas → Biblioteca TWiLight |
| `setup_dspico` / `inspect_dspico` / `get_dspico_official_links` | DSPico → Cartão |
| `browse_dspico_games` / `import_dspico_games` / `delete_dspico_games` / `move_dspico_games` / `mkdir_dspico_games` / `organize_dspico` | DSPico → Jogos |
| `get/search/apply/set_dspico_artwork` / `get_dspico_game_artwork` / `get_dspico_game_previews` / `generate_dspico_artwork_batch` | DSPico → Jogos |
| `ensure_dspico_emunand` / `import_dspico_bios` / `import_dspico_twl_font` | DSPico → Avançado |
| `get_dspico_settings` / `set_dspico_settings` | DSPico → Launcher |
| `list_dspico_emulators` / `install_dspico_emulators` | DSPico → Emuladores e apps USB |
| `list_rp2_volumes` / `flash_dspico_firmware` | DSPico → Avançado |
| `get_routedex_overview` / `toggle_routedex_flag` / `set_routedex_stats` / `prune_routedex_entries` | DSPico → RouteDex → Biblioteca |
| `check_routedex_health` / `remove_routedex_items` | DSPico → Cartão → Saúde do cartão |
| `list/get/export/delete_routedex_screenshot(s)` | DSPico → RouteDex → Capturas |
| `get_routedex_folder_art` / `write_routedex_folder_banner` / `write_routedex_folder_cover` / `remove_routedex_folder_art` | DSPico → RouteDex → Pastas |
| `get_routedex_library` / `get_routedex_gallery` / `get_routedex_gallery_covers` | DSPico → RouteDex → Biblioteca (visão por sistema e galeria) |
| `get_missing_covers` / `fetch_missing_covers` | DSPico → RouteDex → Capas (e Jogos → Capas que faltam) |
| `get_routedex_stats` / `get_routedex_covers_by_name` | DSPico → RouteDex → Estatísticas |
| `get_routedex_compat` | DSPico → RouteDex → Biblioteca → galeria → Loader |
| `get_art_picker_context` / `search_art_catalog` / `get_art_catalog_thumbs` / `get_art_catalog_image` / `get_art_remote_image` / `pick_art_image` / `encode_art` / `get_icon_sources` / `save_game_art` | Janela de capa e ícone (galeria e Jogos) |
| `get_banner_context` / `get_banner_icon_sources` / `save_folder_banner` | Banner de pasta (Biblioteca → lápis do sistema; Pastas) |
| `get_file_associations` / `set_file_associations` | DSPico → Launcher → Associações de arquivo |
| `list_routedex_night_themes` / `generate/remove_routedex_night_backgrounds` | DSPico → Launcher |
| `get_routedex_cheats` / `pick_usrcheat_file` / `import_routedex_cheats` | DSPico → RouteDex → Cheats |
| `get_routedex_credits` | Sobre (créditos de terceiros) |
| `pick_dspico_*` / `pick_rom_files` / `pick_folder` / `pick_image_file` | Diálogos (FilePickerPort) |
| `setup_gei` / `setup_r4` | Mais ferramentas → Flashcards R4/GEi (assistente) |
| `organize_roms` / `browse_roms` / `list_roms` / `list_rom_dir` / `list_rom_tree` / `rom_details` / `mkdir_rom_dir` / `move_roms` / `import_roms` / `delete_roms` / `default_saves_backup_dir` | Mais ferramentas → Biblioteca TWiLight |
| `sd_report` / `backup` / `clean_sd` / `format_sd` | Mais ferramentas → Manutenção |
| `install_homebrew` | Mais ferramentas → Biblioteca TWiLight → Apps homebrew |
| `check_dspico_updates` / `install_dspico_component` (variante `official` / `enhanced`) | DSPico → Cartão → Atualizações |
| `list/set/import/create_pico_*_theme` | DSPico → Launcher |
| `install_dspico_usb_apps` | DSPico → Emuladores e apps USB |
| `get_prefs` / `set_prefs` | Configurações (incl. chave SteamGridDB) |

## Secções legadas → destino

A vista avançada escondida (`view-advanced`) e a realocação de painéis em tempo de execução (`shell.js`) foram removidas: cada painel vive no HTML da vista a que pertence.

| Secção legada | Destino |
|--------------|---------|
| Identificar o DSi | Mais ferramentas → Softmod DSi |
| Slot lateral — softmod (passos 1–3) + Softmod extra | Mais ferramentas → Softmod DSi → Passos manuais |
| Flashcard Slot-1 (GEi, R4, DSPico do zero) e o atalho «Pacote DSPico» | Mais ferramentas → Flashcards R4/GEi (assistente); o pacote DSPico só em DSPico → Cartão |
| Jogos no cartão / explorador ROMs + Conteúdo | Mais ferramentas → Biblioteca TWiLight |
| Manutenção (backup / limpar / formatar) | Mais ferramentas → Manutenção |
| Apps homebrew | Mais ferramentas → Biblioteca TWiLight → Apps homebrew |
| Utilidades (Emuladores, Apps USB, Capas, Temas) | DSPico → Emuladores e apps USB / Jogos / Launcher; Biblioteca TWiLight |
| Seletores de cartão do DSPico e do assistente | Seletor único na barra de cima |
| Log do assistente e log escondido | Gaveta Atividade |

## Checklist de gate (por entrega)

- [x] Todos os métodos `Api` da tabela têm UI alcançável
- [x] Confirmação tipada `FORMATAR` preservada (prompt); `APAGAR` nas mensagens de limpeza
- [x] Temas do app funcionam (Configurações → Aparência)
- [x] `pytest -q` verde (201)
- [x] Orçamento: virtual grid >200; push `web_events`; CSS tailwind+app ≈ 21 KB; shell de console
