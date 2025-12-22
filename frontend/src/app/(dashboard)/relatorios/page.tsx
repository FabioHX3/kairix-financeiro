'use client'

import { Download, TrendingUp, TrendingDown, Wallet, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { BarChart, DonutChart, AreaChart } from '@tremor/react'
import { useDashboard } from '@/hooks/use-dashboard'
import { useUIStore } from '@/stores/ui-store'
import { formatCurrency, formatPercentage } from '@/lib/utils/currency'
import { formatMonth, getAvailableMonths, parseMonthString } from '@/lib/utils/date'
import { Skeleton } from '@/components/ui/skeleton'

export default function RelatoriosPage() {
  const { selectedMonth, selectedYear, setSelectedPeriod } = useUIStore()
  const { data, isLoading } = useDashboard()
  const availableMonths = getAvailableMonths()

  const handlePeriodChange = (value: string) => {
    const [month, year] = value.split('-').map(Number)
    setSelectedPeriod(month, year)
  }

  // Prepare data for charts
  const despesasChartData = data?.despesas_por_categoria.map((cat) => ({
    name: `${cat.categoria_icone} ${cat.categoria_nome}`,
    value: cat.total,
  })) || []

  const receitasChartData = data?.receitas_por_categoria.map((cat) => ({
    name: `${cat.categoria_icone} ${cat.categoria_nome}`,
    value: cat.total,
  })) || []

  const evolucaoChartData = data?.evolucao_mensal.map((item) => ({
    mes: parseMonthString(item.mes),
    Receitas: item.receitas,
    Despesas: item.despesas,
    Saldo: item.saldo,
  })) || []

  const comparativoData = data?.evolucao_mensal.slice(-2).map((item) => ({
    mes: parseMonthString(item.mes),
    Receitas: item.receitas,
    Despesas: item.despesas,
  })) || []

  // Calculate totals
  const totalReceitas = data?.resumo_geral.total_receitas || 0
  const totalDespesas = data?.resumo_geral.total_despesas || 0
  const saldo = data?.resumo_geral.saldo || 0
  const taxaPoupanca = totalReceitas > 0 ? ((totalReceitas - totalDespesas) / totalReceitas) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Relatórios</h1>
          <p className="text-muted-foreground">
            Análise detalhada de {formatMonth(selectedMonth, selectedYear)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={`${selectedMonth}-${selectedYear}`}
            onValueChange={handlePeriodChange}
          >
            <SelectTrigger className="w-[180px]">
              <Calendar className="mr-2 h-4 w-4" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {availableMonths.map((m) => (
                <SelectItem key={`${m.month}-${m.year}`} value={`${m.month}-${m.year}`}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Receitas
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-success" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <div className="text-2xl font-bold text-success">
                {formatCurrency(totalReceitas)}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Despesas
            </CardTitle>
            <TrendingDown className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <div className="text-2xl font-bold text-destructive">
                {formatCurrency(totalDespesas)}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Saldo do Mês
            </CardTitle>
            <Wallet className="h-4 w-4 text-accent" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-32" />
            ) : (
              <div className={`text-2xl font-bold ${saldo >= 0 ? 'text-success' : 'text-destructive'}`}>
                {formatCurrency(saldo)}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Taxa de Poupança
            </CardTitle>
            <span className="text-lg">💰</span>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <div className={`text-2xl font-bold ${taxaPoupanca >= 0 ? 'text-success' : 'text-destructive'}`}>
                {formatPercentage(taxaPoupanca)}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Despesas por Categoria</CardTitle>
            <CardDescription>Distribuição das despesas do mês</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center h-[300px]">
                <Skeleton className="h-48 w-48 rounded-full" />
              </div>
            ) : despesasChartData.length > 0 ? (
              <DonutChart
                data={despesasChartData}
                category="value"
                index="name"
                valueFormatter={formatCurrency}
                className="h-[300px]"
                showAnimation
              />
            ) : (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                Nenhuma despesa no período
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Receitas por Categoria</CardTitle>
            <CardDescription>Distribuição das receitas do mês</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center h-[300px]">
                <Skeleton className="h-48 w-48 rounded-full" />
              </div>
            ) : receitasChartData.length > 0 ? (
              <DonutChart
                data={receitasChartData}
                category="value"
                index="name"
                valueFormatter={formatCurrency}
                colors={['emerald', 'teal', 'cyan', 'sky', 'blue']}
                className="h-[300px]"
                showAnimation
              />
            ) : (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                Nenhuma receita no período
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Evolution Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Evolução Mensal</CardTitle>
          <CardDescription>Comparativo de receitas e despesas nos últimos meses</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[350px] w-full" />
          ) : evolucaoChartData.length > 0 ? (
            <AreaChart
              data={evolucaoChartData}
              index="mes"
              categories={['Receitas', 'Despesas']}
              colors={['emerald', 'rose']}
              valueFormatter={formatCurrency}
              className="h-[350px]"
              showAnimation
              showLegend
              showGridLines
            />
          ) : (
            <div className="flex items-center justify-center h-[350px] text-muted-foreground">
              Dados insuficientes para gráfico de evolução
            </div>
          )}
        </CardContent>
      </Card>

      {/* Comparison Chart */}
      {comparativoData.length === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Comparativo com Mês Anterior</CardTitle>
            <CardDescription>Evolução em relação ao período anterior</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-[300px] w-full" />
            ) : (
              <BarChart
                data={comparativoData}
                index="mes"
                categories={['Receitas', 'Despesas']}
                colors={['emerald', 'rose']}
                valueFormatter={formatCurrency}
                className="h-[300px]"
                showAnimation
                showLegend
              />
            )}
          </CardContent>
        </Card>
      )}

      {/* Top Expenses Table */}
      <Card>
        <CardHeader>
          <CardTitle>Top 5 Categorias de Despesas</CardTitle>
          <CardDescription>Onde você mais gastou este mês</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : data?.despesas_por_categoria && data.despesas_por_categoria.length > 0 ? (
            <div className="space-y-4">
              {data.despesas_por_categoria.slice(0, 5).map((cat, index) => (
                <div key={cat.categoria_id} className="flex items-center gap-4">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium">
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium">
                        {cat.categoria_icone} {cat.categoria_nome}
                      </span>
                      <span className="font-semibold text-destructive">
                        {formatCurrency(cat.total)}
                      </span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-destructive rounded-full transition-all"
                        style={{ width: `${cat.percentual}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>{cat.quantidade} transações</span>
                      <span>{cat.percentual.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Nenhuma despesa no período
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
