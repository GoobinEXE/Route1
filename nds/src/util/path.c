#include "route1/path.h"

#include <stdio.h>
#include <string.h>

static int is_sep(char c)
{
    return c == '/' || c == '\\';
}

bool r1_path_is_safe(const char *rel_path)
{
    const char *p;

    if (!rel_path)
        return false;

    /* "." = raiz lógica do volume. */
    if (rel_path[0] == '.' && rel_path[1] == '\0')
        return true;

    if (!rel_path[0])
        return false;

    if (is_sep(rel_path[0]))
        return false;

    for (p = rel_path; *p; ++p) {
        if (p[0] == '.' && p[1] == '.' &&
            (p == rel_path || is_sep(p[-1])) &&
            (p[2] == '\0' || is_sep(p[2])))
            return false;
    }

    if (strstr(rel_path, ":\\") || strstr(rel_path, ":/"))
        return false;

    return true;
}

bool r1_path_normalize(char *out, size_t out_sz, const char *rel_path)
{
    char tmp[R1_PATH_MAX];
    size_t i = 0, j = 0;

    if (!out || out_sz == 0 || !rel_path)
        return false;

    if (!rel_path[0] || (rel_path[0] == '.' && rel_path[1] == '\0')) {
        if (out_sz < 2)
            return false;
        out[0] = '.';
        out[1] = '\0';
        return true;
    }

    if (!r1_path_is_safe(rel_path))
        return false;

    /* Copiar para tmp com '/' e sem duplicados / "./" */
    while (rel_path[i] && j + 1 < sizeof tmp) {
        if (is_sep(rel_path[i])) {
            if (j == 0 || tmp[j - 1] != '/')
                tmp[j++] = '/';
            i++;
            continue;
        }
        if (rel_path[i] == '.' && (is_sep(rel_path[i + 1]) || rel_path[i + 1] == '\0') &&
            (i == 0 || is_sep(rel_path[i - 1]))) {
            i++;
            if (is_sep(rel_path[i]))
                i++;
            continue;
        }
        tmp[j++] = rel_path[i++];
    }
    tmp[j] = '\0';

    while (j > 1 && tmp[j - 1] == '/')
        tmp[--j] = '\0';

    if (j == 0) {
        if (out_sz < 2)
            return false;
        out[0] = '.';
        out[1] = '\0';
        return true;
    }

    if (j + 1 > out_sz)
        return false;
    memcpy(out, tmp, j + 1);
    return r1_path_is_safe(out);
}

bool r1_path_join(char *out, size_t out_sz, const char *root, const char *rel)
{
    char norm[R1_PATH_MAX];
    size_t n, m;

    if (!out || out_sz == 0 || !root)
        return false;
    if (!r1_path_normalize(norm, sizeof norm, rel))
        return false;

    if (norm[0] == '.' && norm[1] == '\0') {
        n = strlen(root);
        if (n + 1 > out_sz)
            return false;
        memcpy(out, root, n + 1);
        return true;
    }

    n = strlen(root);
    m = strlen(norm);
    if (n + 1 + m + 1 > out_sz)
        return false;

    memcpy(out, root, n);
    if (n > 0 && !is_sep(root[n - 1])) {
        out[n++] = '/';
        out[n] = '\0';
    } else {
        out[n] = '\0';
    }
    memcpy(out + n, norm, m + 1);
    return true;
}

bool r1_path_join_rel(char *out, size_t out_sz, const char *base, const char *name)
{
    char nb[R1_PATH_MAX];
    char combined[R1_PATH_MAX];

    if (!name || !name[0] || strchr(name, '/') || strchr(name, '\\'))
        return false;
    if (strcmp(name, ".") == 0 || strcmp(name, "..") == 0)
        return false;

    if (!r1_path_normalize(nb, sizeof nb, base ? base : "."))
        return false;

    if (nb[0] == '.' && nb[1] == '\0') {
        if (strlen(name) + 1 > out_sz)
            return false;
        memcpy(out, name, strlen(name) + 1);
        return r1_path_is_safe(out);
    }

    if (strlen(nb) + 1 + strlen(name) + 1 > sizeof combined)
        return false;
    snprintf(combined, sizeof combined, "%s/%s", nb, name);
    return r1_path_normalize(out, out_sz, combined);
}

bool r1_path_parent(char *out, size_t out_sz, const char *rel_path)
{
    char norm[R1_PATH_MAX];
    char *slash;

    if (!r1_path_normalize(norm, sizeof norm, rel_path))
        return false;

    if (norm[0] == '.' && norm[1] == '\0') {
        if (out_sz < 2)
            return false;
        out[0] = '.';
        out[1] = '\0';
        return true;
    }

    slash = strrchr(norm, '/');
    if (!slash) {
        if (out_sz < 2)
            return false;
        out[0] = '.';
        out[1] = '\0';
        return true;
    }

    *slash = '\0';
    if (!norm[0]) {
        if (out_sz < 2)
            return false;
        out[0] = '.';
        out[1] = '\0';
        return true;
    }
    if (strlen(norm) + 1 > out_sz)
        return false;
    memcpy(out, norm, strlen(norm) + 1);
    return true;
}

const char *r1_path_basename(const char *rel_path)
{
    const char *p;
    const char *last = rel_path;

    if (!rel_path || !rel_path[0])
        return "";
    for (p = rel_path; *p; ++p) {
        if (is_sep(*p) && p[1])
            last = p + 1;
    }
    return last;
}
