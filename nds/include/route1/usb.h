#ifndef ROUTE1_USB_H
#define ROUTE1_USB_H

#include <stdbool.h>

typedef enum {
    R1_USB_IDLE = 0,
    R1_USB_MSC_BUSY,
    R1_USB_SESSION
} r1_usb_state_t;

r1_usb_state_t r1_usb_state(void);
bool r1_usb_enter_msc_busy(void);
void r1_usb_leave(void);

/* R1USB bulk — Fase 3 (stubs). */
int r1_usb_poll(void);

#endif
