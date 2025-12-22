'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as categoriesApi from '@/lib/api/categories'
import type { CategoriaCriar, CategoriaAtualizar, TipoTransacao } from '@/types/models'

// Query keys
export const categoryKeys = {
  all: ['categories'] as const,
  list: (tipo?: TipoTransacao) => [...categoryKeys.all, 'list', tipo] as const,
}

// Hook for listing categories
export function useCategories(tipo?: TipoTransacao) {
  return useQuery({
    queryKey: categoryKeys.list(tipo),
    queryFn: () => categoriesApi.getCategories(tipo),
    staleTime: 10 * 60 * 1000, // 10 minutes
  })
}

// Hook for creating category
export function useCreateCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CategoriaCriar) => categoriesApi.createCategory(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: categoryKeys.all })
      toast.success('Categoria criada com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao criar categoria')
    },
  })
}

// Hook for updating category
export function useUpdateCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CategoriaAtualizar }) =>
      categoriesApi.updateCategory(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: categoryKeys.all })
      toast.success('Categoria atualizada com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao atualizar categoria')
    },
  })
}

// Hook for deleting category
export function useDeleteCategory() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => categoriesApi.deleteCategory(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: categoryKeys.all })
      toast.success('Categoria excluída com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao excluir categoria')
    },
  })
}
