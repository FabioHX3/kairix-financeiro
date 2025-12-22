'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { DonutChart } from '@tremor/react'
import { formatCurrency } from '@/lib/utils/currency'
import type { ResumoCategoria } from '@/types/models'

interface CategoryChartProps {
  title: string
  data?: ResumoCategoria[]
  isLoading?: boolean
  type: 'receita' | 'despesa'
}

export function CategoryChart({ title, data, isLoading, type }: CategoryChartProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[300px]">
          <Skeleton className="h-48 w-48 rounded-full" />
        </CardContent>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[300px]">
          <p className="text-muted-foreground">Nenhum dado disponível</p>
        </CardContent>
      </Card>
    )
  }

  const chartData = data.map((item) => ({
    name: `${item.categoria_icone} ${item.categoria_nome}`,
    value: item.total,
    color: item.categoria_cor,
  }))

  const total = data.reduce((acc, item) => acc + item.total, 0)

  // Generate accessible description
  const chartDescription = data
    .slice(0, 5)
    .map((item) => `${item.categoria_nome}: ${formatCurrency(item.total)} (${item.percentual.toFixed(0)}%)`)
    .join(', ')

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div
          role="img"
          aria-label={`Gráfico de ${title}. Total: ${formatCurrency(total)}. Distribuição por categoria: ${chartDescription}`}
        >
          <DonutChart
            data={chartData}
            category="value"
            index="name"
            valueFormatter={formatCurrency}
            colors={data.map((d) => d.categoria_cor)}
            className="h-48"
            showAnimation
            showTooltip
          />
        </div>
        <div className="mt-4 space-y-2">
          {data.slice(0, 5).map((item) => (
            <div key={item.categoria_id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.categoria_cor }}
                />
                <span className="text-muted-foreground">
                  {item.categoria_icone} {item.categoria_nome}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{formatCurrency(item.total)}</span>
                <span className="text-muted-foreground">({item.percentual.toFixed(0)}%)</span>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex justify-between text-sm font-medium">
            <span>Total</span>
            <span className={type === 'receita' ? 'text-success' : 'text-destructive'}>
              {formatCurrency(total)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
