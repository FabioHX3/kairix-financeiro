import api from './client'
import type {
  MembroFamilia,
  MembroFamiliaCriar,
  MembroFamiliaAtualizar
} from '@/types/models'

// List family members
export async function getFamilyMembers(): Promise<MembroFamilia[]> {
  const response = await api.get<MembroFamilia[]>('/api/familia')
  return response.data
}

// Get single family member
export async function getFamilyMember(id: number): Promise<MembroFamilia> {
  const response = await api.get<MembroFamilia>(`/api/familia/${id}`)
  return response.data
}

// Create family member
export async function createFamilyMember(data: MembroFamiliaCriar): Promise<MembroFamilia> {
  const response = await api.post<MembroFamilia>('/api/familia', data)
  return response.data
}

// Update family member
export async function updateFamilyMember(id: number, data: MembroFamiliaAtualizar): Promise<MembroFamilia> {
  const response = await api.put<MembroFamilia>(`/api/familia/${id}`, data)
  return response.data
}

// Delete family member (soft delete)
export async function deleteFamilyMember(id: number): Promise<void> {
  await api.delete(`/api/familia/${id}`)
}
