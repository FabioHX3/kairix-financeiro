import api from './client'
import type {
  Transacao,
  TransacaoCriar,
  TransacaoAtualizar,
  TransacaoFiltros,
  ResumoPeriodo
} from '@/types/models'

// List transactions
export async function getTransactions(filtros?: TransacaoFiltros): Promise<Transacao[]> {
  const params = new URLSearchParams()

  if (filtros?.tipo) params.append('tipo', filtros.tipo)
  if (filtros?.categoria_id) params.append('categoria_id', filtros.categoria_id.toString())
  if (filtros?.data_inicio) params.append('data_inicio', filtros.data_inicio)
  if (filtros?.data_fim) params.append('data_fim', filtros.data_fim)
  if (filtros?.skip) params.append('skip', filtros.skip.toString())
  if (filtros?.limit) params.append('limit', filtros.limit.toString())

  const queryString = params.toString()
  const url = queryString ? `/api/transacoes?${queryString}` : '/api/transacoes'

  const response = await api.get<Transacao[]>(url)
  return response.data
}

// Get single transaction
export async function getTransaction(id: number): Promise<Transacao> {
  const response = await api.get<Transacao>(`/api/transacoes/${id}`)
  return response.data
}

// Create transaction
export async function createTransaction(data: TransacaoCriar): Promise<Transacao> {
  const response = await api.post<Transacao>('/api/transacoes', data)
  return response.data
}

// Update transaction
export async function updateTransaction(id: number, data: TransacaoAtualizar): Promise<Transacao> {
  const response = await api.put<Transacao>(`/api/transacoes/${id}`, data)
  return response.data
}

// Delete transaction
export async function deleteTransaction(id: number): Promise<void> {
  await api.delete(`/api/transacoes/${id}`)
}

// Get period summary
export async function getPeriodSummary(dataInicio?: string, dataFim?: string): Promise<ResumoPeriodo> {
  const params = new URLSearchParams()

  if (dataInicio) params.append('data_inicio', dataInicio)
  if (dataFim) params.append('data_fim', dataFim)

  const queryString = params.toString()
  const url = queryString ? `/api/transacoes/resumo/periodo?${queryString}` : '/api/transacoes/resumo/periodo'

  const response = await api.get<ResumoPeriodo>(url)
  return response.data
}
