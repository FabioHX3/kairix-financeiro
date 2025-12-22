import api from './client'
import type { DashboardData } from '@/types/models'

export async function getDashboard(mes?: number, ano?: number): Promise<DashboardData> {
  const params = new URLSearchParams()

  if (mes) params.append('mes', mes.toString())
  if (ano) params.append('ano', ano.toString())

  const queryString = params.toString()
  const url = queryString ? `/api/dashboard?${queryString}` : '/api/dashboard'

  const response = await api.get<DashboardData>(url)
  return response.data
}
