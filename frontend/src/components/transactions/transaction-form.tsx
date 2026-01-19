'use client'

import { useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { useCategories } from '@/hooks/use-categories'
import { useCreateTransaction, useUpdateTransaction } from '@/hooks/use-transactions'
import { transactionSchema, type TransactionFormData } from '@/lib/utils/validators'
import { toISODate } from '@/lib/utils/date'
import type { Transacao } from '@/types/models'

interface TransactionFormProps {
  transaction?: Transacao
  onSuccess?: () => void
  onCancel?: () => void
}

export function TransactionForm({ transaction, onSuccess, onCancel }: TransactionFormProps) {
  const isEditing = !!transaction
  const { data: categories } = useCategories()
  const createMutation = useCreateTransaction()
  const updateMutation = useUpdateTransaction()

  const form = useForm<TransactionFormData>({
    resolver: zodResolver(transactionSchema),
    defaultValues: {
      tipo: 'despesa',
      valor: 0,
      descricao: '',
      data_transacao: new Date(),
      categoria_id: undefined,
    },
  })

  const selectedTipo = form.watch('tipo')

  // Filter categories by type - memoized to prevent unnecessary re-renders
  const filteredCategories = useMemo(
    () => categories?.filter((cat) => cat.tipo === selectedTipo) || [],
    [categories, selectedTipo]
  )

  // Populate form when editing
  useEffect(() => {
    if (transaction) {
      form.reset({
        tipo: transaction.tipo,
        valor: transaction.valor,
        descricao: transaction.descricao || '',
        data_transacao: new Date(transaction.data_transacao),
        categoria_id: transaction.categoria_id,
      })
    }
  }, [transaction, form])

  // Reset categoria when tipo changes
  useEffect(() => {
    const currentCategoria = form.getValues('categoria_id')
    const categoriaExists = filteredCategories.some((cat) => cat.id === currentCategoria)
    if (!categoriaExists) {
      form.setValue('categoria_id', undefined)
    }
  }, [selectedTipo, filteredCategories, form])

  const onSubmit = async (data: TransactionFormData) => {
    const payload = {
      tipo: data.tipo,
      valor: data.valor,
      descricao: data.descricao,
      data_transacao: toISODate(data.data_transacao),
      categoria_id: data.categoria_id,
      origem: 'web' as const,
    }

    if (isEditing && transaction) {
      updateMutation.mutate(
        { id: transaction.id, data: payload },
        { onSuccess }
      )
    } else {
      createMutation.mutate(payload, { onSuccess })
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {/* Tipo */}
        <FormField
          control={form.control}
          name="tipo"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Tipo</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione o tipo" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="receita">
                    <span className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-success" />
                      Receita
                    </span>
                  </SelectItem>
                  <SelectItem value="despesa">
                    <span className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-destructive" />
                      Despesa
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Valor */}
        <FormField
          control={form.control}
          name="valor"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Valor</FormLabel>
              <FormControl>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                    R$
                  </span>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="0,00"
                    className="pl-10"
                    {...field}
                    onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                  />
                </div>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Descrição */}
        <FormField
          control={form.control}
          name="descricao"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Descrição</FormLabel>
              <FormControl>
                <Input placeholder="Ex: Compras no supermercado" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Categoria */}
        <FormField
          control={form.control}
          name="categoria_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Categoria</FormLabel>
              <Select
                onValueChange={(value) => field.onChange(value ? Number(value) : undefined)}
                value={field.value?.toString()}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione uma categoria" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {filteredCategories.map((cat) => (
                    <SelectItem key={cat.id} value={cat.id.toString()}>
                      <span className="flex items-center gap-2">
                        <span>{cat.icone}</span>
                        {cat.nome}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Data */}
        <FormField
          control={form.control}
          name="data_transacao"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Data</FormLabel>
              <FormControl>
                <Input
                  type="date"
                  value={field.value ? toISODate(field.value) : ''}
                  onChange={(e) => field.onChange(e.target.value ? new Date(e.target.value) : undefined)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              Cancelar
            </Button>
          )}
          <Button type="submit" disabled={isPending}>
            {isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {isEditing ? 'Salvando...' : 'Criando...'}
              </>
            ) : (
              <>{isEditing ? 'Salvar' : 'Criar transação'}</>
            )}
          </Button>
        </div>
      </form>
    </Form>
  )
}
