import api from './client'
import type {
  Categoria,
  CategoriaCriar,
  CategoriaAtualizar,
  TipoTransacao
} from '@/types/models'

// List categories
export async function getCategories(tipo?: TipoTransacao): Promise<Categoria[]> {
  const params = tipo ? `?tipo=${tipo}` : ''
  const response = await api.get<Categoria[]>(`/api/categorias${params}`)
  return response.data
}

// Create category
export async function createCategory(data: CategoriaCriar): Promise<Categoria> {
  const response = await api.post<Categoria>('/api/categorias', data)
  return response.data
}

// Update category
export async function updateCategory(id: number, data: CategoriaAtualizar): Promise<Categoria> {
  const response = await api.put<Categoria>(`/api/categorias/${id}`, data)
  return response.data
}

// Delete category
export async function deleteCategory(id: number): Promise<void> {
  await api.delete(`/api/categorias/${id}`)
}
