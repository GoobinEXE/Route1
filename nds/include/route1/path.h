#ifndef ROUTE1_PATH_H
#define ROUTE1_PATH_H

#include <stdbool.h>
#include <stddef.h>

#define R1_PATH_MAX 512

/* Path relativo seguro (permite "." = raiz lógica). Rejeita .., absolutos, NUL. */
bool r1_path_is_safe(const char *rel_path);

/* Normaliza para forma relativa sem "./" nem barras duplas. out pode ser in. */
bool r1_path_normalize(char *out, size_t out_sz, const char *rel_path);

/* Junta root absoluto do volume + rel seguro → abs. */
bool r1_path_join(char *out, size_t out_sz, const char *root, const char *rel);

/* Junta dois relativos seguros (ex. "Games" + "foo.nds"). */
bool r1_path_join_rel(char *out, size_t out_sz, const char *base, const char *name);

/* Pai de um relativo; raiz "." se não houver pai. */
bool r1_path_parent(char *out, size_t out_sz, const char *rel_path);

/* Nome final do componente (sem barras). */
const char *r1_path_basename(const char *rel_path);

#endif
