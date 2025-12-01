from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List

from backend.models.models import TipoTransacao, StatusTransacao, OrigemRegistro


# ==================== Usuario ====================

class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None


class UsuarioCriar(UsuarioBase):
    senha: str


class UsuarioAtualizar(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None


class UsuarioAlterarSenha(BaseModel):
    senha_atual: str
    senha_nova: str


class UsuarioResposta(UsuarioBase):
    id: int
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


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
    nome: str
    telefone: str


class MembroFamiliaCriar(MembroFamiliaBase):
    pass


class MembroFamiliaAtualizar(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    ativo: Optional[bool] = None


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
