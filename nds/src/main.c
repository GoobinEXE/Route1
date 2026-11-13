/*
 * Route Pico (console) — entrada (Fase 1: gestor de ficheiros).
 *
 * Host:  ./build/routepico_host --sd <pasta>
 * NDS:   fatInit via r1_fs_init(NULL)
 */

#include "route1/r1.h"

#include <stdio.h>
#include <string.h>

#ifdef R1_HAVE_LIBNDS
#include <nds.h>
#endif

static void usage(const char *argv0)
{
    fprintf(stderr,
            "Uso: %s --sd <pasta_simulada>\n"
            "  Simula o microSD numa pasta do PC (Fase 1 host-sim).\n",
            argv0 ? argv0 : "routepico_host");
}

int main(int argc, char **argv)
{
    const char *sd = NULL;
    int i;
    int rc;

#ifdef R1_HAVE_LIBNDS
    (void)argc;
    (void)argv;
    sd = NULL;
#else
    for (i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--sd") == 0 && i + 1 < argc) {
            sd = argv[++i];
        } else if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            usage(argv[0]);
            return 0;
        } else {
            fprintf(stderr, "Argumento desconhecido: %s\n", argv[i]);
            usage(argv[0]);
            return 2;
        }
    }
    if (!sd) {
        usage(argv[0]);
        return 2;
    }
#endif

    r1_input_init();
    r1_ui_init();

    rc = r1_fs_init(sd);
    if (rc != R1_OK) {
        r1_ui_show_message("Erro", "Não foi possível montar o cartão / pasta SD.");
        r1_ui_shutdown();
        return 1;
    }

    r1_ui_show_message(
        R1_APP_NAME,
        "Gestor de ficheiros (Fase 1).\n"
        "Não apagues _picoboot.nds nem _pico\n"
        "sem teres a certeza.");

    rc = r1_app_run();

    r1_fs_shutdown();
    r1_ui_shutdown();
    return rc;
}
