#include "route1/err.h"
#include "route1/path.h"
#include "route1/protect.h"

#include <stdio.h>
#include <string.h>

static int fails;

static void expect(int cond, const char *msg)
{
    if (!cond) {
        fprintf(stderr, "FAIL: %s\n", msg);
        fails++;
    }
}

int main(void)
{
    char buf[64];

    expect(r1_path_is_safe("Games/foo.nds"), "Games/foo.nds seguro");
    expect(r1_path_is_safe("."), ". seguro");
    expect(!r1_path_is_safe("../etc/passwd"), "traversal falha");
    expect(!r1_path_is_safe("/absolute"), "absoluto falha");
    expect(!r1_path_is_safe("a/../../b"), "traversal embutido falha");
    expect(r1_path_normalize(buf, sizeof buf, "Games//x.nds"), "normalize ok");
    expect(strcmp(buf, "Games/x.nds") == 0, "normalize resultado");
    expect(r1_path_join(buf, sizeof buf, "/sd", "Games/x.nds"), "join ok");
    expect(strcmp(buf, "/sd/Games/x.nds") == 0, "join resultado");
    expect(r1_path_join_rel(buf, sizeof buf, "Games", "a.nds"), "join_rel ok");
    expect(strcmp(buf, "Games/a.nds") == 0, "join_rel resultado");
    expect(r1_path_parent(buf, sizeof buf, "Games/a.nds"), "parent ok");
    expect(strcmp(buf, "Games") == 0, "parent resultado");
    expect(r1_protect_is_critical("_picoboot.nds"), "picoboot crítico");
    expect(r1_protect_is_critical("_pico/settings.json"), "_pico filho crítico");
    expect(!r1_protect_is_critical("Games/foo.nds"), "jogo não crítico");
    expect(strcmp(r1_err_str_pt(R1_E_DENIED), "Operação negada (ficheiro protegido).") == 0,
           "err pt");

    if (fails) {
        fprintf(stderr, "%d falha(s)\n", fails);
        return 1;
    }
    puts("test_path: ok");
    return 0;
}
