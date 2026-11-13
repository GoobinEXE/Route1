#ifndef ROUTE1_PROTECT_H
#define ROUTE1_PROTECT_H

#include <stdbool.h>

/* Markers DSPico / Pico Launcher — exigem confirmação forte antes de apagar. */
bool r1_protect_is_critical(const char *rel_path);

#endif
