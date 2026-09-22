from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator

from app.models import (
    TipoUsuarioEnum, StatusEmprestimoEnum, TipoMovimentacaoEnum,
    TipoMensagemEnum, StatusEnvioEnum,
)


# --------------------------- Auth ---------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class cadastroRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: EmailStr
    telefone: Optional[str] = Field(default=None, description="Formato E.164, ex: +5511999999999")
    id: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: "UsuarioOut"


# --------------------------- Usuário ---------------------------

class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: EmailStr
    senha: str = Field(min_length=6)
    telefone: Optional[str] = Field(default=None, description="Formato E.164, ex: +5511999999999")
    tipo: TipoUsuarioEnum = TipoUsuarioEnum.cliente
    id_militar: Optional[str] = Field(default=None, max_length=80)

    @field_validator("id_militar")
    @classmethod
    def normalizar_id_militar(cls, id_militar: Optional[str]) -> Optional[str]:
        if id_militar is None or not id_militar.strip():
            return None
        return id_militar.strip().upper()

    @model_validator(mode="after")
    def exigir_id_militar_do_admin(self):
        if self.tipo == TipoUsuarioEnum.admin and not self.id_militar:
            raise ValueError("ID militar e obrigatorio para administrador")
        return self


class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    ativo: Optional[bool] = None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: EmailStr
    telefone: Optional[str]
    tipo: TipoUsuarioEnum
    ativo: bool
    criado_em: datetime


# --------------------------- Categoria ---------------------------

class CategoriaCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=100)
    descricao: Optional[str] = None


class CategoriaUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    descricao: Optional[str]
    criado_em: datetime


# --------------------------- Material ---------------------------

class MaterialCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    descricao: Optional[str] = None
    codigo: str = Field(min_length=1, max_length=50)
    categoria_id: int
    quantidade_total: int = Field(ge=0, default=0)
    tempo_maximo_dias: int = Field(gt=0, default=7)


class MaterialUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    categoria_id: Optional[int] = None
    tempo_maximo_dias: Optional[int] = None
    ativo: Optional[bool] = None


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    descricao: Optional[str]
    codigo: str
    categoria_id: int
    quantidade_total: int
    tempo_maximo_dias: int
    ativo: bool
    criado_em: datetime


class MaterialDisponibilidade(MaterialOut):
    """Material com a quantidade disponível calculada em tempo real."""
    categoria: CategoriaOut
    quantidade_disponivel: int
    quantidade_emprestada: int


# --------------------------- Movimentação de estoque ---------------------------

class MovimentacaoEstoqueCreate(BaseModel):
    tipo: TipoMovimentacaoEnum
    quantidade: int = Field(gt=0)
    motivo: Optional[str] = None


class MovimentacaoEstoqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    material_id: int
    emprestimo_id: Optional[int]
    tipo: TipoMovimentacaoEnum
    quantidade: int
    motivo: Optional[str]
    usuario_id: int
    criado_em: datetime


# --------------------------- Empréstimo ---------------------------

class EmprestimoCreate(BaseModel):
    material_id: int
    quantidade: int = Field(gt=0, default=1)
    usuario_id: Optional[int] = None  # admin pode informar o cliente; cliente sempre pega para si mesmo
    data_devolucao_prevista: Optional[date] = None  # se omitido, usa tempo_maximo_dias do material


class EmprestimoUpdateStatus(BaseModel):
    status: StatusEmprestimoEnum


class EmprestimoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    material_id: int
    registrado_por_id: Optional[int]
    quantidade: int
    data_emprestimo: datetime
    data_devolucao_prevista: date
    data_devolucao_real: Optional[datetime]
    status: StatusEmprestimoEnum
    criado_em: datetime


class EmprestimoDetalhado(EmprestimoOut):
    usuario: UsuarioOut
    material: MaterialOut


# --------------------------- WhatsApp ---------------------------

class WhatsappEnviarRequest(BaseModel):
    tipo: TipoMensagemEnum = TipoMensagemEnum.outro
    mensagem: Optional[str] = None  # se omitido, gera mensagem padrão a partir do tipo


class WhatsappLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usuario_id: int
    emprestimo_id: Optional[int]
    tipo: TipoMensagemEnum
    mensagem: str
    twilio_sid: Optional[str]
    status_envio: StatusEnvioEnum
    erro: Optional[str]
    criado_em: datetime


TokenResponse.model_rebuild()
