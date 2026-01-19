"""
Módulo de segurança - Autenticação e autorização.

Implementa:
- Hash de senhas com bcrypt
- JWT access tokens (curta duração)
- Refresh tokens (longa duração, armazenados no DB)
- Token blacklist via Redis
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import redis
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.database import get_db

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Redis connection for token blacklist
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Obtém conexão Redis (lazy initialization)."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            _redis_client.ping()
        except redis.ConnectionError:
            logger.warning("Redis não disponível - blacklist desabilitada")
            return None
    return _redis_client


# =============================================================================
# Password Hashing
# =============================================================================


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se a senha está correta."""
    return bcrypt.checkpw(senha_plana.encode("utf-8"), senha_hash.encode("utf-8"))


def gerar_hash_senha(senha: str) -> str:
    """Gera hash da senha com bcrypt (cost factor 12)."""
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


# =============================================================================
# JWT Access Tokens
# =============================================================================


def criar_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Cria um token JWT de acesso.

    Args:
        data: Dados a incluir no token (sub, etc)
        expires_delta: Tempo de expiração customizado

    Returns:
        Token JWT codificado
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.now(UTC),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decodificar_token(token: str) -> dict | None:
    """Decodifica e valida um token JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


# =============================================================================
# Refresh Tokens
# =============================================================================


def gerar_refresh_token() -> str:
    """Gera um refresh token aleatório seguro."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Gera hash do refresh token para armazenamento seguro."""
    return hashlib.sha256(token.encode()).hexdigest()


def criar_refresh_token_db(
    db: Session,
    usuario_id: int,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    """
    Cria e armazena um novo refresh token no banco de dados.

    Args:
        db: Sessão do banco de dados
        usuario_id: ID do usuário
        user_agent: User-Agent do navegador (opcional)
        ip_address: IP do cliente (opcional)

    Returns:
        Refresh token em texto plano (enviar ao cliente)
    """
    from backend.models import RefreshToken

    token = gerar_refresh_token()
    token_hash = hash_refresh_token(token)

    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_token = RefreshToken(
        usuario_id=usuario_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    db.add(refresh_token)
    db.commit()

    return token


def validar_refresh_token(db: Session, token: str):
    """
    Valida um refresh token e retorna o registro do banco.

    Args:
        db: Sessão do banco de dados
        token: Refresh token em texto plano

    Returns:
        Objeto RefreshToken se válido, None caso contrário
    """
    from backend.models import RefreshToken

    token_hash = hash_refresh_token(token)

    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    ).first()

    if not refresh_token:
        return None

    if not refresh_token.is_valid:
        return None

    return refresh_token


def revogar_refresh_token(db: Session, token: str) -> bool:
    """
    Revoga um refresh token específico.

    Args:
        db: Sessão do banco de dados
        token: Refresh token em texto plano

    Returns:
        True se revogado com sucesso, False caso contrário
    """
    from backend.models import RefreshToken

    token_hash = hash_refresh_token(token)

    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
    ).first()

    if not refresh_token:
        return False

    refresh_token.revoked_at = datetime.utcnow()
    db.commit()

    return True


def revogar_todos_refresh_tokens(db: Session, usuario_id: int) -> int:
    """
    Revoga todos os refresh tokens de um usuário.

    Args:
        db: Sessão do banco de dados
        usuario_id: ID do usuário

    Returns:
        Número de tokens revogados
    """
    from backend.models import RefreshToken

    result = db.query(RefreshToken).filter(
        RefreshToken.usuario_id == usuario_id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.utcnow()})

    db.commit()
    return result


# =============================================================================
# Token Blacklist (Redis)
# =============================================================================


def adicionar_token_blacklist(token: str, expires_in_seconds: int) -> bool:
    """
    Adiciona um access token à blacklist.

    Args:
        token: Token JWT a ser invalidado
        expires_in_seconds: TTL do registro (tempo restante do token)

    Returns:
        True se adicionado com sucesso
    """
    redis_client = get_redis()
    if not redis_client:
        return False

    try:
        key = f"blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
        redis_client.setex(key, expires_in_seconds, "1")
        return True
    except redis.RedisError as e:
        logger.error(f"Erro ao adicionar token à blacklist: {e}")
        return False


def verificar_token_blacklist(token: str) -> bool:
    """
    Verifica se um token está na blacklist.

    Args:
        token: Token JWT a verificar

    Returns:
        True se o token está na blacklist (inválido)
    """
    redis_client = get_redis()
    if not redis_client:
        return False

    try:
        key = f"blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
        return redis_client.exists(key) > 0
    except redis.RedisError as e:
        logger.error(f"Erro ao verificar blacklist: {e}")
        return False


# =============================================================================
# Authentication
# =============================================================================


def autenticar_usuario(db: Session, email: str, senha: str):
    """Autentica um usuário por email e senha."""
    from backend.models import Usuario

    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if not usuario:
        return False

    if not verificar_senha(senha, usuario.senha_hash):
        return False

    if not usuario.ativo:
        return False

    return usuario


async def obter_usuario_atual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """
    Obtém o usuário atual a partir do token JWT.

    Verifica:
    - Validade do token
    - Token não está na blacklist
    - Usuário existe e está ativo
    """
    from backend.models import Usuario

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Verifica blacklist
    if verificar_token_blacklist(token):
        raise credentials_exception

    # Decodifica token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type", "access")

        if email is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Busca usuário
    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if usuario is None:
        raise credentials_exception

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo",
        )

    return usuario


# =============================================================================
# Cookie Helpers
# =============================================================================


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """
    Define cookies de autenticação na resposta.

    Args:
        response: Objeto Response do FastAPI
        access_token: Token JWT de acesso
        refresh_token: Refresh token
    """
    is_production = settings.ENVIRONMENT == "production"

    # Access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_production,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Refresh token cookie (path restrito)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/auth/refresh",
    )


def clear_auth_cookies(response: Response) -> None:
    """Remove cookies de autenticação."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth/refresh")


def get_client_ip(request: Request) -> str:
    """Obtém o IP do cliente considerando proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
