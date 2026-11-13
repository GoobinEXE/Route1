#ifdef R1_HAVE_LIBNDS

#include "route1/input.h"

#include <nds.h>

void r1_input_init(void)
{
}

void r1_input_wait_frame(void)
{
    swiWaitForVBlank();
    scanKeys();
}

unsigned r1_input_keys_down(void)
{
    unsigned k = keysDown();
    unsigned out = 0;

    if (k & KEY_UP)
        out |= R1_KEY_UP;
    if (k & KEY_DOWN)
        out |= R1_KEY_DOWN;
    if (k & KEY_LEFT)
        out |= R1_KEY_LEFT;
    if (k & KEY_RIGHT)
        out |= R1_KEY_RIGHT;
    if (k & KEY_A)
        out |= R1_KEY_A;
    if (k & KEY_B)
        out |= R1_KEY_B;
    if (k & KEY_X)
        out |= R1_KEY_X;
    if (k & KEY_Y)
        out |= R1_KEY_Y;
    if (k & KEY_L)
        out |= R1_KEY_L;
    if (k & KEY_R)
        out |= R1_KEY_R;
    if (k & KEY_START)
        out |= R1_KEY_START;
    if (k & KEY_SELECT)
        out |= R1_KEY_SELECT;
    return out;
}

#endif /* R1_HAVE_LIBNDS */
