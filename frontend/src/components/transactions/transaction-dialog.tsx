'use client'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { TransactionForm } from './transaction-form'
import type { Transacao } from '@/types/models'

interface TransactionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  transaction?: Transacao
}

export function TransactionDialog({ open, onOpenChange, transaction }: TransactionDialogProps) {
  const isEditing = !!transaction

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Editar transação' : 'Nova transação'}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Atualize os dados da transação abaixo.'
              : 'Preencha os dados para criar uma nova transação.'}
          </DialogDescription>
        </DialogHeader>
        <TransactionForm
          transaction={transaction}
          onSuccess={() => onOpenChange(false)}
          onCancel={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  )
}
