'use client'

import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { StatsCards } from '@/components/dashboard/stats-cards'
import { PeriodSelector } from '@/components/dashboard/period-selector'
import { CategoryChart } from '@/components/dashboard/category-chart'
import { EvolutionChart } from '@/components/dashboard/evolution-chart'
import { RecentTransactions } from '@/components/dashboard/recent-transactions'
import { useDashboard } from '@/hooks/use-dashboard'
import { useUIStore } from '@/stores/ui-store'
import { formatMonth } from '@/lib/utils/date'

export default function DashboardPage() {
  const { selectedMonth, selectedYear, setTransactionModalOpen } = useUIStore()
  const { data, isLoading } = useDashboard()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Visão geral de {formatMonth(selectedMonth, selectedYear)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <PeriodSelector />
          <Button onClick={() => setTransactionModalOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Nova transação
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <StatsCards data={data?.resumo_geral} isLoading={isLoading} />

      {/* Charts Row */}
      <div className="grid gap-6 md:grid-cols-2">
        <CategoryChart
          title="Receitas por Categoria"
          data={data?.receitas_por_categoria}
          isLoading={isLoading}
          type="receita"
        />
        <CategoryChart
          title="Despesas por Categoria"
          data={data?.despesas_por_categoria}
          isLoading={isLoading}
          type="despesa"
        />
      </div>

      {/* Evolution Chart & Recent Transactions */}
      <div className="grid gap-6 lg:grid-cols-2">
        <EvolutionChart data={data?.evolucao_mensal} isLoading={isLoading} />
        <RecentTransactions data={data?.ultimas_transacoes} isLoading={isLoading} />
      </div>
    </div>
  )
}
