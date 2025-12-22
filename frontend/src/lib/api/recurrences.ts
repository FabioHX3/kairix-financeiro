import api from './client'
import type {
  RecurringTransaction,
  RecurringTransactionCriar
} from '@/types/models'

// List recurrences
export async function getRecurrences(apenasAtivas = true): Promise<RecurringTransaction[]> {
  const params = `?apenas_ativas=${apenasAtivas}`
  const response = await api.get<RecurringTransaction[]>(`/api/recorrencias${params}`)
  return response.data
}

// Create recurrence
export async function createRecurrence(data: RecurringTransactionCriar): Promise<RecurringTransaction> {
  const response = await api.post<RecurringTransaction>('/api/recorrencias', data)
  return response.data
}

// Update recurrence
export async function updateRecurrence(id: number, data: Partial<RecurringTransactionCriar>): Promise<RecurringTransaction> {
  const response = await api.put<RecurringTransaction>(`/api/recorrencias/${id}`, data)
  return response.data
}

// Delete recurrence
export async function deleteRecurrence(id: number): Promise<void> {
  await api.delete(`/api/recorrencias/${id}`)
}

// Detect recurrences
export async function detectRecurrences(): Promise<RecurringTransaction[]> {
  const response = await api.post<RecurringTransaction[]>('/api/recorrencias/detectar')
  return response.data
}

// Detect and save recurrences
export async function detectAndSaveRecurrences(): Promise<RecurringTransaction[]> {
  const response = await api.post<RecurringTransaction[]>('/api/recorrencias/detectar/salvar')
  return response.data
}

// Get forecast
export async function getForecast(): Promise<any> {
  const response = await api.get('/api/recorrencias/previsao')
  return response.data
}

// Get summary
export async function getRecurrenceSummary(): Promise<any> {
  const response = await api.get('/api/recorrencias/resumo')
  return response.data
}

// Get balance
export async function getRecurrenceBalance(): Promise<any> {
  const response = await api.get('/api/recorrencias/saldo')
  return response.data
}
