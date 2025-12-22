'use client'

import { useState } from 'react'
import { MoreHorizontal, Pencil, Trash2, TrendingUp, TrendingDown } from 'lucide-react'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { TransactionDialog } from './transaction-dialog'
import { useDeleteTransaction } from '@/hooks/use-transactions'
import { formatCurrency } from '@/lib/utils/currency'
import { formatDate } from '@/lib/utils/date'
import { cn } from '@/lib/utils'
import type { Transacao } from '@/types/models'

interface TransactionListProps {
  transactions?: Transacao[]
  isLoading?: boolean
}

export function TransactionList({ transactions, isLoading }: TransactionListProps) {
  const [editTransaction, setEditTransaction] = useState<Transacao | undefined>()
  const [deleteTransaction, setDeleteTransaction] = useState<Transacao | undefined>()
  const deleteMutation = useDeleteTransaction()

  const handleDelete = () => {
    if (deleteTransaction) {
      deleteMutation.mutate(deleteTransaction.id, {
        onSuccess: () => setDeleteTransaction(undefined),
      })
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center justify-between p-4 border rounded-lg">
            <div className="flex items-center gap-3">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-24" />
              </div>
            </div>
            <Skeleton className="h-5 w-24" />
          </div>
        ))}
      </div>
    )
  }

  if (!transactions || transactions.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Nenhuma transação encontrada</p>
      </div>
    )
  }

  return (
    <>
      {/* Desktop Table */}
      <div className="hidden md:block rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Descrição</TableHead>
              <TableHead>Categoria</TableHead>
              <TableHead>Data</TableHead>
              <TableHead>Código</TableHead>
              <TableHead className="text-right">Valor</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.map((transaction) => (
              <TableRow key={transaction.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'h-8 w-8 rounded-full flex items-center justify-center',
                        transaction.tipo === 'receita'
                          ? 'bg-success/10 text-success'
                          : 'bg-destructive/10 text-destructive'
                      )}
                    >
                      {transaction.tipo === 'receita' ? (
                        <TrendingUp className="h-4 w-4" />
                      ) : (
                        <TrendingDown className="h-4 w-4" />
                      )}
                    </div>
                    <span className="font-medium">
                      {transaction.descricao || 'Sem descrição'}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  {transaction.categoria ? (
                    <Badge variant="secondary">
                      {transaction.categoria.icone} {transaction.categoria.nome}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell>{formatDate(transaction.data_transacao)}</TableCell>
                <TableCell>
                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                    {transaction.codigo}
                  </code>
                </TableCell>
                <TableCell className="text-right">
                  <span
                    className={cn(
                      'font-semibold',
                      transaction.tipo === 'receita' ? 'text-success' : 'text-destructive'
                    )}
                  >
                    {transaction.tipo === 'receita' ? '+' : '-'}
                    {formatCurrency(transaction.valor)}
                  </span>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => setEditTransaction(transaction)}>
                        <Pencil className="mr-2 h-4 w-4" />
                        Editar
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => setDeleteTransaction(transaction)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Excluir
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile List */}
      <div className="md:hidden space-y-3">
        {transactions.map((transaction) => (
          <div
            key={transaction.id}
            className="flex items-center justify-between p-4 border rounded-lg"
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
                  {transaction.descricao || 'Sem descrição'}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(transaction.data_transacao)}
                  {transaction.categoria && (
                    <span className="ml-2">
                      {transaction.categoria.icone} {transaction.categoria.nome}
                    </span>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'font-semibold text-sm',
                  transaction.tipo === 'receita' ? 'text-success' : 'text-destructive'
                )}
              >
                {transaction.tipo === 'receita' ? '+' : '-'}
                {formatCurrency(transaction.valor)}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => setEditTransaction(transaction)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Editar
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => setDeleteTransaction(transaction)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Excluir
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        ))}
      </div>

      {/* Edit Dialog */}
      <TransactionDialog
        open={!!editTransaction}
        onOpenChange={(open) => !open && setEditTransaction(undefined)}
        transaction={editTransaction}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTransaction}
        onOpenChange={(open) => !open && setDeleteTransaction(undefined)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir transação?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação não pode ser desfeita. A transação será permanentemente removida.
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
    </>
  )
}
