'use client'

import { TrendingUp, TrendingDown, Wallet, ArrowLeftRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { formatCurrency } from '@/lib/utils/currency'
import type { ResumoPeriodo } from '@/types/models'

interface StatsCardsProps {
  data?: ResumoPeriodo
  isLoading?: boolean
}

export function StatsCards({ data, isLoading }: StatsCardsProps) {
  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-5 w-5 rounded" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-32 mb-1" />
              <Skeleton className="h-3 w-20" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const cards = [
    {
      title: 'Receitas',
      value: data?.total_receitas || 0,
      count: data?.quantidade_receitas || 0,
      icon: TrendingUp,
      color: 'text-success',
      borderColor: 'border-l-success',
    },
    {
      title: 'Despesas',
      value: data?.total_despesas || 0,
      count: data?.quantidade_despesas || 0,
      icon: TrendingDown,
      color: 'text-destructive',
      borderColor: 'border-l-destructive',
    },
    {
      title: 'Saldo',
      value: data?.saldo || 0,
      count: null,
      icon: Wallet,
      color: data?.saldo && data.saldo >= 0 ? 'text-accent' : 'text-destructive',
      borderColor: data?.saldo && data.saldo >= 0 ? 'border-l-accent' : 'border-l-destructive',
    },
    {
      title: 'Transações',
      value: null,
      count: (data?.quantidade_receitas || 0) + (data?.quantidade_despesas || 0),
      icon: ArrowLeftRight,
      color: 'text-warning',
      borderColor: 'border-l-warning',
    },
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title} className={`border-l-4 ${card.borderColor}`}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
            <card.icon className={`h-5 w-5 ${card.color}`} />
          </CardHeader>
          <CardContent>
            {card.value !== null ? (
              <div className="text-2xl font-bold">
                {formatCurrency(card.value)}
              </div>
            ) : (
              <div className="text-2xl font-bold">{card.count}</div>
            )}
            {card.count !== null && card.value !== null && (
              <p className="text-xs text-muted-foreground">
                {card.count} {card.count === 1 ? 'transação' : 'transações'}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
