
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Categoria, TipoTransacao, Usuario
from backend.schemas import CategoriaAtualizar, CategoriaCriar, CategoriaResposta

router = APIRouter(prefix="/api/categorias", tags=["Categorias"])


@router.get("", response_model=list[CategoriaResposta])
async def listar_categorias(
    tipo: TipoTransacao = None,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Lista categorias (padrão + do usuário)"""

    query = db.query(Categoria).filter(
        (Categoria.padrao.is_(True)) | (Categoria.usuario_id == usuario_atual.id)
    )

    if tipo:
        query = query.filter(Categoria.tipo == tipo)

    categorias = query.order_by(Categoria.padrao.desc(), Categoria.nome).all()

    return categorias


@router.post("", response_model=CategoriaResposta, status_code=status.HTTP_201_CREATED)
async def criar_categoria(
    categoria: CategoriaCriar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Cria uma nova categoria personalizada"""

    categoria_existente = db.query(Categoria).filter(
        Categoria.usuario_id == usuario_atual.id,
        Categoria.nome == categoria.nome,
        Categoria.tipo == categoria.tipo
    ).first()

    if categoria_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Categoria '{categoria.nome}' já existe para {categoria.tipo}"
        )

    nova_categoria = Categoria(
        usuario_id=usuario_atual.id,
        **categoria.model_dump(),
        padrao=False
    )

    db.add(nova_categoria)
    db.commit()
    db.refresh(nova_categoria)

    return nova_categoria


@router.put("/{categoria_id}", response_model=CategoriaResposta)
async def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaAtualizar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Atualiza uma categoria personalizada"""

    categoria = db.query(Categoria).filter(
        Categoria.id == categoria_id,
        Categoria.usuario_id == usuario_atual.id
    ).first()

    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada ou não pertence ao usuário"
        )

    if categoria.padrao:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é possível editar categorias padrão"
        )

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)

    return categoria


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_categoria(
    categoria_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Deleta uma categoria personalizada"""

    categoria = db.query(Categoria).filter(
        Categoria.id == categoria_id,
        Categoria.usuario_id == usuario_atual.id
    ).first()

    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada ou não pertence ao usuário"
        )

    if categoria.padrao:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é possível deletar categorias padrão"
        )

    db.delete(categoria)
    db.commit()

    return None
