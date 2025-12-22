'use client'

import { useQuery } from '@tanstack/react-query'
import { getDashboard } from '@/lib/api/dashboard'
import { useUIStore } from '@/stores/ui-store'

// Query keys
export const dashboardKeys = {
  all: ['dashboard'] as const,
  byPeriod: (month: number, year: number) => [...dashboardKeys.all, month, year] as const,
}

// Hook for dashboard data
export function useDashboard(month?: number, year?: number) {
  const { selectedMonth, selectedYear } = useUIStore()

  const m = month ?? selectedMonth
  const y = year ?? selectedYear

  return useQuery({
    queryKey: dashboardKeys.byPeriod(m, y),
    queryFn: () => getDashboard(m, y),
    staleTime: 2 * 60 * 1000, // 2 minutes
  })
}
