"""
Rotas de autenticação - Login, cadastro, refresh e logout.
"""

from datetime import UTC, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.database import get_db
from backend.core.security import (
    adicionar_token_blacklist,
    autenticar_usuario,
    clear_auth_cookies,
    criar_access_token,
    criar_refresh_token_db,
    decodificar_token,
    gerar_hash_senha,
    get_client_ip,
    obter_usuario_atual,
    revogar_refresh_token,
    revogar_todos_refresh_tokens,
    set_auth_cookies,
    validar_refresh_token,
    verificar_senha,
)
from backend.models import Usuario
from backend.schemas import (
    LoginRequest,
    SystemLoginRequest,
    Token,
    UsuarioAlterarSenha,
    UsuarioAtualizar,
    UsuarioCriar,
    UsuarioResposta,
)

# Rate limiter específico para auth
limiter = Limiter(key_func=get_remote_address)


# ==================== Schemas ====================


class ErrorDetail(BaseModel):
    """Detalhe de erro de validação."""

    loc: list[str] = Field(..., description="Localização do erro (campo)")
    msg: str = Field(..., description="Mensagem de erro")
    type: str = Field(..., description="Tipo do erro")


class ValidationErrorResponse(BaseModel):
    """Resposta de erro de validação (422)."""

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "email"],
                        "msg": "value is not a valid email address",
                        "type": "value_error.email",
                    }
                ]
            }
        }
    }

    detail: list[ErrorDetail] = Field(..., description="Lista de erros de validação")


class HTTPErrorResponse(BaseModel):
    """Resposta de erro HTTP padrão."""

    model_config = {"json_schema_extra": {"example": {"detail": "Email já cadastrado"}}}

    detail: str = Field(..., description="Mensagem de erro")


class TokenResponse(BaseModel):
    """Resposta de autenticação com tokens."""

    access_token: str = Field(..., description="Token JWT de acesso")
    token_type: str = Field(default="bearer", description="Tipo do token")
    expires_in: int = Field(..., description="Tempo de expiração em segundos")


class MessageResponse(BaseModel):
    """Resposta simples com mensagem."""

    message: str


router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


# ==================== Cadastro ====================


@router.post(
    "/cadastro",
    response_model=UsuarioResposta,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar novo usuário",
    responses={
        201: {"description": "Usuário cadastrado com sucesso", "model": UsuarioResposta},
        400: {
            "description": "Dados inválidos ou usuário já existe",
            "model": HTTPErrorResponse,
        },
        422: {"description": "Erro de validação dos dados", "model": ValidationErrorResponse},
        429: {"description": "Muitas tentativas", "model": HTTPErrorResponse},
    },
)
@limiter.limit("3/hour")
def cadastrar_usuario(
    request: Request,
    usuario: UsuarioCriar,
    db: Session = Depends(get_db),
):
    """
    Cadastra um novo usuário no sistema.

    **Rate limit:** 3 cadastros por hora por IP.

    ## Campos obrigatórios
    - **nome**: Nome completo (2-100 caracteres)
    - **email**: Email válido (será usado para login)
    - **senha**: Senha com mínimo 8 caracteres, letras maiúsculas/minúsculas e números

    ## Campos opcionais
    - **whatsapp**: WhatsApp com DDD (necessário para usar o bot)
    """
    # Verifica email duplicado
    usuario_existente = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado",
        )

    # Verifica WhatsApp duplicado
    if usuario.whatsapp:
        whatsapp_existente = (
            db.query(Usuario).filter(Usuario.whatsapp == usuario.whatsapp).first()
        )
        if whatsapp_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WhatsApp já cadastrado",
            )

    # Cria o usuário
    novo_usuario = Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha_hash=gerar_hash_senha(usuario.senha),
        whatsapp=usuario.whatsapp,
        ativo=True,
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario


