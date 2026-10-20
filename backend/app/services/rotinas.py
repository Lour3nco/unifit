"""Tarefas periódicas do backend, fora das requisições: renovação das matrículas e mensalidades em atraso.
Roda ao subir a API e depois a cada INTERVALO_SEG. Assim nenhuma tela (GET) precisa escrever no banco."""
import asyncio
import logging
import os

from ..database import SessionLocal
from .academia import atualizar_atrasados, renovar_matriculas

log = logging.getLogger("unifit")
INTERVALO_SEG = int(os.getenv("ROTINAS_INTERVALO_SEG", str(15 * 60)))


def executar() -> None:
    with SessionLocal() as db:
        renovadas = renovar_matriculas(db)  # antes dos atrasados: a nova mensalidade vence hoje, não atrasa
        atualizar_atrasados(db)
    if renovadas:
        log.info("rotinas: %d matrícula(s) renovada(s)", renovadas)


async def ciclo() -> None:
    while True:
        try:
            await asyncio.to_thread(executar)
        except Exception:  # banco fora do ar etc.: tenta de novo no próximo ciclo
            log.exception("rotinas: falha ao renovar matrículas/atualizar atrasados")
        await asyncio.sleep(INTERVALO_SEG)
