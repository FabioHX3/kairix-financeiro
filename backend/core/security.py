from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.config import settings
from backend.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    """Verifica se a senha está correta"""
    return pwd_context.verify(senha_plana, senha_hash)


def gerar_hash_senha(senha: str) -> str:
    """Gera hash da senha"""
    return pwd_context.hash(senha)


def criar_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def autenticar_usuario(db: Session, email: str, senha: str):
    """Autentica um usuário"""
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
    db: Session = Depends(get_db)
):
    """Obtém o usuário atual a partir do token"""
    from backend.models import Usuario

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if usuario is None:
        raise credentials_exception

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo"
        )

    return usuario
