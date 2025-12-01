from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.config import settings
from backend.core.database import get_db
from backend.core.security import (
    criar_access_token,
    autenticar_usuario,
    gerar_hash_senha,
    obter_usuario_atual,
    verificar_senha
)
from backend.models import Usuario
from backend.schemas import (
    UsuarioCriar, UsuarioResposta, LoginRequest, Token,
    UsuarioAtualizar, UsuarioAlterarSenha, SystemLoginRequest
)

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])


@router.post("/cadastro", response_model=UsuarioResposta, status_code=status.HTTP_201_CREATED)
def cadastrar_usuario(usuario: UsuarioCriar, db: Session = Depends(get_db)):
    """Cadastra um novo usuário"""

    usuario_existente = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado"
        )

    if usuario.whatsapp:
        whatsapp_existente = db.query(Usuario).filter(
            Usuario.whatsapp == usuario.whatsapp
        ).first()
        if whatsapp_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WhatsApp já cadastrado"
            )

    novo_usuario = Usuario(
        nome=usuario.nome,
        email=usuario.email,
        senha_hash=gerar_hash_senha(usuario.senha),
        telefone=usuario.telefone,
        whatsapp=usuario.whatsapp,
        ativo=True
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    return novo_usuario


@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Realiza login e retorna token JWT"""

    usuario = autenticar_usuario(db, login_data.email, login_data.senha)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = criar_access_token(
        data={"sub": usuario.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/system-login", response_model=Token)
def system_login(login_data: SystemLoginRequest, db: Session = Depends(get_db)):
    """Login para sistemas externos (requer API Key)"""

    if not settings.SYSTEM_API_KEY or login_data.api_key != settings.SYSTEM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = db.query(Usuario).filter(
        Usuario.email == login_data.user_email,
        Usuario.ativo == True
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado ou inativo"
        )

    access_token_expires = timedelta(hours=24)
    access_token = criar_access_token(
        data={"sub": usuario.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UsuarioResposta)
async def obter_meus_dados(usuario_atual: Usuario = Depends(obter_usuario_atual)):
    """Retorna dados do usuário logado"""
    return usuario_atual


@router.put("/me", response_model=UsuarioResposta)
async def atualizar_meus_dados(
    dados: UsuarioAtualizar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Atualiza dados do usuário logado"""

    if dados.email and dados.email != usuario_atual.email:
        email_existente = db.query(Usuario).filter(
            Usuario.email == dados.email,
            Usuario.id != usuario_atual.id
        ).first()
        if email_existente:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já cadastrado"
            )

    if dados.nome is not None:
        usuario_atual.nome = dados.nome
    if dados.email is not None:
        usuario_atual.email = dados.email
    if dados.telefone is not None:
        usuario_atual.telefone = dados.telefone
    if dados.whatsapp is not None:
        usuario_atual.whatsapp = dados.whatsapp

    db.commit()
    db.refresh(usuario_atual)

    return usuario_atual


@router.put("/alterar-senha")
async def alterar_senha(
    dados: UsuarioAlterarSenha,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Altera senha do usuário"""

    if not verificar_senha(dados.senha_atual, usuario_atual.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta"
        )

    usuario_atual.senha_hash = gerar_hash_senha(dados.senha_nova)
    db.commit()

    return {"message": "Senha alterada com sucesso"}
