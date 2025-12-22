'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as recurrencesApi from '@/lib/api/recurrences'
import type { RecurringTransactionCriar } from '@/types/models'

// Query keys
export const recurrenceKeys = {
  all: ['recurrences'] as const,
  forecast: ['recurrences', 'forecast'] as const,
  summary: ['recurrences', 'summary'] as const,
}

// Hook for listing recurrences
export function useRecurrences(apenasAtivas = true) {
  return useQuery({
    queryKey: [...recurrenceKeys.all, apenasAtivas],
    queryFn: () => recurrencesApi.getRecurrences(apenasAtivas),
  })
}

// Hook for forecast
export function useForecast() {
  return useQuery({
    queryKey: recurrenceKeys.forecast,
    queryFn: () => recurrencesApi.getForecast(),
  })
}

// Hook for summary
export function useRecurrenceSummary() {
  return useQuery({
    queryKey: recurrenceKeys.summary,
    queryFn: () => recurrencesApi.getRecurrenceSummary(),
  })
}

// Hook for creating recurrence
export function useCreateRecurrence() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: RecurringTransactionCriar) => recurrencesApi.createRecurrence(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: recurrenceKeys.all })
      toast.success('Recorrência criada com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao criar recorrência')
    },
  })
}

// Hook for deleting recurrence
export function useDeleteRecurrence() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => recurrencesApi.deleteRecurrence(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: recurrenceKeys.all })
      toast.success('Recorrência excluída com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao excluir recorrência')
    },
  })
}

// Hook for detecting recurrences
export function useDetectRecurrences() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => recurrencesApi.detectAndSaveRecurrences(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: recurrenceKeys.all })
      toast.success(`${data.length} recorrências detectadas e salvas!`)
    },
    onError: () => {
      toast.error('Erro ao detectar recorrências')
    },
  })
}
