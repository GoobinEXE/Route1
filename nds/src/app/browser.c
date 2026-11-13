#include "route1/app.h"

#include "route1/err.h"
#include "route1/fs.h"
#include "route1/input.h"
#include "route1/path.h"
#include "route1/protect.h"
#include "route1/ui.h"
#include "route1/usb.h"
#include "route1/version.h"

#include <stdio.h>
#include <string.h>

#define VISIBLE_ROWS 12

static char g_dir[R1_PATH_MAX];
static r1_fs_entry_t g_ents[R1_FS_MAX_ENTRIES];
static int g_count;
static int g_cursor;
static int g_scroll;
static char g_status[128];
static int g_dirty = 1;

static void set_status(const char *msg)
{
    strncpy(g_status, msg ? msg : "", sizeof g_status - 1);
    g_status[sizeof g_status - 1] = '\0';
}

static void reload(void)
{
    int n = r1_fs_list(g_dir, g_ents, R1_FS_MAX_ENTRIES);
    if (n < 0) {
        g_count = 0;
        g_cursor = 0;
        g_scroll = 0;
        set_status(r1_err_str_pt(-n));
        g_dirty = 1;
        return;
    }
    g_count = n;
    if (g_cursor >= g_count)
        g_cursor = g_count > 0 ? g_count - 1 : 0;
    if (g_cursor < g_scroll)
        g_scroll = g_cursor;
    if (g_cursor >= g_scroll + VISIBLE_ROWS)
        g_scroll = g_cursor - VISIBLE_ROWS + 1;
    if (g_count >= R1_FS_MAX_ENTRIES)
        set_status("Lista truncada (máx. 200).");
    else if (!g_status[0])
        set_status("A/B navegar · X apagar · Y Games · START sair");
    g_dirty = 1;
}

static void go_dir(const char *rel)
{
    char norm[R1_PATH_MAX];
    int is_dir = 0;
    int rc;

    if (!r1_path_normalize(norm, sizeof norm, rel)) {
        set_status(r1_err_str_pt(R1_E_PATH));
        g_dirty = 1;
        return;
    }
    rc = r1_fs_exists(norm, &is_dir);
    if (rc != R1_OK || !is_dir) {
        set_status(rc != R1_OK ? r1_err_str_pt(-rc) : "Não é uma pasta.");
        g_dirty = 1;
        return;
    }
    memcpy(g_dir, norm, strlen(norm) + 1);
    g_cursor = 0;
    g_scroll = 0;
    g_status[0] = '\0';
    reload();
}

static void enter_selected(void)
{
    char next[R1_PATH_MAX];

    if (g_count <= 0 || g_cursor < 0 || g_cursor >= g_count)
        return;
    if (!g_ents[g_cursor].is_dir)
        return;
    if (!r1_path_join_rel(next, sizeof next, g_dir, g_ents[g_cursor].name)) {
        set_status(r1_err_str_pt(R1_E_PATH));
        g_dirty = 1;
        return;
    }
    go_dir(next);
}

static void go_up(void)
{
    char parent[R1_PATH_MAX];
    if (!r1_path_parent(parent, sizeof parent, g_dir))
        return;
    go_dir(parent);
}

static void do_delete(void)
{
    char target[R1_PATH_MAX];
    char body[256];
    int critical;
    int ok;
    int rc;

    if (g_count <= 0 || g_cursor < 0 || g_cursor >= g_count)
        return;
    if (r1_usb_state() != R1_USB_IDLE) {
        set_status(r1_err_str_pt(R1_E_BUSY));
        g_dirty = 1;
        return;
    }
    if (!r1_path_join_rel(target, sizeof target, g_dir, g_ents[g_cursor].name)) {
        set_status(r1_err_str_pt(R1_E_PATH));
        g_dirty = 1;
        return;
    }

    critical = r1_protect_is_critical(target) ? 1 : 0;
    if (critical) {
        snprintf(body, sizeof body,
                 "PROTEGIDO: %s\nApagar pode impedir o arranque do menu.\n"
                 "A=continuar, depois X=confirmar. B=cancelar.",
                 g_ents[g_cursor].name);
        ok = r1_ui_confirm("Aviso forte", body, 1);
    } else {
        snprintf(body, sizeof body, "Apagar %s%s?", g_ents[g_cursor].name,
                 g_ents[g_cursor].is_dir ? " (pasta e conteúdo)" : "");
        ok = r1_ui_confirm("Apagar", body, 0);
    }
    if (!ok) {
        set_status("Cancelado.");
        g_dirty = 1;
        return;
    }

    rc = r1_fs_delete(target, critical);
    if (rc != R1_OK)
        set_status(r1_err_str_pt(-rc));
    else
        set_status("Apagado.");
    reload();
}

int r1_app_run(void)
{
    unsigned keys;

    go_dir(".");
    set_status(R1_APP_NAME " " R1_APP_VERSION " — gestor");

    for (;;) {
        if (g_dirty) {
            r1_ui_draw_browser(g_dir, g_ents, g_count, g_cursor, g_scroll,
                               r1_fs_free_bytes(), g_status);
            g_dirty = 0;
        }

        r1_input_wait_frame();
        keys = r1_input_keys_down();
        if (!keys)
            continue;

        if (keys & R1_KEY_START)
            break;

        if (keys & R1_KEY_UP) {
            if (g_cursor > 0) {
                g_cursor--;
                if (g_cursor < g_scroll)
                    g_scroll = g_cursor;
                g_dirty = 1;
            }
        } else if (keys & R1_KEY_DOWN) {
            if (g_cursor + 1 < g_count) {
                g_cursor++;
                if (g_cursor >= g_scroll + VISIBLE_ROWS)
                    g_scroll = g_cursor - VISIBLE_ROWS + 1;
                g_dirty = 1;
            }
        } else if (keys & R1_KEY_A) {
            enter_selected();
        } else if (keys & R1_KEY_B) {
            go_up();
        } else if (keys & R1_KEY_X) {
            do_delete();
        } else if (keys & (R1_KEY_Y | R1_KEY_L)) {
            go_dir("Games");
        } else if (keys & R1_KEY_R) {
            go_dir("Apps");
        }
    }

    return 0;
}
