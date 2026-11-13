#ifdef R1_HAVE_LIBNDS

#include "route1/ui.h"

#include "route1/input.h"
#include "route1/version.h"

#include <nds.h>

#include <stdio.h>
#include <string.h>

static PrintConsole g_top;
static PrintConsole g_bot;

static void fmt_size(char *buf, size_t buf_sz, unsigned long long n)
{
    if (n >= 1024ull * 1024ull)
        snprintf(buf, buf_sz, "%lluM", n / (1024ull * 1024ull));
    else if (n >= 1024ull)
        snprintf(buf, buf_sz, "%lluK", n / 1024ull);
    else
        snprintf(buf, buf_sz, "%lluB", n);
}

void r1_ui_init(void)
{
    videoSetMode(MODE_0_2D);
    videoSetModeSub(MODE_0_2D);
    vramSetBankA(VRAM_A_MAIN_BG);
    vramSetBankC(VRAM_C_SUB_BG);
    consoleInit(&g_top, 3, BgType_Text4bpp, BgSize_T_256x256, 31, 0, true, true);
    consoleInit(&g_bot, 3, BgType_Text4bpp, BgSize_T_256x256, 31, 0, false, true);
}

void r1_ui_shutdown(void)
{
}

void r1_ui_show_message(const char *title_pt, const char *body_pt)
{
    consoleSelect(&g_top);
    consoleClear();
    iprintf("%s\n\n%s\n\nA: OK", title_pt ? title_pt : "", body_pt ? body_pt : "");
    consoleSelect(&g_bot);
    consoleClear();
    for (;;) {
        r1_input_wait_frame();
        if (r1_input_keys_down() & (R1_KEY_A | R1_KEY_START | R1_KEY_B))
            break;
    }
}

int r1_ui_confirm(const char *title_pt, const char *body_pt, int strong)
{
    int armed = 0;

    consoleSelect(&g_top);
    consoleClear();
    iprintf("%s\n\n%s\n", title_pt ? title_pt : "?", body_pt ? body_pt : "");
    if (strong)
        iprintf("\nA continua, X confirma, B cancela");
    else
        iprintf("\nA sim, B nao");

    consoleSelect(&g_bot);
    consoleClear();

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
                consoleSelect(&g_bot);
                consoleClear();
                iprintf("X para confirmar");
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
    char free_s[16];
    int i;
    const int rows = 12;

    fmt_size(free_s, sizeof free_s, free_bytes);

    consoleSelect(&g_top);
    consoleClear();
    iprintf("%s %s\n", R1_APP_NAME, R1_APP_VERSION);
    iprintf("Dir: %.28s\n", rel_dir ? rel_dir : ".");
    iprintf("Livre: %s\n", free_s);
    iprintf("%s\n", status_pt ? status_pt : "");
    iprintf("A abrir B subir X apagar\nY Games R Apps START sair");

    consoleSelect(&g_bot);
    consoleClear();
    if (count <= 0) {
        iprintf("(vazio)\n");
        return;
    }
    for (i = scroll; i < count && i < scroll + rows; ++i) {
        char sz[12];
        char line[33];
        if (ents[i].is_dir)
            strncpy(sz, "DIR", sizeof sz);
        else
            fmt_size(sz, sizeof sz, ents[i].size);
        snprintf(line, sizeof line, "%s%-20.20s %6s", i == cursor ? ">" : " ",
                 ents[i].name, sz);
        iprintf("%s\n", line);
    }
}

#endif /* R1_HAVE_LIBNDS */
