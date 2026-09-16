from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario
from app.schemas import LoginRequest, TokenResponse, UsuarioCreate, UsuarioOut
from app.auth import (
    verificar_senha, gerar_hash_senha, criar_token_acesso,
    get_current_user, exigir_admin,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post("/login", response_model=TokenResponse)
def login(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()

    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )

    if not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo")

    token = criar_token_acesso({"sub": str(usuario.id)})
    return TokenResponse(access_token=token, usuario=UsuarioOut.model_validate(usuario))


@router.post("/registrar", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(
    dados: UsuarioCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),  # apenas admin pode criar novos usuários (clientes ou admins)
):
    existente = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if existente:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=gerar_hash_senha(dados.senha),
        telefone=dados.telefone,
        tipo=dados.tipo,
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


@router.get("/me", response_model=UsuarioOut)
def meu_perfil(usuario_atual: Usuario = Depends(get_current_user)):
    return usuario_atual
