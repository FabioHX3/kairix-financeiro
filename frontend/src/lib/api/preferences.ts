import api from './client'
import type {
  UserPreferences,
  UserPreferencesAtualizar,
  UserPattern
} from '@/types/models'

// Get preferences
export async function getPreferences(): Promise<UserPreferences> {
  const response = await api.get<UserPreferences>('/api/preferencias')
  return response.data
}

// Update preferences
export async function updatePreferences(data: UserPreferencesAtualizar): Promise<UserPreferences> {
  const response = await api.put<UserPreferences>('/api/preferencias', data)
  return response.data
}

// Reset preferences to defaults
export async function resetPreferences(): Promise<UserPreferences> {
  const response = await api.post<UserPreferences>('/api/preferencias/reset')
  return response.data
}

// Get learned patterns
export async function getPatterns(): Promise<UserPattern[]> {
  const response = await api.get<UserPattern[]>('/api/preferencias/padroes')
  return response.data
}

// Delete pattern
export async function deletePattern(id: number): Promise<void> {
  await api.delete(`/api/preferencias/padroes/${id}`)
}

// Clear all patterns
export async function clearPatterns(): Promise<void> {
  await api.delete('/api/preferencias/padroes')
}
