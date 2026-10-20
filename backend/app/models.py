from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from .database import DB_SCHEMA, Base
from .perfis import valores_enum

PerfilUsuario = ENUM(
    *valores_enum(),
    name="perfil_usuario",
    schema=DB_SCHEMA,
    create_type=False,  # o tipo já existe no banco
)


class Usuario(Base):
    """Tabela "unifit".usuarios, igual ao print do banco."""
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)  # bigserial
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[str] = mapped_column(PerfilUsuario)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
