#ifndef ROUTE1_INPUT_H
#define ROUTE1_INPUT_H

enum {
    R1_KEY_UP = 1u << 0,
    R1_KEY_DOWN = 1u << 1,
    R1_KEY_LEFT = 1u << 2,
    R1_KEY_RIGHT = 1u << 3,
    R1_KEY_A = 1u << 4,
    R1_KEY_B = 1u << 5,
    R1_KEY_X = 1u << 6,
    R1_KEY_Y = 1u << 7,
    R1_KEY_L = 1u << 8,
    R1_KEY_R = 1u << 9,
    R1_KEY_START = 1u << 10,
    R1_KEY_SELECT = 1u << 11
};

void r1_input_init(void);
/* Teclas premidas neste frame (edge). */
unsigned r1_input_keys_down(void);
void r1_input_wait_frame(void);

#endif
