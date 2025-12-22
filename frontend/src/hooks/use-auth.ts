'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { useAuthStore } from '@/stores/auth-store'
import * as authApi from '@/lib/api/auth'
import { setAuthToken, clearAuthToken, getErrorMessage } from '@/lib/api/client'
import type { LoginRequest, UsuarioCriar, UsuarioAtualizar } from '@/types/models'

// Query keys
export const authKeys = {
  user: ['user'] as const,
}

// Hook for getting current user
export function useUser() {
  const { setUser, setLoading, logout } = useAuthStore()

  return useQuery({
    queryKey: authKeys.user,
    queryFn: async () => {
      try {
        const user = await authApi.getMe()
        setUser(user)
        setLoading(false)
        return user
      } catch {
        logout()
        throw new Error('Failed to fetch user')
      }
    },
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

// Hook for login
export function useLogin() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { setAuth } = useAuthStore()

  return useMutation({
    mutationFn: (data: LoginRequest) => authApi.login(data),
    onSuccess: async (response) => {
      // Fetch user data after login
      const user = await authApi.getMe()
      setAuth(user, response.access_token)

      // Set token with secure cookie
      setAuthToken(response.access_token)

      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: authKeys.user })

      toast.success('Login realizado com sucesso!')
      router.push('/')
    },
    onError: (error: unknown) => {
      const message = getErrorMessage(error)
      toast.error(message === 'Erro desconhecido' ? 'Email ou senha inválidos' : message)
    },
  })
}

// Hook for register
export function useRegister() {
  const router = useRouter()

  return useMutation({
    mutationFn: (data: UsuarioCriar) => authApi.register(data),
    onSuccess: () => {
      toast.success('Conta criada com sucesso! Faça login para continuar.')
      router.push('/login')
    },
    onError: (error: unknown) => {
      const message = getErrorMessage(error)
      toast.error(message === 'Erro desconhecido' ? 'Erro ao criar conta' : message)
    },
  })
}

// Hook for updating profile
export function useUpdateProfile() {
  const queryClient = useQueryClient()
  const { setUser } = useAuthStore()

  return useMutation({
    mutationFn: (data: UsuarioAtualizar) => authApi.updateMe(data),
    onSuccess: (user) => {
      setUser(user)
      queryClient.setQueryData(authKeys.user, user)
      toast.success('Perfil atualizado com sucesso!')
    },
    onError: (error: unknown) => {
      const message = getErrorMessage(error)
      toast.error(message === 'Erro desconhecido' ? 'Erro ao atualizar perfil' : message)
    },
  })
}

// Hook for changing password
export function useChangePassword() {
  return useMutation({
    mutationFn: ({ senhaAtual, senhaNova }: { senhaAtual: string; senhaNova: string }) =>
      authApi.changePassword(senhaAtual, senhaNova),
    onSuccess: () => {
      toast.success('Senha alterada com sucesso!')
    },
    onError: (error: unknown) => {
      const message = getErrorMessage(error)
      toast.error(message === 'Erro desconhecido' ? 'Erro ao alterar senha. Verifique a senha atual.' : message)
    },
  })
}

// Hook for logout
export function useLogout() {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { logout } = useAuthStore()

  return () => {
    // Clear token and cookie
    clearAuthToken()

    // Clear store
    logout()

    // Clear queries
    queryClient.clear()

    // Redirect
    router.push('/login')
  }
}
