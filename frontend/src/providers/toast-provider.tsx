'use client'

import { Toaster } from '@/components/ui/sonner'

export function ToastProvider() {
  return (
    <Toaster
      position="top-right"
      toastOptions={{
        style: {
          background: '#1e1e1e',
          color: '#ffffff',
          border: '1px solid rgba(255, 255, 255, 0.1)',
        },
      }}
    />
  )
}
