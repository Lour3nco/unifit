"""API keys: geração, validação e gestão. A chave pertence a um usuário e age com o perfil dele.
Guardamos só o SHA-256 da chave; a chave completa só existe no momento da criação."""
import hashlib
import secrets
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from ..models import Usuario
from ..reflexao import tabela
from .academia import utc

PREFIXO_VISIVEL = 12  # quantos caracteres do início guardamos para exibir na lista
INTERVALO_ULTIMO_USO = timedelta(minutes=5)


def _hash(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


def gerar_chave() -> tuple[str, str, str]:
    """Devolve (chave_completa, prefixo_visivel, hash). A chave completa não é guardada."""
    chave = f"unifit_{secrets.token_urlsafe(32)}"
    return chave, chave[:PREFIXO_VISIVEL], _hash(chave)


def _linha(m) -> dict:
    return {"id": m["id"], "nome": m["nome"], "prefixo": m["prefixo"], "ativo": m["ativo"],
            "criado_em": utc(m["criado_em"]), "ultimo_uso_em": utc(m["ultimo_uso_em"]),
            "expira_em": utc(m["expira_em"])}


def listar_chaves(db: Session, usuario_id: int) -> list:
    ak = tabela("api_keys")
    linhas = db.execute(select(ak).where(ak.c.usuario_id == usuario_id).order_by(ak.c.criado_em.desc())).all()
    return [_linha(l._mapping) for l in linhas]


def criar_chave(db: Session, usuario_id: int, nome: str, expira_em: date | None = None) -> dict:
    ak = tabela("api_keys")
    chave, prefixo, token_hash = gerar_chave()
    exp = None
    if expira_em is not None:
        exp = datetime.combine(expira_em, time.max, tzinfo=timezone.utc)
    novo_id = db.execute(insert(ak).values(
        usuario_id=usuario_id, nome=nome.strip(), prefixo=prefixo, token_hash=token_hash,
        ativo=True, expira_em=exp).returning(ak.c.id)).scalar_one()
    db.commit()
    criada = db.execute(select(ak).where(ak.c.id == novo_id)).first()._mapping
    # a chave completa só é devolvida aqui, nunca mais
    return {**_linha(criada), "chave": chave}


def revogar_chave(db: Session, usuario_id: int, chave_id: int) -> None:
    ak = tabela("api_keys")
    n = db.execute(delete(ak).where(ak.c.id == chave_id, ak.c.usuario_id == usuario_id)).rowcount
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chave não encontrada.")
    db.commit()


def usuario_por_chave(db: Session, chave: str) -> Usuario | None:
    """Resolve o usuário dono de uma API key válida (ativa e não expirada). None se inválida."""
    ak = tabela("api_keys")
    if ak is None or not chave:
        return None
    linha = db.execute(select(ak).where(ak.c.token_hash == _hash(chave), ak.c.ativo.is_(True))).first()
    if not linha:
        return None
    m = linha._mapping
    if m["expira_em"] is not None and utc(m["expira_em"]) < datetime.now(timezone.utc):
        return None
    usuario = db.get(Usuario, m["usuario_id"])
    if not usuario or not usuario.ativo:
        return None
    agora = datetime.now(timezone.utc)
    ultimo = utc(m["ultimo_uso_em"])
    if ultimo is None or agora - ultimo > INTERVALO_ULTIMO_USO:  # grava no máximo a cada 5 min, não a cada chamada
        try:  # best-effort: não derruba a requisição se falhar
            db.execute(update(ak).where(ak.c.id == m["id"]).values(ultimo_uso_em=agora))
            db.commit()
        except Exception:
            db.rollback()
    return usuario