# ==================== Login ====================


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Realizar login",
    responses={
        200: {"description": "Login bem-sucedido", "model": TokenResponse},
        401: {"description": "Credenciais inválidas", "model": HTTPErrorResponse},
        429: {"description": "Muitas tentativas", "model": HTTPErrorResponse},
    },
)
@limiter.limit("5/15minutes")
def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Realiza login e retorna tokens de autenticação.

    **Rate limit:** 5 tentativas a cada 15 minutos por IP.

    Retorna:
    - `access_token`: Token JWT de curta duração (15 min)
    - Cookies HttpOnly com access e refresh tokens
    """
    usuario = autenticar_usuario(db, login_data.email, login_data.senha)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cria access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = criar_access_token(
        data={"sub": usuario.email},
        expires_delta=access_token_expires,
    )

    # Cria refresh token
    user_agent = request.headers.get("User-Agent")
    ip_address = get_client_ip(request)
    refresh_token = criar_refresh_token_db(
        db=db,
        usuario_id=usuario.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Define cookies HttpOnly
    set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ==================== Refresh ====================


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar tokens",
    responses={
        200: {"description": "Tokens renovados", "model": TokenResponse},
        401: {"description": "Refresh token inválido", "model": HTTPErrorResponse},
    },
)
def refresh_tokens(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(None),
):
    """
    Renova os tokens de autenticação usando o refresh token.

    O refresh token deve ser enviado via cookie HttpOnly.
    """
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token não fornecido",
        )

    # Valida refresh token
    token_db = validar_refresh_token(db, refresh_token)
    if not token_db:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado",
        )

    # Busca usuário
    usuario = db.query(Usuario).filter(Usuario.id == token_db.usuario_id).first()
    if not usuario or not usuario.ativo:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo",
        )

    # Revoga o refresh token atual (rotation)
    revogar_refresh_token(db, refresh_token)

    # Cria novos tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = criar_access_token(
        data={"sub": usuario.email},
        expires_delta=access_token_expires,
    )

    user_agent = request.headers.get("User-Agent")
    ip_address = get_client_ip(request)
    new_refresh_token = criar_refresh_token_db(
        db=db,
        usuario_id=usuario.id,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Define novos cookies
    set_auth_cookies(response, new_access_token, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ==================== Logout ====================


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Realizar logout",
    responses={
        200: {"description": "Logout realizado", "model": MessageResponse},
    },
)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
):
    """
    Realiza logout do usuário.

    - Revoga o refresh token atual
    - Adiciona o access token à blacklist
    - Remove os cookies de autenticação
    """
    # Revoga refresh token
    if refresh_token:
        revogar_refresh_token(db, refresh_token)

    # Adiciona access token à blacklist
    if access_token:
        payload = decodificar_token(access_token)
        if payload and "exp" in payload:
            from datetime import datetime

            exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
            now = datetime.now(UTC)
            remaining_seconds = int((exp - now).total_seconds())
            if remaining_seconds > 0:
                adicionar_token_blacklist(access_token, remaining_seconds)

    # Remove cookies
    clear_auth_cookies(response)

    return MessageResponse(message="Logout realizado com sucesso")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Logout de todas as sessões",
    responses={
        200: {"description": "Todas as sessões encerradas", "model": MessageResponse},
    },
)
async def logout_all(
    response: Response,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """
    Encerra todas as sessões do usuário.

    Revoga todos os refresh tokens associados ao usuário.
    """
    count = revogar_todos_refresh_tokens(db, usuario_atual.id)
    clear_auth_cookies(response)

    return MessageResponse(message=f"{count} sessões encerradas")


# ==================== System Login ====================


@router.post("/system-login", response_model=Token, include_in_schema=False)
def system_login(login_data: SystemLoginRequest, db: Session = Depends(get_db)):
    """Login para sistemas externos (requer API Key)."""
    if not settings.SYSTEM_API_KEY or login_data.api_key != settings.SYSTEM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.email == login_data.user_email, Usuario.ativo.is_(True))
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado ou inativo",
        )

    access_token_expires = timedelta(hours=24)
    access_token = criar_access_token(
        data={"sub": usuario.email},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ==================== User Profile ====================


@router.get("/me", response_model=UsuarioResposta, summary="Obter dados do usuário")
async def obter_meus_dados(usuario_atual: Usuario = Depends(obter_usuario_atual)):
    """Retorna dados do usuário logado."""
    return usuario_atual


@router.put("/me", response_model=UsuarioResposta, summary="Atualizar dados do usuário")
async def atualizar_meus_dados(
    dados: UsuarioAtualizar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Atualiza dados do usuário logado."""
    if dados.email and dados.email != usuario_atual.email:
        email_existente = (
            db.query(Usuario)
            .filter(Usuario.email == dados.email, Usuario.id != usuario_atual.id)
            .first()
        )
        if email_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado",
            )

    if dados.nome is not None:
        usuario_atual.nome = dados.nome
    if dados.email is not None:
        usuario_atual.email = dados.email
    if dados.whatsapp is not None:
        usuario_atual.whatsapp = dados.whatsapp

    db.commit()
    db.refresh(usuario_atual)

    return usuario_atual


@router.put("/alterar-senha", response_model=MessageResponse, summary="Alterar senha")
async def alterar_senha(
    dados: UsuarioAlterarSenha,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Altera senha do usuário."""
    if not verificar_senha(dados.senha_atual, usuario_atual.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta",
        )

    usuario_atual.senha_hash = gerar_hash_senha(dados.senha_nova)
    db.commit()

    return MessageResponse(message="Senha alterada com sucesso")
