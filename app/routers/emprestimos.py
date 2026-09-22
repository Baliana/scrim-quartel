from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Emprestimo, Material, Usuario, MovimentacaoEstoque, WhatsappLog,
    StatusEmprestimoEnum, TipoMovimentacaoEnum, TipoUsuarioEnum, StatusEnvioEnum,
)
from app.schemas import (
    EmprestimoCreate, EmprestimoOut, EmprestimoDetalhado, EmprestimoUpdateStatus,
    WhatsappEnviarRequest, WhatsappLogOut,
)
from app.auth import get_current_user
from app.whatsapp_service import (
    whatsapp_service,
    mensagem_lembrete_devolucao,
    mensagem_atraso,
    mensagem_confirmacao_devolucao,
)

router = APIRouter(prefix="/emprestimos", tags=["Empréstimos"])


# ============================================================
# Helpers
# ============================================================

def _quantidade_emprestada(db: Session, material_id: int) -> int:
    from sqlalchemy import func
    total = (
        db.query(func.coalesce(func.sum(Emprestimo.quantidade), 0))
        .filter(
            Emprestimo.material_id == material_id,
            Emprestimo.status.in_([StatusEmprestimoEnum.ativo, StatusEmprestimoEnum.atrasado]),
        )
        .scalar()
    )
    return int(total)


def _atualizar_atrasados(db: Session) -> None:
    """Marca como 'atrasado' qualquer empréstimo ativo cujo prazo já passou."""
    hoje = date.today()
    db.query(Emprestimo).filter(
        Emprestimo.status == StatusEmprestimoEnum.ativo,
        Emprestimo.data_devolucao_prevista < hoje,
    ).update({"status": StatusEmprestimoEnum.atrasado}, synchronize_session=False)
    db.commit()


def _obter_emprestimo_ou_404(db: Session, emprestimo_id: int) -> Emprestimo:
    emprestimo = (
        db.query(Emprestimo)
        .options(joinedload(Emprestimo.usuario), joinedload(Emprestimo.material))
        .filter(Emprestimo.id == emprestimo_id)
        .first()
    )
    if not emprestimo:
        raise HTTPException(status_code=404, detail="Empréstimo não encontrado")
    return emprestimo


def _garantir_acesso(emprestimo: Emprestimo, usuario_atual: Usuario) -> None:
    """Cliente só acessa os próprios empréstimos; admin acessa todos."""
    if usuario_atual.tipo != TipoUsuarioEnum.admin and emprestimo.usuario_id != usuario_atual.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")


# ============================================================
# CRUD Empréstimos
# ============================================================

