from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import JWT_EXPIRE_MINUTES, JWT_SECRET

ALGORITHM = "HS256"


def _bytes(senha: str) -> bytes:
    return senha.encode()[:72]  # limite do bcrypt


def hash_senha(senha: str) -> str:  # RNF01
    return bcrypt.hashpw(_bytes(senha), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(_bytes(senha), hash_.encode())
    except ValueError:  # hash em formato inválido
        return False


HASH_FICTICIO = hash_senha("conta-inexistente")  # comparado no login quando o e-mail não existe


def criar_token(usuario_id: int, perfil: str) -> str:  # RNF02
    exp = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(usuario_id), "perfil": perfil, "exp": exp}, JWT_SECRET, algorithm=ALGORITHM)


def ler_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
