"""Vínculo entre a conta (usuarios) e o cadastro do aluno (alunos).

Regra de segurança: a ficha do aluno só é encontrada pelo usuario_id. Uma conta nova só é ligada a uma
ficha já existente quando e-mail E CPF batem (cadastro pelo app) ou quando quem cria a conta é o
administrador. Ligar só pelo e-mail deixaria qualquer pessoa ver os dados de outra.
"""
import logging

from fastapi import HTTPException, status  # type: ignore[import-not-found]
from sqlalchemy import func, insert, select, update  # type: ignore[import-not-found]
from sqlalchemy.orm import Session  # type: ignore[import-not-found]

from ..models import Usuario
from ..reflexao import coluna, tabela

log = logging.getLogger("unifit")
AUTOMATICAS = {"criado_em", "atualizado_em", "created_at", "updated_at"}


def aluno_do_usuario(db: Session, usuario: Usuario) -> dict | None:
    """Linha de "alunos" ligada à conta (pelo usuario_id)."""
    t = tabela("alunos")
    uid = coluna(t, "usuario_id")
    if uid is None:
        return None
    linha = db.execute(select(t).where(uid == usuario.id).limit(1)).first()
    return dict(linha._mapping) if linha else None


def ficha_para_cadastro(db: Session, email: str, cpf: str):
    """Antes de criar a conta pelo app: devolve o id da ficha a ligar (e-mail e CPF batem), None para criar
    uma ficha nova, ou recusa (409) quando há conflito que só a recepção pode resolver."""
    t = tabela("alunos")
    email = email.strip().lower()
    ficha = db.execute(select(t.c.id, t.c.email, t.c.usuario_id).where(t.c.cpf == cpf)).first()
    if ficha:
        if ficha.usuario_id is not None:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Este CPF já tem uma conta no app. Entre com o e-mail dela ou fale com a recepção.")
        if (ficha.email or "").strip().lower() != email:
            raise HTTPException(status.HTTP_409_CONFLICT, "Este CPF já está cadastrado na academia com outro e-mail. "
                                                          "Fale com a recepção para atualizar seu cadastro.")
        return ficha.id
    outra = db.execute(select(t.c.id).where(func.lower(t.c.email) == email, t.c.usuario_id.is_(None)).limit(1)).first()
    if outra:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um cadastro na academia com este e-mail e outro CPF "
                                                      "(ou sem CPF). Fale com a recepção para conferir seus dados.")
    return None


def ligar_ficha(db: Session, usuario: Usuario, ficha_id=None, cpf: str | None = None, por_email: bool = False) -> bool:
    """Liga a conta a uma ficha existente ou cria uma ficha nova em "alunos", sem commit (quem chama decide).
    ficha_id: ficha já validada (ficha_para_cadastro). por_email: só para contas criadas pelo administrador.
    Devolve False quando não há o que fazer (conta já ligada ou tabela incompatível); erros do banco sobem."""
    t = tabela("alunos")
    if t is None or "usuario_id" not in t.c or aluno_do_usuario(db, usuario):
        return False
    if ficha_id is None and por_email:
        linha = db.execute(select(t.c.id).where(func.lower(t.c.email) == usuario.email.lower(),
                                                t.c.usuario_id.is_(None)).limit(1)).first()
        ficha_id = linha.id if linha else None
    if ficha_id is not None:
        db.execute(update(t).where(t.c.id == ficha_id).values(usuario_id=usuario.id))
        return True
    candidatos = {"nome": usuario.nome, "email": usuario.email, "usuario_id": usuario.id, "cpf": cpf, "ativo": True}
    valores = {k: v for k, v in candidatos.items() if k in t.c and v is not None}
    for c in t.c:
        if c.name in AUTOMATICAS and not c.nullable and c.server_default is None:
            valores[c.name] = func.now()
    obrigatorias = [c.name for c in t.c if not c.nullable and not c.primary_key
                    and c.server_default is None and c.identity is None and c.default is None]
    if any(n not in valores for n in obrigatorias):
        return False  # a tabela exige campos que a conta não tem
    db.execute(insert(t).values(**valores))
    return True


def vincular_aluno(db: Session, usuario: Usuario, ficha_id=None, cpf: str | None = None, por_email: bool = False) -> bool:
    """Versão tolerante de ligar_ficha para contas já gravadas (criadas ou promovidas pelo administrador):
    faz o commit e, em qualquer problema, só devolve False. O aluno ainda pode criar a ficha em "Meus dados"."""
    try:
        if not ligar_ficha(db, usuario, ficha_id, cpf, por_email):
            return False
        db.commit()
        return True
    except Exception as erro:
        db.rollback()
        log.warning("vincular_aluno: %s", erro)
        return False