@router.get("", response_model=list[EmprestimoOut])
def listar_emprestimos(
    usuario_id: int | None = None,
    material_id: int | None = None,
    status_filtro: StatusEmprestimoEnum | None = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    _atualizar_atrasados(db)

    query = db.query(Emprestimo)

    # cliente só enxerga os próprios empréstimos ("Meus empréstimos")
    if usuario_atual.tipo != TipoUsuarioEnum.admin:
        query = query.filter(Emprestimo.usuario_id == usuario_atual.id)
    elif usuario_id:
        query = query.filter(Emprestimo.usuario_id == usuario_id)

    if material_id:
        query = query.filter(Emprestimo.material_id == material_id)
    if status_filtro:
        query = query.filter(Emprestimo.status == status_filtro)

    return query.order_by(Emprestimo.criado_em.desc()).offset(skip).limit(limit).all()


@router.get("/{emprestimo_id}", response_model=EmprestimoDetalhado)
def obter_emprestimo(
    emprestimo_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    _atualizar_atrasados(db)
    emprestimo = _obter_emprestimo_ou_404(db, emprestimo_id)
    _garantir_acesso(emprestimo, usuario_atual)
    return emprestimo


@router.post("", response_model=EmprestimoDetalhado, status_code=status.HTTP_201_CREATED)
def criar_emprestimo(
    dados: EmprestimoCreate,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    """
    Registra a retirada de um material.
    - Cliente: sempre retira para si mesmo (ignora `usuario_id` enviado, se houver).
    - Admin: pode registrar a retirada em nome de qualquer cliente via `usuario_id`.
    """
    if usuario_atual.tipo == TipoUsuarioEnum.admin and dados.usuario_id:
        beneficiario_id = dados.usuario_id
        beneficiario = db.query(Usuario).filter(Usuario.id == beneficiario_id).first()
        if not beneficiario:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
    else:
        beneficiario_id = usuario_atual.id

    # Serializa retiradas do mesmo material e evita saldo negativo por concorrência.
    material = (
        db.query(Material)
        .filter(Material.id == dados.material_id)
        .with_for_update()
        .first()
    )
    if not material or not material.ativo:
        raise HTTPException(status_code=404, detail="Material não encontrado ou inativo")

    disponivel = material.quantidade_total - _quantidade_emprestada(db, material.id)
    if dados.quantidade > disponivel:
        raise HTTPException(
            status_code=400,
            detail=f"Quantidade indisponível. Disponível no momento: {disponivel}",
        )

    prazo = dados.data_devolucao_prevista or (date.today() + timedelta(days=material.tempo_maximo_dias))

    emprestimo = Emprestimo(
        usuario_id=beneficiario_id,
        material_id=material.id,
        registrado_por_id=usuario_atual.id if usuario_atual.tipo == TipoUsuarioEnum.admin else None,
        quantidade=dados.quantidade,
        data_emprestimo=datetime.utcnow(),
        data_devolucao_prevista=prazo,
        status=StatusEmprestimoEnum.ativo,
    )
    db.add(emprestimo)
    db.flush()  # gera emprestimo.id sem commitar ainda

    db.add(MovimentacaoEstoque(
        material_id=material.id,
        emprestimo_id=emprestimo.id,
        tipo=TipoMovimentacaoEnum.saida,
        quantidade=dados.quantidade,
        motivo=f"Retirada por usuário #{beneficiario_id}",
        usuario_id=usuario_atual.id,
    ))

    db.commit()
    db.refresh(emprestimo)
    return _obter_emprestimo_ou_404(db, emprestimo.id)


@router.patch("/{emprestimo_id}/devolver", response_model=EmprestimoDetalhado)
def registrar_devolucao(
    emprestimo_id: int,
    db: Session = Depends(get_db),
    admin_atual: Usuario = Depends(get_current_user),
):
    """Confirma a devolução física do material (registrado pelo administrador/funcionário)."""
    if admin_atual.tipo != TipoUsuarioEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")

    emprestimo = _obter_emprestimo_ou_404(db, emprestimo_id)
    if emprestimo.status in (StatusEmprestimoEnum.devolvido, StatusEmprestimoEnum.cancelado):
        raise HTTPException(status_code=400, detail="Este empréstimo já foi encerrado")

    emprestimo.status = StatusEmprestimoEnum.devolvido
    emprestimo.data_devolucao_real = datetime.utcnow()

    db.add(MovimentacaoEstoque(
        material_id=emprestimo.material_id,
        emprestimo_id=emprestimo.id,
        tipo=TipoMovimentacaoEnum.devolucao,
        quantidade=emprestimo.quantidade,
        motivo=f"Devolução registrada por usuário #{admin_atual.id}",
        usuario_id=admin_atual.id,
    ))

    db.commit()
    db.refresh(emprestimo)
    return _obter_emprestimo_ou_404(db, emprestimo.id)


@router.patch("/{emprestimo_id}/status", response_model=EmprestimoOut)
def atualizar_status_emprestimo(
    emprestimo_id: int,
    dados: EmprestimoUpdateStatus,
    db: Session = Depends(get_db),
    admin_atual: Usuario = Depends(get_current_user),
):
    """Uso administrativo: cancelar um empréstimo, ou corrigir o status manualmente."""
    if admin_atual.tipo != TipoUsuarioEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")

    emprestimo = _obter_emprestimo_ou_404(db, emprestimo_id)

    # Alterar para "devolvido" diretamente não cria movimentação de estoque.
    # A devolução física deve passar pela rota /devolver.
    if dados.status != StatusEmprestimoEnum.cancelado:
        raise HTTPException(
            status_code=400,
            detail="Use a rota /devolver para concluir uma devolucao fisica",
        )
    if emprestimo.status not in (StatusEmprestimoEnum.ativo, StatusEmprestimoEnum.atrasado):
        raise HTTPException(status_code=400, detail="Este emprestimo ja foi encerrado")

    if dados.status == StatusEmprestimoEnum.cancelado and emprestimo.status not in (
        StatusEmprestimoEnum.devolvido, StatusEmprestimoEnum.cancelado,
    ):
        # cancelar devolve o item ao estoque disponível (ex.: empréstimo criado por engano)
        db.add(MovimentacaoEstoque(
            material_id=emprestimo.material_id,
            emprestimo_id=emprestimo.id,
            tipo=TipoMovimentacaoEnum.devolucao,
            quantidade=emprestimo.quantidade,
            motivo="Empréstimo cancelado",
            usuario_id=admin_atual.id,
        ))

    emprestimo.status = dados.status
    db.commit()
    db.refresh(emprestimo)
    return emprestimo


# ============================================================
# WhatsApp — envio real via Twilio
# ============================================================

@router.post("/{emprestimo_id}/whatsapp", response_model=WhatsappLogOut)
def enviar_whatsapp(
    emprestimo_id: int,
    dados: WhatsappEnviarRequest,
    db: Session = Depends(get_db),
    admin_atual: Usuario = Depends(get_current_user),
):
    """
    Envia uma mensagem WhatsApp para o cliente do empréstimo via Twilio.
    Se `mensagem` não for informada, gera uma mensagem padrão a partir do `tipo`.
    """
    if admin_atual.tipo != TipoUsuarioEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")

    emprestimo = _obter_emprestimo_ou_404(db, emprestimo_id)
    cliente = emprestimo.usuario

    if not cliente.telefone:
        raise HTTPException(status_code=400, detail="Cliente não possui telefone cadastrado")

    mensagem = dados.mensagem
    if not mensagem:
        material_nome = emprestimo.material.nome
        prazo_str = emprestimo.data_devolucao_prevista.strftime("%d/%m/%Y")

        if dados.tipo == "lembrete_devolucao":
            mensagem = mensagem_lembrete_devolucao(cliente.nome, material_nome, prazo_str)
        elif dados.tipo == "atraso":
            mensagem = mensagem_atraso(cliente.nome, material_nome, prazo_str)
        elif dados.tipo == "confirmacao_devolucao":
            mensagem = mensagem_confirmacao_devolucao(cliente.nome, material_nome)
        else:
            raise HTTPException(status_code=400, detail="Informe `mensagem` para este tipo")

    resultado = whatsapp_service.enviar_mensagem(cliente.telefone, mensagem)

    log = WhatsappLog(
        usuario_id=cliente.id,
        emprestimo_id=emprestimo.id,
        tipo=dados.tipo,
        mensagem=mensagem,
        twilio_sid=resultado["sid"],
        status_envio=StatusEnvioEnum.enviado if resultado["sucesso"] else StatusEnvioEnum.falha,
        erro=resultado["erro"],
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    if not resultado["sucesso"]:
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao enviar WhatsApp: {resultado['erro']}",
        )

    return log


@router.get("/{emprestimo_id}/whatsapp/historico", response_model=list[WhatsappLogOut])
def historico_whatsapp(
    emprestimo_id: int,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
):
    emprestimo = _obter_emprestimo_ou_404(db, emprestimo_id)
    _garantir_acesso(emprestimo, usuario_atual)
    return (
        db.query(WhatsappLog)
        .filter(WhatsappLog.emprestimo_id == emprestimo_id)
        .order_by(WhatsappLog.criado_em.desc())
        .all()
    )
