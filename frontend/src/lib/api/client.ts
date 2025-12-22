import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

// Create axios instance
export const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8014',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

// Request interceptor - add auth token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Only run on client side
    if (typeof window !== 'undefined') {
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

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token')
        // Only redirect if not already on auth pages
        if (!window.location.pathname.startsWith('/login') &&
            !window.location.pathname.startsWith('/cadastro')) {
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// Helper to set token
export const setAuthToken = (token: string) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', token)
  }
}

// Helper to clear token
export const clearAuthToken = () => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token')
  }
}

// Helper to get token
export const getAuthToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('token')
  }
  return null
}

export default api
