from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Material, Categoria, Emprestimo, MovimentacaoEstoque, Usuario,
    StatusEmprestimoEnum, TipoMovimentacaoEnum,
)
from app.schemas import (
    MaterialCreate, MaterialUpdate, MaterialOut, MaterialDisponibilidade,
    MovimentacaoEstoqueCreate, MovimentacaoEstoqueOut,
)
from app.auth import get_current_user, exigir_admin

router = APIRouter(prefix="/materiais", tags=["Materiais"])

STATUS_EMPRESTADO = (StatusEmprestimoEnum.ativo, StatusEmprestimoEnum.atrasado)


# ============================================================
# Helpers de disponibilidade
# ============================================================

def _quantidade_emprestada(db: Session, material_id: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(Emprestimo.quantidade), 0))
        .filter(Emprestimo.material_id == material_id, Emprestimo.status.in_(STATUS_EMPRESTADO))
        .scalar()
    )
    return int(total)


def _para_disponibilidade(db: Session, material: Material) -> MaterialDisponibilidade:
    emprestada = _quantidade_emprestada(db, material.id)
    return MaterialDisponibilidade(
        **MaterialOut.model_validate(material).model_dump(),
        categoria=material.categoria,
        quantidade_emprestada=emprestada,
        quantidade_disponivel=material.quantidade_total - emprestada,
    )


def _obter_material_ou_404(db: Session, material_id: int) -> Material:
    material = (
        db.query(Material)
        .options(joinedload(Material.categoria))
        .filter(Material.id == material_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")
    return material


# ============================================================
# CRUD Materiais
# ============================================================

@router.get("", response_model=list[MaterialDisponibilidade])
def listar_materiais(
    categoria_id: Optional[int] = None,
    busca: Optional[str] = Query(None, description="Busca por nome ou código"),
    apenas_disponiveis: bool = False,
    somente_ativos: bool = True,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
):
    query = db.query(Material).options(joinedload(Material.categoria))
    if categoria_id:
        query = query.filter(Material.categoria_id == categoria_id)
    if busca:
        termo = f"%{busca}%"
        query = query.filter(or_(Material.nome.like(termo), Material.codigo.like(termo)))
    if somente_ativos:
        query = query.filter(Material.ativo.is_(True))

    materiais = query.order_by(Material.nome).offset(skip).limit(limit).all()
    resultado = [_para_disponibilidade(db, m) for m in materiais]

    if apenas_disponiveis:
        resultado = [m for m in resultado if m.quantidade_disponivel > 0]

    return resultado


@router.get("/{material_id}", response_model=MaterialDisponibilidade)
def obter_material(
    material_id: int,
    db: Session = Depends(get_db),
    _usuario: Usuario = Depends(get_current_user),
):
    material = _obter_material_ou_404(db, material_id)
    return _para_disponibilidade(db, material)


@router.post("", response_model=MaterialOut, status_code=status.HTTP_201_CREATED)
def criar_material(
    dados: MaterialCreate,
    db: Session = Depends(get_db),
    admin_atual: Usuario = Depends(exigir_admin),
):
    categoria = db.query(Categoria).filter(Categoria.id == dados.categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    existente = db.query(Material).filter(Material.codigo == dados.codigo).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe um material com esse código")

    material = Material(**dados.model_dump())
    db.add(material)
    db.commit()
    db.refresh(material)

    if material.quantidade_total > 0:
        db.add(MovimentacaoEstoque(
            material_id=material.id,
            tipo=TipoMovimentacaoEnum.entrada,
            quantidade=material.quantidade_total,
            motivo="Cadastro inicial do material",
            usuario_id=admin_atual.id,
        ))
        db.commit()

    return material


@router.put("/{material_id}", response_model=MaterialOut)
def atualizar_material(
    material_id: int,
    dados: MaterialUpdate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    if dados.categoria_id is not None:
        categoria = db.query(Categoria).filter(Categoria.id == dados.categoria_id).first()
        if not categoria:
            raise HTTPException(status_code=404, detail="Categoria não encontrada")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(material, campo, valor)

    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_material(
    material_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    """Desativa o material (não exclui, para preservar o histórico de empréstimos/movimentações)."""
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    material.ativo = False
    db.commit()


# ============================================================
# Movimentações de estoque
# ============================================================

@router.post("/{material_id}/movimentacoes", response_model=MovimentacaoEstoqueOut, status_code=status.HTTP_201_CREATED)
def registrar_movimentacao(
    material_id: int,
    dados: MovimentacaoEstoqueCreate,
    db: Session = Depends(get_db),
    admin_atual: Usuario = Depends(exigir_admin),
):
    """
    Registra entrada, perda, dano ou ajuste manual de estoque.
    (Saídas e devoluções são geradas automaticamente pelas rotas de /emprestimos.)
    """
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material não encontrado")

    if dados.tipo in (TipoMovimentacaoEnum.saida, TipoMovimentacaoEnum.devolucao):
        raise HTTPException(
            status_code=400,
            detail="Saídas e devoluções são registradas automaticamente via /emprestimos",
        )

    if dados.tipo == TipoMovimentacaoEnum.entrada:
        material.quantidade_total += dados.quantidade
    elif dados.tipo in (TipoMovimentacaoEnum.perda, TipoMovimentacaoEnum.danificado):
        if dados.quantidade > material.quantidade_total:
            raise HTTPException(status_code=400, detail="Quantidade maior que o total em estoque")
        material.quantidade_total -= dados.quantidade
    elif dados.tipo == TipoMovimentacaoEnum.ajuste:
        # Para "ajuste", `quantidade` representa a NOVA quantidade_total (contagem física),
        # não um delta. Útil para corrigir divergências de inventário. O `motivo` deve
        # explicar a divergência encontrada.
        material.quantidade_total = dados.quantidade

    movimentacao = MovimentacaoEstoque(
        material_id=material.id,
        tipo=dados.tipo,
        quantidade=dados.quantidade,
        motivo=dados.motivo,
        usuario_id=admin_atual.id,
    )
    db.add(movimentacao)
    db.commit()
    db.refresh(movimentacao)
    return movimentacao


@router.get("/{material_id}/movimentacoes", response_model=list[MovimentacaoEstoqueOut])
def historico_movimentacoes(
    material_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(exigir_admin),
):
    _obter_material_ou_404(db, material_id)
    return (
        db.query(MovimentacaoEstoque)
        .filter(MovimentacaoEstoque.material_id == material_id)
        .order_by(MovimentacaoEstoque.criado_em.desc())
        .offset(skip).limit(limit)
        .all()
    )
