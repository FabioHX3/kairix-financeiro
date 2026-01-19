import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.models.models import OrigemRegistro, StatusTransacao, TipoTransacao

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
    whatsapp: str | None = Field(
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
        min_length=8,
        max_length=100,
        description="Senha com mínimo 8 caracteres, letras maiúsculas/minúsculas e números",
        json_schema_extra={"example": "Senha123"},
    )

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, v: str) -> str:
        """Valida força da senha."""
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v


class UsuarioAtualizar(BaseModel):
    """Schema para atualização de dados do usuário"""
    nome: str | None = Field(
        None,
        min_length=2,
        max_length=100,
        description="Nome completo do usuário"
    )
    email: EmailStr | None = Field(
        None,
        description="Email do usuário"
    )
    whatsapp: str | None = Field(
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
    """Schema para alteração de senha."""

    senha_atual: str = Field(..., description="Senha atual do usuário")
    senha_nova: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Nova senha com mínimo 8 caracteres, letras maiúsculas/minúsculas e números",
    )

    @field_validator("senha_nova")
    @classmethod
    def validar_senha_nova(cls, v: str) -> str:
        """Valida força da nova senha."""
        if len(v) < 8:
            raise ValueError("Senha deve ter no mínimo 8 caracteres")
        if not re.search(r"[a-z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra minúscula")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Senha deve conter pelo menos uma letra maiúscula")
        if not re.search(r"\d", v):
            raise ValueError("Senha deve conter pelo menos um número")
        return v


class UsuarioResposta(BaseModel):
    """
    Schema de resposta com dados do usuário.

    Retornado após cadastro, login ou consulta de dados.
    Não inclui a senha por segurança.
    """

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "nome": "João da Silva",
                "email": "joao@email.com",
                "whatsapp": "11999998888",
                "ativo": True,
                "criado_em": "2025-01-18T10:00:00Z"
            }
        }
    }

    id: int = Field(..., description="ID único do usuário")
    nome: str = Field(..., description="Nome completo")
    email: EmailStr = Field(..., description="Email do usuário")
    whatsapp: str | None = Field(None, description="WhatsApp com DDD")
    ativo: bool = Field(..., description="Se o usuário está ativo no sistema")
    criado_em: datetime = Field(..., description="Data de criação do cadastro")


# ==================== Auth ====================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None


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
    nome: str | None = Field(None, min_length=2, max_length=100)
    whatsapp: str | None = Field(None, min_length=10, max_length=15)
    ativo: bool | None = None

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
    cor: str | None = "#0EA5E9"
    icone: str | None = "💰"


class CategoriaCriar(CategoriaBase):
    pass


class CategoriaAtualizar(BaseModel):
    nome: str | None = None
    cor: str | None = None
    icone: str | None = None


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
    descricao: str | None = None
    data_transacao: datetime
    categoria_id: int | None = None


class TransacaoCriar(TransacaoBase):
    origem: OrigemRegistro = OrigemRegistro.WEB


class TransacaoAtualizar(BaseModel):
    tipo: TipoTransacao | None = None
    valor: float | None = Field(None, gt=0)
    descricao: str | None = None
    data_transacao: datetime | None = None
    categoria_id: int | None = None
    status: StatusTransacao | None = None


class TransacaoResposta(TransacaoBase):
    id: int
    usuario_id: int
    status: StatusTransacao
    origem: OrigemRegistro
    mensagem_original: str | None = None
    arquivo_url: str | None = None
    confianca_ia: float | None = None
    criado_em: datetime
    atualizado_em: datetime
    categoria: CategoriaResposta | None = None

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
    receitas_por_categoria: list[ResumoCategoria]
    despesas_por_categoria: list[ResumoCategoria]
    ultimas_transacoes: list[TransacaoResposta]
    evolucao_mensal: list[dict]


# ==================== WhatsApp ====================

class WhatsAppMessage(BaseModel):
    from_number: str
    message_type: str
    text: str | None = None
    audio_url: str | None = None
    image_url: str | None = None
    timestamp: datetime
