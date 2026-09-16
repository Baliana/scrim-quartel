from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Categoria, Usuario
from app.schemas import CategoriaCreate, CategoriaUpdate, CategoriaOut
from app.auth import get_current_user, exigir_admin

router = APIRouter(prefix="/categorias", tags=["Categorias"])


@router.get("", response_model=list[CategoriaOut])
def listar_categorias(
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
):
    return db.query(Categoria).order_by(Categoria.nome).all()


@router.get("/{categoria_id}", response_model=CategoriaOut)
def obter_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return categoria


@router.post("", response_model=CategoriaOut, status_code=status.HTTP_201_CREATED)
def criar_categoria(
    dados: CategoriaCreate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    existente = db.query(Categoria).filter(Categoria.nome == dados.nome).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe uma categoria com esse nome")

    categoria = Categoria(**dados.model_dump())
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.put("/{categoria_id}", response_model=CategoriaOut)
def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaUpdate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if categoria.materiais:
        raise HTTPException(
            status_code=400,
            detail="Não é possível excluir categoria com materiais vinculados",
        )

    db.delete(categoria)
    db.commit()
