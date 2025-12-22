'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Navbar } from '@/components/layout/navbar'
import { Sidebar } from '@/components/layout/sidebar'
import { useAuthStore } from '@/stores/auth-store'
import { useUser } from '@/hooks/use-auth'
import { Skeleton } from '@/components/ui/skeleton'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const { isAuthenticated, isLoading: storeLoading } = useAuthStore()
  const { isLoading: queryLoading, isError } = useUser()

  const isLoading = storeLoading || queryLoading

  useEffect(() => {
    if (!isLoading && (!isAuthenticated || isError)) {
      router.push('/login')
    }
  }, [isAuthenticated, isError, isLoading, router])

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="sticky top-0 z-50 w-full border-b border-border bg-card h-16 flex items-center px-4">
          <Skeleton className="h-8 w-32" />
          <div className="flex-1" />
          <Skeleton className="h-9 w-9 rounded-full" />
        </div>
        <div className="flex">
          <aside className="hidden md:block w-64 border-r border-border p-4 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </aside>
          <main className="flex-1 p-6 space-y-4">
            <Skeleton className="h-8 w-48" />
            <div className="grid gap-4 md:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          </main>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 md:ml-64 p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
