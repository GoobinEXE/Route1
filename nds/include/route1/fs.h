#ifndef ROUTE1_FS_H
#define ROUTE1_FS_H

#include <stddef.h>

#define R1_FS_MAX_ENTRIES 200
#define R1_FS_NAME_MAX 256

typedef struct {
    char name[R1_FS_NAME_MAX];
    int is_dir;
    unsigned long long size;
} r1_fs_entry_t;

/* root_abs: caminho absoluto do volume (host) ou "fat:/" / "" no NDS. */
int r1_fs_init(const char *root_abs);
void r1_fs_shutdown(void);
const char *r1_fs_root(void);

/*
 * Lista rel_dir ("" ou "." = raiz). Ordena pastas primeiro, depois nome.
 * Devolve contagem (0..max) ou código R1_E_* negativo.
 */
int r1_fs_list(const char *rel_dir, r1_fs_entry_t *out, int max_entries);

/* Apaga ficheiro ou pasta (recursivo). critical_ok=1 após aviso forte na UI. */
int r1_fs_delete(const char *rel_path, int critical_ok);

unsigned long long r1_fs_free_bytes(void);
int r1_fs_exists(const char *rel_path, int *is_dir_out);

#endif
