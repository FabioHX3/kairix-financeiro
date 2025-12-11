from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import secrets
import string

from backend.core.database import engine, SessionLocal

Base = declarative_base()


def _gerar_codigo_formato() -> str:
    """Gera código no formato LL+NN+L (ex: AB12C) - mais legível que aleatório puro"""
    letras = string.ascii_uppercase
    numeros = string.digits
    return (
        secrets.choice(letras) +
        secrets.choice(letras) +
        secrets.choice(numeros) +
        secrets.choice(numeros) +
        secrets.choice(letras)
    )


def gerar_codigo_unico(db=None) -> str:
    """
    Gera código único no formato LL+NN+L (ex: AB12C).
    Se db for fornecido, verifica unicidade no banco.
    """
    max_tentativas = 10
    for _ in range(max_tentativas):
        codigo = _gerar_codigo_formato()
        if db is None:
            return codigo
        # Verifica se já existe no banco
        from backend.models.models import Transacao
        existente = db.query(Transacao).filter(Transacao.codigo == codigo).first()
        if not existente:
            return codigo
    # Fallback: adiciona timestamp se todas tentativas falharem (improvável)
    import time
    return _gerar_codigo_formato() + str(int(time.time()))[-2:]


class TipoTransacao(str, enum.Enum):
    RECEITA = "receita"
    DESPESA = "despesa"


class StatusTransacao(str, enum.Enum):
    PENDENTE = "pendente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"


class OrigemRegistro(str, enum.Enum):
    WHATSAPP_TEXTO = "whatsapp_texto"
    WHATSAPP_AUDIO = "whatsapp_audio"
    WHATSAPP_IMAGEM = "whatsapp_imagem"
    WEB = "web"
    API = "api"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    telefone = Column(String(20), unique=True, index=True)
    whatsapp = Column(String(20), unique=True, index=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    transacoes = relationship("Transacao", back_populates="usuario")
    categorias = relationship("Categoria", back_populates="usuario")
    membros_familia = relationship("MembroFamilia", back_populates="usuario")
    padroes = relationship("UserPattern", back_populates="usuario")
    preferencias = relationship("UserPreferences", back_populates="usuario", uselist=False)


class MembroFamilia(Base):
    __tablename__ = "membros_familia"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    nome = Column(String(255), nullable=False)
    telefone = Column(String(20), nullable=False, index=True)
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="membros_familia")
    transacoes = relationship("Transacao", back_populates="membro_familia")


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    nome = Column(String(100), nullable=False)
    tipo = Column(Enum(TipoTransacao), nullable=False)
    cor = Column(String(7), default="#0EA5E9")
    icone = Column(String(50), default="💰")
    padrao = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="categorias")
    transacoes = relationship("Transacao", back_populates="categoria")


class PersonalidadeIA(str, enum.Enum):
    """Personalidades disponíveis para o assistente"""
    FORMAL = "formal"
    AMIGAVEL = "amigavel"
    DIVERTIDO = "divertido"


class UserPattern(Base):
    """
    Padrões aprendidos do usuário.
    Mapeia palavras-chave para categorias baseado no histórico.
    """
    __tablename__ = "user_patterns"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)

    # Padrão de texto (normalizado, sem acentos, lowercase)
    palavras_chave = Column(String(255), nullable=False, index=True)

    # Tipo da transação associada
    tipo = Column(Enum(TipoTransacao), nullable=False)

    # Métricas de confiança
    ocorrencias = Column(Integer, default=1)
    confianca = Column(Float, default=0.5)  # 0.0 a 1.0

    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="padroes")
    categoria = relationship("Categoria")


class UserPreferences(Base):
    """
    Preferências do usuário para o assistente.
    """
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, unique=True)

    # Personalidade do assistente
    personalidade = Column(Enum(PersonalidadeIA), default=PersonalidadeIA.AMIGAVEL)

    # Configurações de alertas
    alertar_vencimentos = Column(Boolean, default=True)
    dias_antes_vencimento = Column(Integer, default=3)
    alertar_gastos_anomalos = Column(Boolean, default=True)
    limite_anomalia_percentual = Column(Integer, default=30)  # Alerta se gastar 30% acima da média

    # Resumos automáticos
    resumo_diario = Column(Boolean, default=False)
    resumo_semanal = Column(Boolean, default=True)
    resumo_mensal = Column(Boolean, default=True)
    horario_resumo = Column(String(5), default="09:00")  # HH:MM

    # Auto-confirmação
    auto_confirmar_confianca = Column(Float, default=0.90)  # Auto-confirma se confiança >= 90%

    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="preferencias")


