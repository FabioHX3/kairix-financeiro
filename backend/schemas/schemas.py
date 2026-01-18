from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List
import re

from backend.models.models import TipoTransacao, StatusTransacao, OrigemRegistro


# ==================== Usuario ====================

class UsuarioBase(BaseModel):
    """Schema base para usuário"""
    nome: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nome completo do usuário",
        json_schema_extra={"example": "João da Silva"}
    )
    email: EmailStr = Field(
        ...,
        description="Email do usuário (usado para login)",
        json_schema_extra={"example": "joao@email.com"}
    )
    whatsapp: Optional[str] = Field(
        None,
        min_length=10,
        max_length=15,
        description="WhatsApp com DDD (apenas números) - usado para integração com bot",
        json_schema_extra={"example": "11999998888"}
    )

    @field_validator('whatsapp', mode='before')
    @classmethod
    def limpar_whatsapp(cls, v):
        if v is None:
            return v
        # Remove tudo que não é número
        numeros = re.sub(r'\D', '', str(v))
        if numeros and (len(numeros) < 10 or len(numeros) > 15):
            raise ValueError('WhatsApp deve ter entre 10 e 15 dígitos')
        return numeros if numeros else None


class UsuarioCriar(UsuarioBase):
    """
    Schema para criação de novo usuário.

    Use este endpoint para cadastrar novos usuários no sistema.
    O WhatsApp é opcional, mas necessário para usar o bot de registro por mensagem.
    """
    senha: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Senha do usuário (mínimo 6 caracteres)",
        json_schema_extra={"example": "senha123"}
    )


class UsuarioAtualizar(BaseModel):
    """Schema para atualização de dados do usuário"""
    nome: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Nome completo do usuário"
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Email do usuário"
    )
    whatsapp: Optional[str] = Field(
        None,
        min_length=10,
        max_length=15,
        description="WhatsApp com DDD (apenas números)"
    )

    @field_validator('whatsapp', mode='before')
    @classmethod
    def limpar_whatsapp(cls, v):
        if v is None:
            return v
        numeros = re.sub(r'\D', '', str(v))
        if numeros and (len(numeros) < 10 or len(numeros) > 15):
            raise ValueError('WhatsApp deve ter entre 10 e 15 dígitos')
        return numeros if numeros else None


class UsuarioAlterarSenha(BaseModel):
    """Schema para alteração de senha"""
    senha_atual: str = Field(
        ...,
        description="Senha atual do usuário"
    )
    senha_nova: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Nova senha (mínimo 6 caracteres)"
    )


class UsuarioResposta(BaseModel):
    """
    Schema de resposta com dados do usuário.

    Retornado após cadastro, login ou consulta de dados.
    Não inclui a senha por segurança.
    """
    id: int = Field(..., description="ID único do usuário")
    nome: str = Field(..., description="Nome completo")
    email: EmailStr = Field(..., description="Email do usuário")
    whatsapp: Optional[str] = Field(None, description="WhatsApp com DDD")
    ativo: bool = Field(..., description="Se o usuário está ativo no sistema")
    criado_em: datetime = Field(..., description="Data de criação do cadastro")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "nome": "João da Silva",
                "email": "joao@email.com",
                "whatsapp": "11999998888",
                "ativo": True,
                "criado_em": "2025-01-18T10:00:00Z"
            }
        }


# ==================== Auth ====================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class SystemLoginRequest(BaseModel):
    api_key: str
    user_email: EmailStr


# ==================== Membro Familia ====================

class MembroFamiliaBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100, description="Nome do membro da família")
    whatsapp: str = Field(..., min_length=10, max_length=15, description="WhatsApp do membro (apenas números)")

    @field_validator('whatsapp', mode='before')
    @classmethod
    def limpar_whatsapp(cls, v):
        if v is None:
            return v
        numeros = re.sub(r'\D', '', str(v))
        if numeros and (len(numeros) < 10 or len(numeros) > 15):
            raise ValueError('WhatsApp deve ter entre 10 e 15 dígitos')
        return numeros if numeros else None


class MembroFamiliaCriar(MembroFamiliaBase):
    pass


class MembroFamiliaAtualizar(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=100)
    whatsapp: Optional[str] = Field(None, min_length=10, max_length=15)
    ativo: Optional[bool] = None

    @field_validator('whatsapp', mode='before')
    @classmethod
    def limpar_whatsapp(cls, v):
        if v is None:
            return v
        numeros = re.sub(r'\D', '', str(v))
        if numeros and (len(numeros) < 10 or len(numeros) > 15):
            raise ValueError('WhatsApp deve ter entre 10 e 15 dígitos')
        return numeros if numeros else None


class MembroFamiliaResposta(MembroFamiliaBase):
    id: int
    usuario_id: int
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


# ==================== Categoria ====================

class CategoriaBase(BaseModel):
    nome: str
    tipo: TipoTransacao
    cor: Optional[str] = "#0EA5E9"
    icone: Optional[str] = "💰"


class CategoriaCriar(CategoriaBase):
    pass


class CategoriaAtualizar(BaseModel):
    nome: Optional[str] = None
    cor: Optional[str] = None
    icone: Optional[str] = None


class CategoriaResposta(CategoriaBase):
    id: int
    padrao: bool
    criado_em: datetime

    class Config:
        from_attributes = True


# ==================== Transacao ====================

class TransacaoBase(BaseModel):
    tipo: TipoTransacao
    valor: float = Field(gt=0, description="Valor deve ser maior que zero")
    descricao: Optional[str] = None
    data_transacao: datetime
    categoria_id: Optional[int] = None


class TransacaoCriar(TransacaoBase):
    origem: OrigemRegistro = OrigemRegistro.WEB


class TransacaoAtualizar(BaseModel):
    tipo: Optional[TipoTransacao] = None
    valor: Optional[float] = Field(None, gt=0)
    descricao: Optional[str] = None
    data_transacao: Optional[datetime] = None
    categoria_id: Optional[int] = None
    status: Optional[StatusTransacao] = None


class TransacaoResposta(TransacaoBase):
    id: int
    usuario_id: int
    status: StatusTransacao
    origem: OrigemRegistro
    mensagem_original: Optional[str] = None
    arquivo_url: Optional[str] = None
    confianca_ia: Optional[float] = None
    criado_em: datetime
    atualizado_em: datetime
    categoria: Optional[CategoriaResposta] = None

    class Config:
        from_attributes = True


# ==================== Dashboard ====================

class ResumoPeriodo(BaseModel):
    total_receitas: float
    total_despesas: float
    saldo: float
    quantidade_receitas: int
    quantidade_despesas: int


class ResumoCategoria(BaseModel):
    categoria_id: int
    categoria_nome: str
    categoria_icone: str
    categoria_cor: str
    total: float
    quantidade: int
    percentual: float


class DashboardResposta(BaseModel):
    periodo: str
    resumo_geral: ResumoPeriodo
    receitas_por_categoria: List[ResumoCategoria]
    despesas_por_categoria: List[ResumoCategoria]
    ultimas_transacoes: List[TransacaoResposta]
    evolucao_mensal: List[dict]


# ==================== WhatsApp ====================

class WhatsAppMessage(BaseModel):
    from_number: str
    message_type: str
    text: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    timestamp: datetime
