'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as alertsApi from '@/lib/api/alerts'

// Query keys
export const alertsKeys = {
  all: ['alerts'] as const,
  billsDue: (dias?: number) => [...alertsKeys.all, 'bills-due', dias] as const,
  overdueBills: () => [...alertsKeys.all, 'overdue-bills'] as const,
  anomalies: (percentual?: number) => [...alertsKeys.all, 'anomalies', percentual] as const,
  dailySummary: () => [...alertsKeys.all, 'summary', 'daily'] as const,
  weeklySummary: () => [...alertsKeys.all, 'summary', 'weekly'] as const,
  monthlySummary: () => [...alertsKeys.all, 'summary', 'monthly'] as const,
}

// Get bills due soon
export function useBillsDue(dias = 7) {
  return useQuery({
    queryKey: alertsKeys.billsDue(dias),
    queryFn: () => alertsApi.getBillsDue(dias),
  })
}

// Get overdue bills
export function useOverdueBills() {
  return useQuery({
    queryKey: alertsKeys.overdueBills(),
    queryFn: alertsApi.getOverdueBills,
  })
}

// Get spending anomalies
export function useAnomalies(percentual = 0.30) {
  return useQuery({
    queryKey: alertsKeys.anomalies(percentual),
    queryFn: () => alertsApi.getAnomalies(percentual),
  })
}

// Get daily summary
export function useDailySummary() {
  return useQuery({
    queryKey: alertsKeys.dailySummary(),
    queryFn: alertsApi.getDailySummary,
  })
}

// Get weekly summary
export function useWeeklySummary() {
  return useQuery({
    queryKey: alertsKeys.weeklySummary(),
    queryFn: alertsApi.getWeeklySummary,
  })
}

// Get monthly summary
export function useMonthlySummary() {
  return useQuery({
    queryKey: alertsKeys.monthlySummary(),
    queryFn: alertsApi.getMonthlySummary,
  })
}

// Execute verification
export function useExecuteVerification() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: alertsApi.executeVerification,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertsKeys.all })
      toast.success('Verificação executada com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao executar verificação')
    },
  })
}
