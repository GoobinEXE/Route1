#include "route1/ui.h"

#include "route1/version.h"

void r1_ui_init(void)
{
    /* Fase 1: consolas dual screen / gfx. */
}

void r1_ui_frame(void)
{
}

void r1_ui_show_message(const char *title_pt, const char *body_pt)
{
    (void)title_pt;
    (void)body_pt;
    (void)R1_APP_NAME;
    /* Em build com libnds: imprimir nos ecrãs. */
}