class Transacao(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(5), unique=True, index=True, default=gerar_codigo_unico)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    membro_familia_id = Column(Integer, ForeignKey("membros_familia.id"), nullable=True)
    tipo = Column(Enum(TipoTransacao), nullable=False)
    valor = Column(Float, nullable=False)
    descricao = Column(Text)
    data_transacao = Column(DateTime, nullable=False)
    status = Column(Enum(StatusTransacao), default=StatusTransacao.CONFIRMADA)
    origem = Column(Enum(OrigemRegistro), nullable=False)

    # Campos WhatsApp
    mensagem_original = Column(Text)
    arquivo_url = Column(String(500))
    confianca_ia = Column(Float)

    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="transacoes")
    categoria = relationship("Categoria", back_populates="transacoes")
    membro_familia = relationship("MembroFamilia", back_populates="transacoes")


# Categorias padrão
CATEGORIAS_PADRAO = [
    # Despesas
    {"nome": "Alimentação", "tipo": TipoTransacao.DESPESA, "icone": "🍽️", "cor": "#F59E0B"},
    {"nome": "Transporte", "tipo": TipoTransacao.DESPESA, "icone": "🚗", "cor": "#3B82F6"},
    {"nome": "Saúde", "tipo": TipoTransacao.DESPESA, "icone": "🏥", "cor": "#EF4444"},
    {"nome": "Educação", "tipo": TipoTransacao.DESPESA, "icone": "📚", "cor": "#8B5CF6"},
    {"nome": "Lazer", "tipo": TipoTransacao.DESPESA, "icone": "🎮", "cor": "#EC4899"},
    {"nome": "Casa", "tipo": TipoTransacao.DESPESA, "icone": "🏠", "cor": "#10B981"},
    {"nome": "Vestuário", "tipo": TipoTransacao.DESPESA, "icone": "👕", "cor": "#6366F1"},
    {"nome": "Outros", "tipo": TipoTransacao.DESPESA, "icone": "💸", "cor": "#6B7280"},
    # Receitas
    {"nome": "Salário", "tipo": TipoTransacao.RECEITA, "icone": "💼", "cor": "#10B981"},
    {"nome": "Freelance", "tipo": TipoTransacao.RECEITA, "icone": "💻", "cor": "#0EA5E9"},
    {"nome": "Investimentos", "tipo": TipoTransacao.RECEITA, "icone": "📈", "cor": "#F59E0B"},
    {"nome": "Vendas", "tipo": TipoTransacao.RECEITA, "icone": "🛒", "cor": "#8B5CF6"},
    {"nome": "Aluguel", "tipo": TipoTransacao.RECEITA, "icone": "🏡", "cor": "#EC4899"},
    {"nome": "Outros", "tipo": TipoTransacao.RECEITA, "icone": "💰", "cor": "#6B7280"},
]


def criar_tabelas():
    """Cria todas as tabelas no banco de dados"""
    Base.metadata.create_all(bind=engine)
    print("[OK] Tabelas criadas com sucesso!")


def inserir_categorias_padrao():
    """Insere categorias padrão no banco"""
    db = SessionLocal()
    try:
        categorias_existentes = db.query(Categoria).filter(Categoria.padrao == True).count()

        if categorias_existentes == 0:
            for cat_data in CATEGORIAS_PADRAO:
                categoria = Categoria(**cat_data, padrao=True, usuario_id=None)
                db.add(categoria)

            db.commit()
            print(f"[OK] {len(CATEGORIAS_PADRAO)} categorias padrao inseridas!")
        else:
            print(f"[INFO] Categorias padrao ja existem ({categorias_existentes})")

    except Exception as e:
        db.rollback()
        print(f"[ERRO] Erro ao inserir categorias: {e}")
    finally:
        db.close()
