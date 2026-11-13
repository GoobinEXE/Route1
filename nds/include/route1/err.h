#ifndef ROUTE1_ERR_H
#define ROUTE1_ERR_H

/* Códigos locais Fase 1 (alinhados em espírito aos E_* do protocolo). */
enum {
    R1_OK = 0,
    R1_E_PROTO = 1,
    R1_E_PATH = 2,
    R1_E_IO = 3,
    R1_E_HASH = 4,
    R1_E_BUSY = 5,
    R1_E_NOSPC = 6,
    R1_E_CANCEL = 7,
    R1_E_DENIED = 9,
    R1_E_NOMEM = 10,
    R1_E_NOTFOUND = 11,
    R1_E_NOT_EMPTY = 12,
    R1_E_EXISTS = 13
};

const char *r1_err_str_pt(int err);

#endif
