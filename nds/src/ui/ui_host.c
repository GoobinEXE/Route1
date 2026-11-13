#ifndef R1_HAVE_LIBNDS

#include "route1/ui.h"

#include "route1/input.h"
#include "route1/version.h"

#include <stdio.h>
#include <string.h>

static void cls(void)
{
    fputs("\033[2J\033[H", stdout);
}

static void fmt_size(char *buf, size_t buf_sz, unsigned long long n)
{
    if (n >= 1024ull * 1024ull * 1024ull)
        snprintf(buf, buf_sz, "%.1f GB", n / (1024.0 * 1024.0 * 1024.0));
    else if (n >= 1024ull * 1024ull)
        snprintf(buf, buf_sz, "%.1f MB", n / (1024.0 * 1024.0));
    else if (n >= 1024ull)
        snprintf(buf, buf_sz, "%.1f KB", n / 1024.0);
    else
        snprintf(buf, buf_sz, "%llu B", (unsigned long long)n);
}

void r1_ui_init(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
}

void r1_ui_shutdown(void)
{
}

void r1_ui_show_message(const char *title_pt, const char *body_pt)
{
    cls();
    printf("=== %s ===\n%s\n\n[A/Enter] continuar\n", title_pt ? title_pt : "",
           body_pt ? body_pt : "");
    for (;;) {
        r1_input_wait_frame();
        if (r1_input_keys_down() & (R1_KEY_A | R1_KEY_START | R1_KEY_B))
            break;
    }
}

int r1_ui_confirm(const char *title_pt, const char *body_pt, int strong)
{
    int armed = 0;

    cls();
    printf("=== %s ===\n%s\n\n", title_pt ? title_pt : "Confirmar",
           body_pt ? body_pt : "");
    if (strong)
        printf("[A] continuar · [X] confirmar apagar · [B] cancelar\n");
    else
        printf("[A] sim · [B] não\n");

    for (;;) {
        unsigned k;
        r1_input_wait_frame();
        k = r1_input_keys_down();
        if (!k)
            continue;
        if (strong) {
            if (k & R1_KEY_B)
                return 0;
            if (k & R1_KEY_A) {
                armed = 1;
                printf("Agora pressiona X para confirmar…\n");
                continue;
            }
            if ((k & R1_KEY_X) && armed)
                return 1;
        } else {
            if (k & R1_KEY_A)
                return 1;
            if (k & R1_KEY_B)
                return 0;
        }
    }
}

void r1_ui_draw_browser(const char *rel_dir, const r1_fs_entry_t *ents, int count,
                        int cursor, int scroll, unsigned long long free_bytes,
                        const char *status_pt)
{
    char free_s[32];
    int i;
    const int rows = 12;

    cls();
    fmt_size(free_s, sizeof free_s, free_bytes);
    printf("%s  v%s\n", R1_APP_NAME, R1_APP_VERSION);
    printf("Pasta: %s\n", rel_dir && rel_dir[0] ? rel_dir : ".");
    printf("Livre: %s\n", free_s);
    printf("----------------------------------------\n");

    if (count <= 0) {
        printf("  (vazio)\n");
    } else {
        for (i = scroll; i < count && i < scroll + rows; ++i) {
            char sz[32];
            const char *mark = (i == cursor) ? ">" : " ";
            if (ents[i].is_dir)
                snprintf(sz, sizeof sz, "<DIR>");
            else
                fmt_size(sz, sizeof sz, ents[i].size);
            printf("%s %s%-40s %8s\n", mark, ents[i].is_dir ? "/" : " ",
                   ents[i].name, sz);
        }
    }

    printf("----------------------------------------\n");
    printf("%s\n", status_pt ? status_pt : "");
    printf("W/S ou ↑↓ · A abrir · B subir · X apagar · Y Games · R Apps · Q sair\n");
}

#endif /* !R1_HAVE_LIBNDS */
