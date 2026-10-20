"""Gestão das API keys do próprio usuário logado. A chave age com o perfil do dono.
A chave completa só é devolvida na criação; depois, só o prefixo fica visível."""
from fastapi import APIRouter, Depends, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import usuario_atual
from ..models import Usuario
from ..schemas import ApiKeyCriarIn
from ..services.chaves import criar_chave, listar_chaves, revogar_chave

router = APIRouter(prefix="/minhas-chaves", tags=["api keys"])


@router.get("")
def listar(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    return jsonable_encoder(listar_chaves(db, usuario.id))


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: ApiKeyCriarIn, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    """Cria a chave e devolve o valor completo UMA ÚNICA VEZ (campo "chave"). Guarde-o com segurança."""
    return jsonable_encoder(criar_chave(db, usuario.id, dados.nome, dados.expira_em))


@router.delete("/{chave_id}", status_code=status.HTTP_204_NO_CONTENT)
def revogar(chave_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    revogar_chave(db, usuario.id, chave_id)
