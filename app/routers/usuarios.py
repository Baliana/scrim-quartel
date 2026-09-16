from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Usuario, TipoUsuarioEnum
from app.schemas import UsuarioOut, UsuarioUpdate
from app.auth import get_current_user, exigir_admin

router = APIRouter(prefix="/usuarios", tags=["Usuários"])


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    tipo: Optional[TipoUsuarioEnum] = None,
    busca: Optional[str] = Query(None, description="Busca por nome ou e-mail"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    query = db.query(Usuario)
    if tipo:
        query = query.filter(Usuario.tipo == tipo)
    if busca:
        termo = f"%{busca}%"
        query = query.filter(or_(Usuario.nome.like(termo), Usuario.email.like(termo)))
    return query.order_by(Usuario.nome).offset(skip).limit(limit).all()


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obter_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    # um cliente só pode ver o próprio perfil; admin pode ver qualquer um
    if usuario_atual.tipo != TipoUsuarioEnum.admin and usuario_atual.id != usuario_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


@router.put("/{usuario_id}", response_model=UsuarioOut)
def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioUpdate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(usuario, campo, valor)

    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    """Desativa o usuário (não exclui, para preservar histórico de empréstimos)."""
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    usuario.ativo = False
    db.commit()
