import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario
from .perfis import normalizar_perfil
from .security import ler_token
from .services.chaves import usuario_por_chave

bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def usuario_atual(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    chave: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> Usuario:
    # 1) API key (header X-API-Key): acesso programático, age com o perfil do dono da chave
    if chave:
        usuario = usuario_por_chave(db, chave)
        if usuario is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida, expirada ou revogada.")
        return usuario
    # 2) Token JWT (login pelo app)
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    try:
        dados = ler_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente.")
    usuario = db.get(Usuario, int(dados["sub"]))
    if not usuario or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inválido.")
    return usuario


def exige_perfis(*perfis: str):  # RF02
    def checar(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if normalizar_perfil(usuario.perfil) not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu perfil não tem acesso a esta função.")
        return usuario

    return checar
