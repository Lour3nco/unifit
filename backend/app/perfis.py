"""Perfis de usuário. O banco tem o enum "unifit".perfil_usuario; aqui lemos os valores reais
e traduzimos para os nomes usados na API e no frontend (administrador, recepcao, instrutor, aluno)."""
import unicodedata
from functools import lru_cache

from sqlalchemy import text

from .database import DB_SCHEMA, engine

CANONICOS = ("administrador", "recepcao", "instrutor", "aluno")
_PREFIXOS = {"admi": "administrador", "rece": "recepcao", "inst": "instrutor", "alun": "aluno"}


def normalizar_perfil(valor) -> str:
    s = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode().lower().strip()
    return _PREFIXOS.get(s[:4], s)


@lru_cache(maxsize=1)
def valores_enum() -> tuple:
    """Valores reais do enum perfil_usuario no banco (cai nos padrões se não conseguir ler)."""
    try:
        with engine.connect() as conn:
            linhas = conn.execute(text(
                "select e.enumlabel from pg_enum e "
                "join pg_type t on t.oid = e.enumtypid "
                "join pg_namespace n on n.oid = t.typnamespace "
                "where t.typname = 'perfil_usuario' and n.nspname = :s order by e.enumsortorder"
            ), {"s": DB_SCHEMA}).scalars().all()
        if linhas:
            return tuple(linhas)
    except Exception as erro:  # banco inacessível na importação
        print(f"[perfis] não consegui ler o enum do banco ({erro.__class__.__name__}); usando padrão")
    return CANONICOS


def perfil_para_banco(canonico: str) -> str:
    for valor in valores_enum():
        if normalizar_perfil(valor) == canonico:
            return valor
    raise ValueError(f"O perfil '{canonico}' não existe no enum perfil_usuario: {valores_enum()}")
