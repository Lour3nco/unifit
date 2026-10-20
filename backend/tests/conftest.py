"""Testes de integração com um Postgres de verdade, num schema temporário e isolado.

O schema "unifit_teste_<aleatório>" é criado a partir de banco/schema.sql + migrações novas e apagado no fim.
O schema real ("unifit") nunca é tocado. Por padrão usa a conexão do .env; para outro servidor, defina
TEST_DB_HOST, TEST_DB_PORT, TEST_DB_NAME, TEST_DB_USER e TEST_DB_PASSWORD.

Rodar (na pasta backend):  python -m pytest
"""
import os
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

SCHEMA = f"unifit_teste_{uuid.uuid4().hex[:8]}"
BANCO = Path(__file__).resolve().parent.parent / "banco"
MIGRACOES_DEPOIS_DO_SCHEMA = ("005_pagamento_informado.sql", "006_indices_matricula_postura.sql")

# precisa acontecer ANTES de importar o app: database.py e perfis.py leem isso na importação
os.environ["DB_SCHEMA"] = SCHEMA
for nome in ("HOST", "PORT", "NAME", "USER", "PASSWORD"):
    if os.getenv(f"TEST_DB_{nome}"):
        os.environ[f"DB_{nome}"] = os.environ[f"TEST_DB_{nome}"]
os.environ["BENCHMARK_ATIVO"] = "false"

from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402  (só o engine: perfis/models ainda não leram o enum)


def _criar_schema():
    sql = (BANCO / "schema.sql").read_text(encoding="utf-8")
    sql += "\n".join((BANCO / m).read_text(encoding="utf-8") for m in MIGRACOES_DEPOIS_DO_SCHEMA)
    with engine.begin() as conn:
        conn.exec_driver_sql(sql.replace('"unifit"', f'"{SCHEMA}"'))


_criar_schema()

from fastapi.testclient import TestClient  # noqa: E402

from app import limite  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.reflexao import tabela  # noqa: E402
from app.security import criar_token  # noqa: E402
from app.services.usuarios import criar_usuario  # noqa: E402

SENHA = "senha-segura-1"


def pytest_sessionfinish(session, exitstatus):
    with engine.begin() as conn:
        conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')


@pytest.fixture(autouse=True)
def banco_limpo():
    """Cada teste começa com as tabelas vazias e sem bloqueios de login."""
    with engine.begin() as conn:
        tabelas = conn.execute(text("select tablename from pg_tables where schemaname = :s"), {"s": SCHEMA}).scalars()
        conn.exec_driver_sql("TRUNCATE " + ", ".join(f'"{SCHEMA}"."{t}"' for t in tabelas) + " RESTART IDENTITY CASCADE")
    limite._falhas.clear()
    yield


@pytest.fixture
def db():
    with SessionLocal() as sessao:
        yield sessao


@pytest.fixture
def cliente():
    return TestClient(app)  # sem "with": não sobe a rotina de fundo (renovação), que é testada à parte


def gerar_cpf(n: int) -> str:
    """CPF válido e único por número (o banco recusa CPF repetido)."""
    base = f"{n:09d}"
    for tamanho in (9, 10):
        soma = sum(int(base[i]) * (tamanho + 1 - i) for i in range(tamanho))
        base += str(soma * 10 % 11 % 10)
    return base


@pytest.fixture
def plano_id(db):
    """Plano Mensal ativo (R$ 120, 30 dias)."""
    p = tabela("planos")
    pid = db.execute(p.insert().values(nome="Mensal", valor=120, duracao_dias=30, ativo=True).returning(p.c.id)).scalar_one()
    db.commit()
    return pid


@pytest.fixture
def conta(db):
    """conta(perfil) -> (usuario, cabeçalho Authorization). Contas de aluno já saem com a ficha."""
    contador = iter(range(1, 10_000))

    def criar(perfil: str, ativo: bool = True, email: str | None = None):
        n = next(contador)
        u = criar_usuario(db, f"{perfil.title()} {n}", email or f"{perfil}{n}@teste.com", SENHA, perfil, ativo=ativo,
                          cpf=gerar_cpf(n) if perfil == "aluno" else None)
        return u, {"Authorization": f"Bearer {criar_token(u.id, perfil)}"}

    return criar


def aluno_id_de(db, usuario) -> int:
    alu = tabela("alunos")
    return db.execute(alu.select().where(alu.c.usuario_id == usuario.id)).first().id


def mudar_vencimento(db, aluno_id: int, dias_atras: int):
    """Move o início/fim da matrícula e o vencimento das mensalidades do aluno para o passado."""
    mat, pag = tabela("matriculas"), tabela("pagamentos")
    delta = timedelta(days=dias_atras)
    ids = [m.id for m in db.execute(mat.select().where(mat.c.aluno_id == aluno_id)).all()]
    db.execute(mat.update().where(mat.c.id.in_(ids)).values(data_inicio=mat.c.data_inicio - delta,
                                                             data_fim=mat.c.data_fim - delta))
    db.execute(pag.update().where(pag.c.matricula_id.in_(ids)).values(data_vencimento=pag.c.data_vencimento - delta))
    db.commit()
