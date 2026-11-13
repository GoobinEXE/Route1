#include "route1/integrity.h"

#include <stdio.h>
#include <string.h>

bool r1_integrity_partial_path(char *out, size_t out_sz, const char *final_path)
{
    size_t n;

    if (!out || !final_path || out_sz < 2)
        return false;
    n = strlen(final_path);
    if (n + strlen(R1_PARTIAL_SUFFIX) + 1 > out_sz)
        return false;
    memcpy(out, final_path, n + 1);
    strcat(out, R1_PARTIAL_SUFFIX);
    return true;
}

int r1_integrity_promote(const char *partial_path, const char *final_path,
                         const r1_sha256_t *expected)
{
    (void)partial_path;
    (void)final_path;
    (void)expected;
    /* Fase 1+: hash partial, rename, sync. */
    return -1; /* not implemented */
}
