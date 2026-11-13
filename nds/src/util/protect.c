#include "route1/protect.h"

#include "route1/path.h"

#include <ctype.h>
#include <string.h>

static void lower_copy(char *dst, size_t dst_sz, const char *src)
{
    size_t i;
    for (i = 0; src[i] && i + 1 < dst_sz; ++i)
        dst[i] = (char)tolower((unsigned char)src[i]);
    dst[i] = '\0';
}

bool r1_protect_is_critical(const char *rel_path)
{
    char norm[R1_PATH_MAX];
    char low[R1_PATH_MAX];
    const char *base;

    if (!r1_path_normalize(norm, sizeof norm, rel_path))
        return true; /* path inválido → tratar como protegido */

    if (norm[0] == '.' && norm[1] == '\0')
        return false;

    lower_copy(low, sizeof low, norm);
    base = r1_path_basename(low);

    if (strcmp(base, "_picoboot.nds") == 0)
        return true;
    if (strcmp(low, "_pico") == 0)
        return true;
    if (strncmp(low, "_pico/", 6) == 0)
        return true;

    return false;
}
