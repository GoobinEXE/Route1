#ifndef ROUTE1_UI_H
#define ROUTE1_UI_H

#include "route1/fs.h"

void r1_ui_init(void);
void r1_ui_shutdown(void);

void r1_ui_show_message(const char *title_pt, const char *body_pt);

/* strong=1: exige confirmar com X (além de A). Devolve 1 se sim. */
int r1_ui_confirm(const char *title_pt, const char *body_pt, int strong);

void r1_ui_draw_browser(const char *rel_dir, const r1_fs_entry_t *ents, int count,
                        int cursor, int scroll, unsigned long long free_bytes,
                        const char *status_pt);

#endif
