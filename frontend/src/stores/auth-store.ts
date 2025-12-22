import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Usuario } from '@/types/models'

interface AuthState {
  user: Usuario | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  setAuth: (user: Usuario, token: string) => void
  setUser: (user: Usuario) => void
  setLoading: (loading: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,

      setAuth: (user, token) => {
        if (typeof window !== 'undefined') {
          localStorage.setItem('token', token)
        }
        set({
          user,
          token,
          isAuthenticated: true,
          isLoading: false,
        })
      },

      setUser: (user) => {
        set({ user })
      },

      setLoading: (loading) => {
        set({ isLoading: loading })
      },

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('token')
        }
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
        })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
