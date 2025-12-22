import api from './client'
import type { ContaVencer, Anomalia } from '@/types/models'

// Get bills due soon
export async function getBillsDue(dias = 7): Promise<ContaVencer[]> {
  const response = await api.get<ContaVencer[]>(`/api/alertas/contas-vencer?dias=${dias}`)
  return response.data
}

// Get overdue bills
export async function getOverdueBills(): Promise<ContaVencer[]> {
  const response = await api.get<ContaVencer[]>('/api/alertas/contas-atrasadas')
  return response.data
}

// Get spending anomalies
export async function getAnomalies(percentual = 0.30): Promise<Anomalia[]> {
  const response = await api.get<Anomalia[]>(`/api/alertas/anomalias?percentual=${percentual}`)
  return response.data
}

// Get daily summary
export async function getDailySummary(): Promise<any> {
  const response = await api.get('/api/alertas/resumo/diario')
  return response.data
}

// Get weekly summary
export async function getWeeklySummary(): Promise<any> {
  const response = await api.get('/api/alertas/resumo/semanal')
  return response.data
}

// Get monthly summary
export async function getMonthlySummary(): Promise<any> {
  const response = await api.get('/api/alertas/resumo/mensal')
  return response.data
}

// Execute verification now
export async function executeVerification(): Promise<any> {
  const response = await api.post('/api/alertas/executar-agora')
  return response.data
}
