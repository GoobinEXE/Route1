#include "route1/err.h"
#include "route1/fs.h"
#include "route1/path.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

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
    r1_fs_entry_t ents[R1_FS_MAX_ENTRIES];
    char root[] = "tests/fixtures/fake_sd";
    char scratch_rel[] = "scratch_to_delete.txt";
    int n;
    int rc;
    int is_dir = 0;

    /* Garantir scratch existe para o teste de delete. */
    {
        FILE *f = fopen("tests/fixtures/fake_sd/scratch_to_delete.txt", "w");
        expect(f != NULL, "criar scratch");
        if (f) {
            fputs("temp\n", f);
            fclose(f);
        }
    }

    rc = r1_fs_init(root);
    expect(rc == R1_OK, "fs_init");

    n = r1_fs_list(".", ents, R1_FS_MAX_ENTRIES);
    expect(n > 0, "list root");

    rc = r1_fs_exists("Games", &is_dir);
    expect(rc == R1_OK && is_dir, "Games existe");

    rc = r1_fs_delete("_picoboot.nds", 0);
    expect(rc == -R1_E_DENIED, "picoboot negado sem critical_ok");

    rc = r1_fs_delete("_pico", 0);
    expect(rc == -R1_E_DENIED, "_pico negado");

    rc = r1_fs_delete(scratch_rel, 0);
    expect(rc == R1_OK, "apagar scratch");
    rc = r1_fs_exists(scratch_rel, &is_dir);
    expect(rc == -R1_E_NOTFOUND, "scratch sumiu");

    /* Recriar scratch para próximos runs. */
    {
        FILE *f = fopen("tests/fixtures/fake_sd/scratch_to_delete.txt", "w");
        if (f) {
            fputs("temp\n", f);
            fclose(f);
        }
    }

    r1_fs_shutdown();

    if (fails) {
        fprintf(stderr, "%d falha(s)\n", fails);
        return 1;
    }
    puts("test_fs: ok");
    return 0;
}
