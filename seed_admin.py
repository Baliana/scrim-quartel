"""
Cria o primeiro usuário administrador do sistema.

Necessário porque a rota POST /auth/registrar só pode ser chamada por um admin
já autenticado — então é preciso semear o primeiro admin diretamente no banco.

Uso:
    python seed_admin.py
"""
from getpass import getpass

from app.database import SessionLocal, engine, Base
from app.models import Usuario, TipoUsuarioEnum
from app.auth import gerar_hash_senha


def main():
    Base.metadata.create_all(bind=engine)  # garante que as tabelas existem

    db = SessionLocal()
    try:
        nome = input("Nome do admin: ").strip()
        email = input("E-mail do admin: ").strip()
        senha = getpass("Senha (mín. 6 caracteres): ").strip()

        if db.query(Usuario).filter(Usuario.email == email).first():
            print(f"Já existe um usuário com o e-mail {email}.")
            return

        admin = Usuario(
            nome=nome,
            email=email,
            senha_hash=gerar_hash_senha(senha),
            tipo=TipoUsuarioEnum.admin,
            ativo=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin '{nome}' criado com sucesso (id={admin.id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
