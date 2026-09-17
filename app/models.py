import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    Text, ForeignKey, Enum, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class TipoUsuarioEnum(str, enum.Enum):
    cliente = "cliente"
    admin = "admin"


class StatusEmprestimoEnum(str, enum.Enum):
    ativo = "ativo"
    devolvido = "devolvido"
    atrasado = "atrasado"
    cancelado = "cancelado"


class TipoMovimentacaoEnum(str, enum.Enum):
    entrada = "entrada"
    saida = "saida"
    devolucao = "devolucao"
    perda = "perda"
    danificado = "danificado"
    ajuste = "ajuste"


class TipoMensagemEnum(str, enum.Enum):
    lembrete_devolucao = "lembrete_devolucao"
    atraso = "atraso"
    confirmacao_devolucao = "confirmacao_devolucao"
    outro = "outro"


class StatusEnvioEnum(str, enum.Enum):
    enviado = "enviado"
    falha = "falha"


class Usuario(Base):
    """Cliente (quem retira materiais) ou Admin/Funcionário (quem gerencia o sistema)."""
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    telefone = Column(String(20), nullable=True)  # formato E.164, ex: +5511999999999 (usado no WhatsApp)
    tipo = Column(Enum(TipoUsuarioEnum), nullable=False, default=TipoUsuarioEnum.cliente)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emprestimos = relationship("Emprestimo", back_populates="usuario", foreign_keys="Emprestimo.usuario_id")
    movimentacoes_registradas = relationship("MovimentacaoEstoque", back_populates="usuario")


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)
    descricao = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    materiais = relationship("Material", back_populates="categoria")


class Material(Base):
    __tablename__ = "materiais"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    codigo = Column(String(50), nullable=False, unique=True, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    quantidade_total = Column(Integer, nullable=False, default=0)
    tempo_maximo_dias = Column(Integer, nullable=False, default=7)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria = relationship("Categoria", back_populates="materiais")
    emprestimos = relationship("Emprestimo", back_populates="material")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="material")

    # NOTA: a quantidade disponível NÃO é armazenada aqui. Ela é sempre calculada
    # em tempo real (quantidade_total - soma dos empréstimos ativos/atrasados),
    # para evitar que o banco "minta" sobre a disponibilidade real do estoque.


class Emprestimo(Base):
    __tablename__ = "emprestimos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)  # cliente que retirou
    material_id = Column(Integer, ForeignKey("materiais.id"), nullable=False)
    registrado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)  # admin que registrou (se houver)
    quantidade = Column(Integer, nullable=False, default=1)
    data_emprestimo = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_devolucao_prevista = Column(Date, nullable=False)
    data_devolucao_real = Column(DateTime, nullable=True)
    status = Column(Enum(StatusEmprestimoEnum), nullable=False, default=StatusEmprestimoEnum.ativo)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="emprestimos", foreign_keys=[usuario_id])
    registrado_por = relationship("Usuario", foreign_keys=[registrado_por_id])
    material = relationship("Material", back_populates="emprestimos")
    movimentacoes = relationship("MovimentacaoEstoque", back_populates="emprestimo")


class MovimentacaoEstoque(Base):
    """Histórico de tudo que acontece com o estoque (entradas, saídas, devoluções, perdas, ajustes)."""
    __tablename__ = "movimentacoes_estoque"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materiais.id"), nullable=False)
    emprestimo_id = Column(Integer, ForeignKey("emprestimos.id"), nullable=True)
    tipo = Column(Enum(TipoMovimentacaoEnum), nullable=False)
    quantidade = Column(Integer, nullable=False)
    motivo = Column(String(255), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)  # quem registrou a movimentação
    criado_em = Column(DateTime, default=datetime.utcnow)

    material = relationship("Material", back_populates="movimentacoes")
    emprestimo = relationship("Emprestimo", back_populates="movimentacoes")
    usuario = relationship("Usuario", back_populates="movimentacoes_registradas")


class WhatsappLog(Base):
    __tablename__ = "whatsapp_logs"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)  # cliente destinatário
    emprestimo_id = Column(Integer, ForeignKey("emprestimos.id"), nullable=True)
    tipo = Column(Enum(TipoMensagemEnum), nullable=False, default=TipoMensagemEnum.outro)
    mensagem = Column(Text, nullable=False)
    twilio_sid = Column(String(64), nullable=True)
    status_envio = Column(Enum(StatusEnvioEnum), nullable=False)
    erro = Column(Text, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)


class cadastro(Base):
    __tablename__ = "cadastro"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True, index=True)
    telefone = Column(String(20), nullable=True)  # formato E.164, ex: +5511999999999 (usado no WhatsApp)
    criado_em = Column(DateTime, default=datetime.utcnow    )