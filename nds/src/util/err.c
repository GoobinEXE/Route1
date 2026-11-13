#include "route1/err.h"

const char *r1_err_str_pt(int err)
{
    switch (err) {
    case R1_OK:
        return "OK";
    case R1_E_PATH:
        return "Caminho inválido.";
    case R1_E_IO:
        return "Erro de leitura/escrita no cartão.";
    case R1_E_BUSY:
        return "Operação em curso.";
    case R1_E_NOSPC:
        return "Sem espaço no cartão.";
    case R1_E_CANCEL:
        return "Cancelado.";
    case R1_E_DENIED:
        return "Operação negada (ficheiro protegido).";
    case R1_E_NOMEM:
        return "Memória insuficiente.";
    case R1_E_NOTFOUND:
        return "Não encontrado.";
    case R1_E_NOT_EMPTY:
        return "Pasta não está vazia.";
    case R1_E_EXISTS:
        return "Já existe.";
    default:
        return "Erro desconhecido.";
    }
}
