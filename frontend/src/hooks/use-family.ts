'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as familyApi from '@/lib/api/family'
import type { MembroFamiliaCriar, MembroFamiliaAtualizar } from '@/types/models'

// Query keys
export const familyKeys = {
  all: ['family'] as const,
}

// Hook for listing family members
export function useFamilyMembers() {
  return useQuery({
    queryKey: familyKeys.all,
    queryFn: () => familyApi.getFamilyMembers(),
  })
}

// Hook for creating family member
export function useCreateFamilyMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: MembroFamiliaCriar) => familyApi.createFamilyMember(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: familyKeys.all })
      toast.success('Membro adicionado com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao adicionar membro')
    },
  })
}

// Hook for updating family member
export function useUpdateFamilyMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: MembroFamiliaAtualizar }) =>
      familyApi.updateFamilyMember(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: familyKeys.all })
      toast.success('Membro atualizado com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao atualizar membro')
    },
  })
}

// Hook for deleting family member
export function useDeleteFamilyMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => familyApi.deleteFamilyMember(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: familyKeys.all })
      toast.success('Membro removido com sucesso!')
    },
    onError: () => {
      toast.error('Erro ao remover membro')
    },
  })
}
