import getpass

from sqlalchemy import func, select  # pyright: ignore[reportMissingImports]

from app.database import SessionLocal
from app.models import Usuario
from app.perfis import perfil_para_banco
from app.security import hash_senha

email = input("E-mail do usuário: ").strip().lower()

with SessionLocal() as db:
    u = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
    if not u:
        raise SystemExit("Esse e-mail não existe no banco.")

    print(f"Encontrado: {u.nome} | perfil atual: {u.perfil} | ativo: {u.ativo}")
    nova = getpass.getpass("Nova senha (mín. 8 caracteres): ")
    if len(nova) < 8:
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")

    u.senha_hash = hash_senha(nova)
    u.ativo = True
    promover = input("Tornar este usuário administrador? (s/n) ").strip().lower() == "s"
    if promover:
        u.perfil = perfil_para_banco("administrador")
    db.commit()
    print("Pronto: senha redefinida e usuário ativo" + (", agora administrador." if promover else "."))