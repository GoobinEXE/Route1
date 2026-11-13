#include "route1/usb.h"

static r1_usb_state_t g_state = R1_USB_IDLE;

r1_usb_state_t r1_usb_state(void)
{
    return g_state;
}

bool r1_usb_enter_msc_busy(void)
{
    if (g_state != R1_USB_IDLE)
        return false;
    g_state = R1_USB_MSC_BUSY;
    return true;
}

void r1_usb_leave(void)
{
    g_state = R1_USB_IDLE;
}

int r1_usb_poll(void)
{
    /* Fase 3: processar frames R1USB. */
    return 0;
}
