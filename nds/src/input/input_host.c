#ifndef R1_HAVE_LIBNDS

#include "route1/input.h"

#include <stdio.h>
#include <stdlib.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

static struct termios g_saved;
static int g_raw;

static void restore_tty(void)
{
    if (g_raw)
        tcsetattr(STDIN_FILENO, TCSANOW, &g_saved);
    g_raw = 0;
}

void r1_input_init(void)
{
    struct termios t;

    if (!isatty(STDIN_FILENO))
        return;
    if (tcgetattr(STDIN_FILENO, &g_saved) != 0)
        return;
    t = g_saved;
    t.c_lflag &= (tcflag_t) ~(ICANON | ECHO);
    t.c_cc[VMIN] = 0;
    t.c_cc[VTIME] = 0;
    if (tcsetattr(STDIN_FILENO, TCSANOW, &t) == 0) {
        g_raw = 1;
        atexit(restore_tty);
    }
}

void r1_input_wait_frame(void)
{
    usleep(16000);
}

static int read_byte(unsigned char *c)
{
    fd_set fds;
    struct timeval tv;

    FD_ZERO(&fds);
    FD_SET(STDIN_FILENO, &fds);
    tv.tv_sec = 0;
    tv.tv_usec = 0;
    if (select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv) <= 0)
        return 0;
    return read(STDIN_FILENO, c, 1) == 1;
}

unsigned r1_input_keys_down(void)
{
    unsigned keys = 0;
    unsigned char c;

    while (read_byte(&c)) {
        if (c == 0x1b) {
            unsigned char a, b;
            if (read_byte(&a) && a == '[' && read_byte(&b)) {
                if (b == 'A')
                    keys |= R1_KEY_UP;
                else if (b == 'B')
                    keys |= R1_KEY_DOWN;
                else if (b == 'C')
                    keys |= R1_KEY_RIGHT;
                else if (b == 'D')
                    keys |= R1_KEY_LEFT;
            } else {
                keys |= R1_KEY_B;
            }
            continue;
        }
        switch (c) {
        case 'w':
        case 'W':
            keys |= R1_KEY_UP;
            break;
        case 's':
        case 'S':
            keys |= R1_KEY_DOWN;
            break;
        case 'a':
        case 'A':
        case '\n':
        case '\r':
            keys |= R1_KEY_A;
            break;
        case 'b':
        case 'B':
        case 0x7f:
            keys |= R1_KEY_B;
            break;
        case 'x':
        case 'X':
            keys |= R1_KEY_X;
            break;
        case 'y':
        case 'Y':
            keys |= R1_KEY_Y;
            break;
        case 'l':
        case 'L':
            keys |= R1_KEY_L;
            break;
        case 'r':
        case 'R':
            keys |= R1_KEY_R;
            break;
        case 'q':
        case 'Q':
            keys |= R1_KEY_START;
            break;
        default:
            break;
        }
    }
    return keys;
}

#endif /* !R1_HAVE_LIBNDS */
