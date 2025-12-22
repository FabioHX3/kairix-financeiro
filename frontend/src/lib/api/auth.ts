import api, { setAuthToken, clearAuthToken } from './client'
import type {
  LoginRequest,
  LoginResponse,
  Usuario,
  UsuarioCriar,
  UsuarioAtualizar
} from '@/types/models'

// Login
export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>('/api/auth/login', data)
  setAuthToken(response.data.access_token)
  return response.data
}

// Register
export async function register(data: UsuarioCriar): Promise<Usuario> {
  const response = await api.post<Usuario>('/api/auth/cadastro', data)
  return response.data
}

// Get current user
export async function getMe(): Promise<Usuario> {
  const response = await api.get<Usuario>('/api/auth/me')
  return response.data
}

// Update current user
export async function updateMe(data: UsuarioAtualizar): Promise<Usuario> {
  const response = await api.put<Usuario>('/api/auth/me', data)
  return response.data
}

// Change password
export async function changePassword(senhaAtual: string, senhaNova: string): Promise<void> {
  await api.put('/api/auth/alterar-senha', {
    senha_atual: senhaAtual,
    senha_nova: senhaNova,
  })
}

// Logout
export function logout(): void {
  clearAuthToken()
  if (typeof window !== 'undefined') {
    window.location.href = '/login'
  }
}
