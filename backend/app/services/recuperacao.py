"""'Esqueci a senha': gera o link de troca (uso único, curta duração) e troca a senha pelo token.

O token vai só no link; o banco guarda o SHA-256 dele (tabela senha_tokens, migração 009).
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from ..config import FRONTEND_URL
from ..database import SessionLocal
from ..models import Usuario
from ..reflexao import tabela
from ..security import hash_senha
from .notificacoes import enviar_email, enviar_sms, telefone_e164

log = logging.getLogger("unifit")
VALIDADE = timedelta(minutes=30)


def _tokens():
    tok = tabela("senha_tokens")
    if tok is None:  # sem isso o erro do SQLAlchemy ("expected, got None") não diz o que fazer
        raise RuntimeError("tabela senha_tokens não existe: rode banco/009_recuperacao_senha.sql e reinicie o backend")
    return tok


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def usuarios_por_email(db: Session, email: str) -> list[Usuario]:
    u = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email.strip().lower(), Usuario.ativo.is_(True)))
    return [u] if u else []


def usuarios_por_telefone(db: Session, telefone: str) -> list[tuple[Usuario, str]]:
    """Contas ativas cujo aluno tem esse telefone (só alunos têm telefone cadastrado). Compara pelo número
    normalizado, então "(11) 98888-7777" e "11988887777" batem. Devolve (usuario, telefone do cadastro)."""
    alvo = telefone_e164(telefone)
    if alvo is None:
        return []
    alu = tabela("alunos")
    linhas = db.execute(select(alu.c.usuario_id, alu.c.telefone).where(
        alu.c.usuario_id.is_not(None), alu.c.telefone.is_not(None))).all()
    ids = {l.usuario_id: l.telefone for l in linhas if telefone_e164(l.telefone) == alvo}
    if not ids:
        return []
    usuarios = db.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True))).all()
    return [(u, ids[u.id]) for u in usuarios]


def gerar_link(db: Session, usuario: Usuario, canal: str) -> str:
    """Novo link de troca. Pedir outro invalida os anteriores ainda não usados."""
    tok = _tokens()
    agora = datetime.now(timezone.utc)
    db.execute(update(tok).where(tok.c.usuario_id == usuario.id, tok.c.usado_em.is_(None)).values(usado_em=agora))
    token = secrets.token_urlsafe(32)
    db.execute(insert(tok).values(usuario_id=usuario.id, token_hash=_hash(token), canal=canal,
                                  expira_em=agora + VALIDADE))
    db.commit()
    return f"{FRONTEND_URL.rstrip('/')}/redefinir-senha?token={token}"


def enviar_link(email: str | None = None, telefone: str | None = None) -> None:
    """Roda em segundo plano, depois da resposta (sessão própria do banco): procura a conta, gera o link e
    envia. Conta inexistente simplesmente não recebe nada."""
    try:
        with SessionLocal() as db:
            if email:
                for u in usuarios_por_email(db, email):
                    link = gerar_link(db, u, "email")
                    enviar_email(u.email, "UniFit: troca de senha",
                                 f"Olá, {u.nome.split()[0]}!\n\nPara criar uma nova senha, acesse:\n{link}\n\n"
                                 "O link vale por 30 minutos e só pode ser usado uma vez. "
                                 "Se você não pediu a troca, ignore este e-mail: sua senha continua a mesma.")
            elif telefone:
                for u, tel in usuarios_por_telefone(db, telefone):
                    link = gerar_link(db, u, "sms")
                    enviar_sms(tel, f"UniFit: para trocar sua senha acesse {link} (vale 30 min). Se nao pediu, ignore.")
    except Exception:  # banco fora do ar etc.: não há a quem devolver o erro, fica no log
        log.exception("falha ao gerar o link de troca de senha")


def redefinir(db: Session, token: str, nova_senha: str) -> Usuario:
    tok = _tokens()
    agora = datetime.now(timezone.utc)
    # marca como usado no mesmo UPDATE que valida: dois cliques no link não trocam a senha duas vezes
    linha = db.execute(update(tok).where(tok.c.token_hash == _hash(token), tok.c.usado_em.is_(None),
                                         tok.c.expira_em > agora)
                       .values(usado_em=agora).returning(tok.c.usuario_id)).first()
    if not linha:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Link inválido ou expirado. Peça um novo em “Esqueci a senha”.")
    usuario = db.get(Usuario, linha.usuario_id)
    if not usuario or not usuario.ativo:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Link inválido ou expirado. Peça um novo em “Esqueci a senha”.")
    usuario.senha_hash = hash_senha(nova_senha)
    db.execute(update(tok).where(tok.c.usuario_id == usuario.id, tok.c.usado_em.is_(None)).values(usado_em=agora))
    db.commit()
    return usuario
