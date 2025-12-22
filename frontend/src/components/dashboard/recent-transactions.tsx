'use client'

import Link from 'next/link'
import { ArrowRight, TrendingUp, TrendingDown } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatCurrency } from '@/lib/utils/currency'
import { formatRelativeDate } from '@/lib/utils/date'
import type { Transacao } from '@/types/models'
import { cn } from '@/lib/utils'

interface RecentTransactionsProps {
  data?: Transacao[]
  isLoading?: boolean
}

export function RecentTransactions({ data, isLoading }: RecentTransactionsProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Últimas Transações</CardTitle>
          <Skeleton className="h-8 w-24" />
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="space-y-1">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
              <Skeleton className="h-5 w-24" />
            </div>
          ))}
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">Últimas Transações</CardTitle>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/transacoes" className="flex items-center gap-1">
            Ver todas
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {!data || data.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">
            Nenhuma transação encontrada
          </p>
        ) : (
          <div className="space-y-4">
            {data.slice(0, 5).map((transaction) => (
              <div
                key={transaction.id}
                className="flex items-center justify-between hover:bg-secondary/50 -mx-2 px-2 py-2 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      'h-10 w-10 rounded-full flex items-center justify-center',
                      transaction.tipo === 'receita'
                        ? 'bg-success/10 text-success'
                        : 'bg-destructive/10 text-destructive'
                    )}
                  >
                    {transaction.tipo === 'receita' ? (
                      <TrendingUp className="h-5 w-5" />
                    ) : (
                      <TrendingDown className="h-5 w-5" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-sm">
                      {transaction.descricao || transaction.categoria?.nome || 'Sem descrição'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatRelativeDate(transaction.data_transacao)}
                      {transaction.categoria && (
                        <span className="ml-2">
                          {transaction.categoria.icone} {transaction.categoria.nome}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <span
                  className={cn(
                    'font-semibold',
                    transaction.tipo === 'receita' ? 'text-success' : 'text-destructive'
                  )}
                >
                  {transaction.tipo === 'receita' ? '+' : '-'}
                  {formatCurrency(transaction.valor)}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
