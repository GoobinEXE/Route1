#ifndef ROUTE1_INTEGRITY_H
#define ROUTE1_INTEGRITY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define R1_PARTIAL_SUFFIX ".r1partial"
#define R1_SHA256_LEN 32

typedef struct {
    uint8_t digest[R1_SHA256_LEN];
} r1_sha256_t;

/* Contratos — implementação na Fase 1+. */
bool r1_integrity_partial_path(char *out, size_t out_sz, const char *final_path);
int r1_integrity_promote(const char *partial_path, const char *final_path,
                         const r1_sha256_t *expected);

#endif
