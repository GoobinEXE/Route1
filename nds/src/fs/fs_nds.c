#ifdef R1_HAVE_LIBNDS

#include "route1/fs.h"

#include "route1/err.h"
#include "route1/path.h"
#include "route1/protect.h"

#include <nds.h>
#include <fat.h>

#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static char g_root[R1_PATH_MAX];
static int g_ready;

static int cmp_entries(const void *a, const void *b)
{
    const r1_fs_entry_t *ea = a;
    const r1_fs_entry_t *eb = b;
    if (ea->is_dir != eb->is_dir)
        return eb->is_dir - ea->is_dir;
    return strcasecmp(ea->name, eb->name);
}

int r1_fs_init(const char *root_abs)
{
    (void)root_abs;

    if (!fatInitDefault())
        return -R1_E_IO;

    /* Raiz do volume montado pelo libfat. */
    strncpy(g_root, "/", sizeof g_root - 1);
    g_root[sizeof g_root - 1] = '\0';
    g_ready = 1;
    return R1_OK;
}

void r1_fs_shutdown(void)
{
    g_ready = 0;
    g_root[0] = '\0';
}

const char *r1_fs_root(void)
{
    return g_ready ? g_root : "";
}

static int abs_for_rel(char *abs, size_t abs_sz, const char *rel)
{
    char norm[R1_PATH_MAX];

    if (!g_ready)
        return -R1_E_IO;
    if (!r1_path_normalize(norm, sizeof norm, rel ? rel : "."))
        return -R1_E_PATH;

    if (norm[0] == '.' && norm[1] == '\0') {
        if (abs_sz < 2)
            return -R1_E_PATH;
        abs[0] = '/';
        abs[1] = '\0';
        return R1_OK;
    }

    if (strlen(norm) + 2 > abs_sz)
        return -R1_E_PATH;
    abs[0] = '/';
    memcpy(abs + 1, norm, strlen(norm) + 1);
    return R1_OK;
}

int r1_fs_exists(const char *rel_path, int *is_dir_out)
{
    char abs[R1_PATH_MAX];
    struct stat st;
    int rc = abs_for_rel(abs, sizeof abs, rel_path);
    if (rc != R1_OK)
        return rc;
    if (stat(abs, &st) != 0)
        return -R1_E_NOTFOUND;
    if (is_dir_out)
        *is_dir_out = S_ISDIR(st.st_mode) ? 1 : 0;
    return R1_OK;
}

int r1_fs_list(const char *rel_dir, r1_fs_entry_t *out, int max_entries)
{
    char abs[R1_PATH_MAX];
    DIR *dir;
    struct dirent *de;
    int n = 0;
    int rc;

    if (!out || max_entries <= 0)
        return -R1_E_PATH;
    if (max_entries > R1_FS_MAX_ENTRIES)
        max_entries = R1_FS_MAX_ENTRIES;

    rc = abs_for_rel(abs, sizeof abs, rel_dir);
    if (rc != R1_OK)
        return rc;

    dir = opendir(abs);
    if (!dir)
        return -R1_E_IO;

    while ((de = readdir(dir)) != NULL) {
        char child_abs[R1_PATH_MAX];
        struct stat st;

        if (strcmp(de->d_name, ".") == 0 || strcmp(de->d_name, "..") == 0)
            continue;
        if (n >= max_entries)
            break;

        if (strlen(abs) + 1 + strlen(de->d_name) + 1 > sizeof child_abs) {
            closedir(dir);
            return -R1_E_PATH;
        }
        if (strcmp(abs, "/") == 0)
            snprintf(child_abs, sizeof child_abs, "/%s", de->d_name);
        else
            snprintf(child_abs, sizeof child_abs, "%s/%s", abs, de->d_name);

        if (stat(child_abs, &st) != 0)
            continue;

        memset(&out[n], 0, sizeof out[n]);
        strncpy(out[n].name, de->d_name, R1_FS_NAME_MAX - 1);
        out[n].is_dir = S_ISDIR(st.st_mode) ? 1 : 0;
        out[n].size = S_ISREG(st.st_mode) ? (unsigned long long)st.st_size : 0;
        n++;
    }
    closedir(dir);

    if (n > 1)
        qsort(out, (size_t)n, sizeof out[0], cmp_entries);
    return n;
}

static int unlink_tree(const char *abs)
{
    struct stat st;
    DIR *dir;
    struct dirent *de;

    if (stat(abs, &st) != 0)
        return -R1_E_NOTFOUND;

    if (!S_ISDIR(st.st_mode)) {
        if (unlink(abs) != 0)
            return -R1_E_IO;
        return R1_OK;
    }

    dir = opendir(abs);
    if (!dir)
        return -R1_E_IO;

    while ((de = readdir(dir)) != NULL) {
        char child[R1_PATH_MAX];
        int rc;

        if (strcmp(de->d_name, ".") == 0 || strcmp(de->d_name, "..") == 0)
            continue;
        if (strlen(abs) + 1 + strlen(de->d_name) + 1 > sizeof child) {
            closedir(dir);
            return -R1_E_PATH;
        }
        if (strcmp(abs, "/") == 0)
            snprintf(child, sizeof child, "/%s", de->d_name);
        else
            snprintf(child, sizeof child, "%s/%s", abs, de->d_name);
        rc = unlink_tree(child);
        if (rc != R1_OK) {
            closedir(dir);
            return rc;
        }
    }
    closedir(dir);

    if (rmdir(abs) != 0)
        return -R1_E_IO;
    return R1_OK;
}

int r1_fs_delete(const char *rel_path, int critical_ok)
{
    char norm[R1_PATH_MAX];
    char abs[R1_PATH_MAX];
    int rc;

    if (!r1_path_normalize(norm, sizeof norm, rel_path))
        return -R1_E_PATH;
    if (norm[0] == '.' && norm[1] == '\0')
        return -R1_E_DENIED;
    if (r1_protect_is_critical(norm) && !critical_ok)
        return -R1_E_DENIED;

    rc = abs_for_rel(abs, sizeof abs, norm);
    if (rc != R1_OK)
        return rc;
    return unlink_tree(abs);
}

unsigned long long r1_fs_free_bytes(void)
{
    /* libfat não expõe API portátil estável em todas as versões. */
    return 0;
}

#endif /* R1_HAVE_LIBNDS */
