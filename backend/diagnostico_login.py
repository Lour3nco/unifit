import getpass

from sqlalchemy import func, select  # pyright: ignore[reportMissingImports]

from app.database import SessionLocal
from app.models import Usuario
from app.security import hash_senha, verificar_senha

email = input("E-mail: ").strip().lower()

with SessionLocal() as db:
    todos = db.scalars(select(Usuario)).all()
    print(f"\n{len(todos)} usuário(s) no banco:")
    for u in todos:
        print(f" - {u.email} | perfil={u.perfil} | ativo={u.ativo} | hash={u.senha_hash[:7]}...")

    u = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
    if not u:
        print("\n-> Este e-mail NÃO existe no banco. Rode criar_admin.py com ele.")
        raise SystemExit

    senha = getpass.getpass("Senha: ")
    print("\nativo:", u.ativo)
    print("senha confere:", verificar_senha(senha, u.senha_hash))

    if input("\nRedefinir a senha deste usuário? (s/n) ").strip().lower() == "s":
        nova = getpass.getpass("Nova senha (mín. 8 caracteres): ")
        if len(nova) < 8:
            raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
        u.senha_hash = hash_senha(nova)
        u.ativo = True
        db.commit()
        print("Senha redefinida. Tente entrar de novo.")