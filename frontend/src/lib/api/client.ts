import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types/models'

// Create axios instance
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8014',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Required for HttpOnly cookies
  timeout: 30000,
})

// Flag to prevent multiple refresh attempts
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: unknown) => void
  reject: (reason?: unknown) => void
}> = []

const processQueue = (error: unknown = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve()
    }
  })
  failedQueue = []
}

// Request interceptor - add auth token from localStorage (backwards compatible)
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Only run on client side
    if (typeof window !== 'undefined') {
      // Check localStorage for token (backwards compatible)
      const token = localStorage.getItem('token')
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle 401 and auto-refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean
    }

    // If 401 and not already retrying
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Skip refresh for auth endpoints
      if (
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/refresh') ||
        originalRequest.url?.includes('/auth/cadastro')
      ) {
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // Queue request while refreshing
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(() => {
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // Try to refresh tokens
        const response = await api.post('/api/auth/refresh')

        // If we get a new access_token in the response, store it
        if (response.data?.access_token) {
          localStorage.setItem('token', response.data.access_token)
        }

        processQueue()
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError)
        // Clear auth state and redirect to login
        clearAuth()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

/**
 * Clear all authentication data and redirect to login
 */
export const clearAuth = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token')
    localStorage.removeItem('auth-storage')

    // Only redirect if not already on auth pages
    if (
      !window.location.pathname.startsWith('/login') &&
      !window.location.pathname.startsWith('/cadastro')
    ) {
      window.location.href = '/login'
    }
  }
}

/**
 * Set auth token (stored in localStorage for backwards compatibility)
 * The backend will also set HttpOnly cookies
 */
export const setAuthToken = (token: string) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', token)
  }
}

/**
 * Clear auth token
 */
export const clearAuthToken = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token')
  }
}

/**
 * Get auth token from localStorage
 */
export const getAuthToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('token')
  }
  return null
}

/**
 * Perform logout - clears both frontend and backend auth state
 */
export const logout = async () => {
  try {
    await api.post('/api/auth/logout')
  } catch {
    // Ignore errors during logout
  } finally {
    clearAuth()
  }
}

/**
 * Extract error message from axios error
 */
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>

    // Handle validation errors
    if (axiosError.response?.status === 422) {
      const detail = axiosError.response.data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        return detail[0].msg || 'Erro de validação'
      }
    }

    // Handle rate limit
    if (axiosError.response?.status === 429) {
      return 'Muitas tentativas. Aguarde antes de tentar novamente.'
    }

    return axiosError.response?.data?.detail || axiosError.message || 'Erro desconhecido'
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Erro desconhecido'
}

export default api
