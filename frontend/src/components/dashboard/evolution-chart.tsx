'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { AreaChart } from '@tremor/react'
import { formatCurrency } from '@/lib/utils/currency'
import { parseMonthString } from '@/lib/utils/date'
import type { EvolucaoMensal } from '@/types/models'

interface EvolutionChartProps {
  data?: EvolucaoMensal[]
  isLoading?: boolean
}

export function EvolutionChart({ data, isLoading }: EvolutionChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Evolução Mensal</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[300px] w-full" />
        </CardContent>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Evolução Mensal</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[300px]">
          <p className="text-muted-foreground">Nenhum dado disponível</p>
        </CardContent>
      </Card>
    )
  }

  const chartData = data.map((item) => ({
    mes: parseMonthString(item.mes),
    Receitas: item.receitas,
    Despesas: item.despesas,
    Saldo: item.saldo,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Evolução Mensal</CardTitle>
      </CardHeader>
      <CardContent>
        <AreaChart
          data={chartData}
          index="mes"
          categories={['Receitas', 'Despesas']}
          colors={['emerald', 'rose']}
          valueFormatter={formatCurrency}
          className="h-[300px]"
          showAnimation
          showLegend
          showGridLines
          curveType="monotone"
        />
      </CardContent>
    </Card>
  )
}
