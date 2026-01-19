
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import MembroFamilia, Usuario
from backend.schemas import MembroFamiliaAtualizar, MembroFamiliaCriar, MembroFamiliaResposta

router = APIRouter(prefix="/api/familia", tags=["Família"])


@router.post("", response_model=MembroFamiliaResposta, status_code=status.HTTP_201_CREATED)
async def criar_membro(
    membro: MembroFamiliaCriar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Adiciona um membro à família"""

    whatsapp_limpo = ''.join(filter(str.isdigit, membro.whatsapp))

    membro_existente = db.query(MembroFamilia).filter(
        MembroFamilia.usuario_id == usuario_atual.id,
        MembroFamilia.whatsapp == whatsapp_limpo,
        MembroFamilia.ativo.is_(True)
    ).first()

    if membro_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este whatsapp já está cadastrado na sua família"
        )

    novo_membro = MembroFamilia(
        usuario_id=usuario_atual.id,
        nome=membro.nome,
        whatsapp=whatsapp_limpo
    )

    db.add(novo_membro)
    db.commit()
    db.refresh(novo_membro)

    return novo_membro


@router.get("", response_model=list[MembroFamiliaResposta])
async def listar_membros(
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Lista todos os membros da família do usuário"""

    membros = db.query(MembroFamilia).filter(
        MembroFamilia.usuario_id == usuario_atual.id,
        MembroFamilia.ativo.is_(True)
    ).all()

    return membros


@router.get("/{membro_id}", response_model=MembroFamiliaResposta)
async def obter_membro(
    membro_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Obtém informações de um membro específico"""

    membro = db.query(MembroFamilia).filter(
        MembroFamilia.id == membro_id,
        MembroFamilia.usuario_id == usuario_atual.id
    ).first()

    if not membro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado"
        )

    return membro


@router.put("/{membro_id}", response_model=MembroFamiliaResposta)
async def atualizar_membro(
    membro_id: int,
    dados: MembroFamiliaAtualizar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Atualiza informações de um membro"""

    membro = db.query(MembroFamilia).filter(
        MembroFamilia.id == membro_id,
        MembroFamilia.usuario_id == usuario_atual.id
    ).first()

    if not membro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado"
        )

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if campo == 'whatsapp' and valor:
            valor = ''.join(filter(str.isdigit, valor))
        setattr(membro, campo, valor)

    db.commit()
    db.refresh(membro)

    return membro


@router.delete("/{membro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_membro(
    membro_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Remove um membro da família (soft delete)"""

    membro = db.query(MembroFamilia).filter(
        MembroFamilia.id == membro_id,
        MembroFamilia.usuario_id == usuario_atual.id
    ).first()

    if not membro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membro não encontrado"
        )

    membro.ativo = False
    db.commit()

    return None
