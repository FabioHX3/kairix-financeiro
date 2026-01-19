'use client'

import { useState } from 'react'
import { Target, Plus, RefreshCw, TrendingUp, TrendingDown, Calendar, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useRecurrences, useForecast, useDeleteRecurrence, useDetectRecurrences } from '@/hooks/use-recurrences'
import { formatCurrency } from '@/lib/utils/currency'
import { formatDate } from '@/lib/utils/date'
import { cn } from '@/lib/utils'
import type { RecurringTransaction } from '@/types/models'

const frequencyLabels: Record<string, string> = {
  diaria: 'Diária',
  semanal: 'Semanal',
  quinzenal: 'Quinzenal',
  mensal: 'Mensal',
  bimestral: 'Bimestral',
  trimestral: 'Trimestral',
  semestral: 'Semestral',
  anual: 'Anual',
}

export default function MetasPage() {
  const [deleteRecurrence, setDeleteRecurrence] = useState<RecurringTransaction | undefined>()
  const { data: recurrences, isLoading: loadingRecurrences } = useRecurrences()
  const { data: _forecast, isLoading: _loadingForecast } = useForecast()
  const deleteMutation = useDeleteRecurrence()
  const detectMutation = useDetectRecurrences()

  const handleDelete = () => {
    if (deleteRecurrence) {
      deleteMutation.mutate(deleteRecurrence.id, {
        onSuccess: () => setDeleteRecurrence(undefined),
      })
    }
  }

  // Separate by type
  const despesasRecorrentes = recurrences?.filter((r) => r.tipo === 'despesa') || []
  const receitasRecorrentes = recurrences?.filter((r) => r.tipo === 'receita') || []

  // Calculate totals
  const totalDespesasRecorrentes = despesasRecorrentes.reduce((acc, r) => acc + r.valor_medio, 0)
  const totalReceitasRecorrentes = receitasRecorrentes.reduce((acc, r) => acc + r.valor_medio, 0)
  const saldoPrevistoMensal = totalReceitasRecorrentes - totalDespesasRecorrentes

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Metas e Recorrências</h1>
          <p className="text-muted-foreground">
            Gerencie seus gastos fixos e previsões
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => detectMutation.mutate()}
            disabled={detectMutation.isPending}
          >
            <RefreshCw className={cn("h-4 w-4 mr-2", detectMutation.isPending && "animate-spin")} />
            Detectar Recorrências
          </Button>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Nova Recorrência
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-l-4 border-l-success">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Receitas Fixas
            </CardTitle>
            <TrendingUp className="h-5 w-5 text-success" />
          </CardHeader>
          <CardContent>
            {loadingRecurrences ? (
              <Skeleton className="h-8 w-32" />
            ) : (
              <>
                <div className="text-2xl font-bold text-success">
                  {formatCurrency(totalReceitasRecorrentes)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {receitasRecorrentes.length} recorrências
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-destructive">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Despesas Fixas
            </CardTitle>
            <TrendingDown className="h-5 w-5 text-destructive" />
          </CardHeader>
          <CardContent>
            {loadingRecurrences ? (
              <Skeleton className="h-8 w-32" />
            ) : (
              <>
                <div className="text-2xl font-bold text-destructive">
                  {formatCurrency(totalDespesasRecorrentes)}
                </div>
                <p className="text-xs text-muted-foreground">
                  {despesasRecorrentes.length} recorrências
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-accent">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Saldo Previsto
            </CardTitle>
            <Target className="h-5 w-5 text-accent" />
          </CardHeader>
          <CardContent>
            {loadingRecurrences ? (
              <Skeleton className="h-8 w-32" />
            ) : (
              <>
                <div className={cn(
                  "text-2xl font-bold",
                  saldoPrevistoMensal >= 0 ? 'text-success' : 'text-destructive'
                )}>
                  {formatCurrency(saldoPrevistoMensal)}
                </div>
                <p className="text-xs text-muted-foreground">
                  por mês
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recurrences Lists */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Despesas Recorrentes */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-destructive" />
              Despesas Fixas
            </CardTitle>
            <CardDescription>Suas contas e gastos recorrentes</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingRecurrences ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : despesasRecorrentes.length > 0 ? (
              <div className="space-y-3">
                {despesasRecorrentes.map((recurrence) => (
                  <div
                    key={recurrence.id}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-secondary/50 transition-colors"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{recurrence.descricao_padrao}</span>
                        <Badge variant="outline" className="text-xs">
                          {frequencyLabels[recurrence.frequencia] || recurrence.frequencia}
                        </Badge>
                        {recurrence.detectada_automaticamente && (
                          <Badge variant="secondary" className="text-xs">
                            Auto
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        {recurrence.proxima_esperada && (
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            Próxima: {formatDate(recurrence.proxima_esperada)}
                          </span>
                        )}
                        <span>{recurrence.ocorrencias} ocorrências</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-destructive">
                        {formatCurrency(recurrence.valor_medio)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={() => setDeleteRecurrence(recurrence)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Nenhuma despesa recorrente encontrada
              </div>
            )}
          </CardContent>
        </Card>

        {/* Receitas Recorrentes */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-success" />
              Receitas Fixas
            </CardTitle>
            <CardDescription>Seus ganhos recorrentes</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingRecurrences ? (
              <div className="space-y-3">
                {[1, 2].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : receitasRecorrentes.length > 0 ? (
              <div className="space-y-3">
                {receitasRecorrentes.map((recurrence) => (
                  <div
                    key={recurrence.id}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-secondary/50 transition-colors"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{recurrence.descricao_padrao}</span>
                        <Badge variant="outline" className="text-xs">
                          {frequencyLabels[recurrence.frequencia] || recurrence.frequencia}
                        </Badge>
                        {recurrence.detectada_automaticamente && (
                          <Badge variant="secondary" className="text-xs">
                            Auto
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        {recurrence.proxima_esperada && (
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            Próxima: {formatDate(recurrence.proxima_esperada)}
                          </span>
                        )}
                        <span>{recurrence.ocorrencias} ocorrências</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-success">
                        {formatCurrency(recurrence.valor_medio)}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={() => setDeleteRecurrence(recurrence)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                Nenhuma receita recorrente encontrada
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteRecurrence}
        onOpenChange={(open) => !open && setDeleteRecurrence(undefined)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir recorrência?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação não pode ser desfeita. A recorrência será permanentemente removida.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Excluindo...' : 'Excluir'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
