'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as transactionsApi from '@/lib/api/transactions'
import { dashboardKeys } from './use-dashboard'
import type { TransacaoCriar, TransacaoAtualizar, TransacaoFiltros } from '@/types/models'

// Query keys
export const transactionKeys = {
  all: ['transactions'] as const,
  list: (filters?: TransacaoFiltros) => [...transactionKeys.all, 'list', filters] as const,
  detail: (id: number) => [...transactionKeys.all, 'detail', id] as const,
}

// Hook for listing transactions
export function useTransactions(filters?: TransacaoFiltros) {
  return useQuery({
    queryKey: transactionKeys.list(filters),
    queryFn: () => transactionsApi.getTransactions(filters),
  })
}

// Hook for single transaction
export function useTransaction(id: number) {
  return useQuery({
    queryKey: transactionKeys.detail(id),
    queryFn: () => transactionsApi.getTransaction(id),
    enabled: !!id,
  })
}

// Hook for creating transaction
export function useCreateTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: TransacaoCriar) => transactionsApi.createTransaction(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: transactionKeys.all })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
      toast.success('Transação criada com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao criar transação')
    },
  })
}

// Hook for updating transaction
export function useUpdateTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TransacaoAtualizar }) =>
      transactionsApi.updateTransaction(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: transactionKeys.all })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
      toast.success('Transação atualizada com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao atualizar transação')
    },
  })
}

// Hook for deleting transaction
export function useDeleteTransaction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => transactionsApi.deleteTransaction(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: transactionKeys.all })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
      toast.success('Transação excluída com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao excluir transação')
    },
  })
}
