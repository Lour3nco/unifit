"""Limite de tentativas de login (contra força bruta), em memória.

Conta só as tentativas que FALHARAM, por e-mail e por IP, numa janela deslizante. Vale para um processo do
uvicorn; com vários processos/servidores, cada um conta separado (aí o certo é guardar no Redis/banco).
"""
import os
import time
from collections import defaultdict, deque
from threading import Lock

JANELA_SEG = 15 * 60
MAX_POR_EMAIL = int(os.getenv("LOGIN_MAX_POR_EMAIL", "5"))  # protege uma conta específica
MAX_POR_IP = int(os.getenv("LOGIN_MAX_POR_IP", "20"))       # protege contra quem testa várias contas

_falhas: dict[str, deque] = defaultdict(deque)
_trava = Lock()


def _limpar(chave: str, agora: float) -> deque:
    fila = _falhas[chave]
    while fila and fila[0] <= agora - JANELA_SEG:
        fila.popleft()
    if not fila:
        _falhas.pop(chave, None)
    return fila


def segundos_bloqueado(email: str, ip: str) -> int:
    """0 se pode tentar; senão, quantos segundos faltam para liberar."""
    agora = time.monotonic()
    espera = 0.0
    with _trava:
        for chave, maximo in ((f"email:{email}", MAX_POR_EMAIL), (f"ip:{ip}", MAX_POR_IP)):
            fila = _limpar(chave, agora)
            if len(fila) >= maximo:
                espera = max(espera, fila[0] + JANELA_SEG - agora)
    return int(espera) + (1 if espera else 0)


def registrar_falha(email: str, ip: str) -> None:
    agora = time.monotonic()
    with _trava:
        _falhas[f"email:{email}"].append(agora)
        _falhas[f"ip:{ip}"].append(agora)


def registrar_sucesso(email: str) -> None:
    """Login certo zera as falhas daquele e-mail (as do IP continuam valendo)."""
    with _trava:
        _falhas.pop(f"email:{email}", None)
