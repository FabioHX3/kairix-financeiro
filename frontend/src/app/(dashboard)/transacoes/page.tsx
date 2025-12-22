'use client'

import { useState, useMemo } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { TransactionFilters } from '@/components/transactions/transaction-filters'
import { TransactionList } from '@/components/transactions/transaction-list'
import { TransactionDialog } from '@/components/transactions/transaction-dialog'
import { useTransactions } from '@/hooks/use-transactions'
import type { TransacaoFiltros } from '@/types/models'

export default function TransacoesPage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [filters, setFilters] = useState<TransacaoFiltros>({})
  const [searchTerm, setSearchTerm] = useState('')

  const { data: transactions, isLoading } = useTransactions(filters)

  // Filter transactions by search term (client-side)
  const filteredTransactions = useMemo(() => {
    if (!transactions || !searchTerm) return transactions

    const term = searchTerm.toLowerCase()
    return transactions.filter(
      (t) =>
        t.descricao?.toLowerCase().includes(term) ||
        t.categoria?.nome.toLowerCase().includes(term) ||
        t.codigo.toLowerCase().includes(term)
    )
  }, [transactions, searchTerm])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Transações</h1>
          <p className="text-muted-foreground">
            Gerencie suas receitas e despesas
          </p>
        </div>
        <Button onClick={() => setIsDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nova transação
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <TransactionFilters
            filters={filters}
            onFiltersChange={setFilters}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
          />
        </CardContent>
      </Card>

      {/* Transactions List */}
      <Card>
        <CardContent className="pt-6">
          <TransactionList
            transactions={filteredTransactions}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <TransactionDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
      />
    </div>
  )
}
