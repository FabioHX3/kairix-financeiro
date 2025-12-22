'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as preferencesApi from '@/lib/api/preferences'
import type { UserPreferencesAtualizar } from '@/types/models'

// Query keys
export const preferencesKeys = {
  all: ['preferences'] as const,
  patterns: ['patterns'] as const,
}

// Hook for getting preferences
export function usePreferences() {
  return useQuery({
    queryKey: preferencesKeys.all,
    queryFn: () => preferencesApi.getPreferences(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

// Hook for updating preferences
export function useUpdatePreferences() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: UserPreferencesAtualizar) => preferencesApi.updatePreferences(data),
    onSuccess: (data) => {
      queryClient.setQueryData(preferencesKeys.all, data)
      toast.success('Preferências atualizadas com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao atualizar preferências')
    },
  })
}

// Hook for resetting preferences
export function useResetPreferences() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => preferencesApi.resetPreferences(),
    onSuccess: (data) => {
      queryClient.setQueryData(preferencesKeys.all, data)
      toast.success('Preferências restauradas para o padrão!')
    },
    onError: () => {
      toast.error('Erro ao restaurar preferências')
    },
  })
}

// Hook for getting patterns
export function usePatterns() {
  return useQuery({
    queryKey: preferencesKeys.patterns,
    queryFn: () => preferencesApi.getPatterns(),
  })
}

// Hook for deleting pattern
export function useDeletePattern() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => preferencesApi.deletePattern(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesKeys.patterns })
      toast.success('Padrão excluído com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao excluir padrão')
    },
  })
}

// Hook for clearing all patterns
export function useClearPatterns() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => preferencesApi.clearPatterns(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: preferencesKeys.patterns })
      toast.success('Todos os padrões foram excluídos!')
    },
    onError: () => {
      toast.error('Erro ao excluir padrões')
    },
  })
}
