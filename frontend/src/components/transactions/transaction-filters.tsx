'use client'

import { useState } from 'react'
import { Search, Filter, X, Calendar } from 'lucide-react'
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'
import { useCategories } from '@/hooks/use-categories'
import type { TipoTransacao, TransacaoFiltros } from '@/types/models'

interface TransactionFiltersProps {
  filters: TransacaoFiltros
  onFiltersChange: (filters: TransacaoFiltros) => void
  searchTerm: string
  onSearchChange: (term: string) => void
}

export function TransactionFilters({
  filters,
  onFiltersChange,
  searchTerm,
  onSearchChange,
}: TransactionFiltersProps) {
  const [isOpen, setIsOpen] = useState(false)
  const { data: categories } = useCategories()

  const activeFiltersCount = [
    filters.tipo,
    filters.categoria_id,
    filters.data_inicio,
    filters.data_fim,
  ].filter(Boolean).length

  const handleTipoChange = (value: string) => {
    onFiltersChange({
      ...filters,
      tipo: value === 'todos' ? undefined : (value as TipoTransacao),
    })
  }

  const handleCategoriaChange = (value: string) => {
    onFiltersChange({
      ...filters,
      categoria_id: value === 'todas' ? undefined : Number(value),
    })
  }

  const handleDataInicioChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({
      ...filters,
      data_inicio: e.target.value || undefined,
    })
  }

  const handleDataFimChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onFiltersChange({
      ...filters,
      data_fim: e.target.value || undefined,
    })
  }

  const clearFilters = () => {
    onFiltersChange({})
    onSearchChange('')
  }

  return (
    <div className="flex flex-col sm:flex-row gap-3">
      {/* Search */}
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por descrição..."
          value={searchTerm}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Filter Popover */}
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" className="gap-2">
            <Filter className="h-4 w-4" />
            Filtros
            {activeFiltersCount > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 w-5 p-0 flex items-center justify-center">
                {activeFiltersCount}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80" align="end">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-medium">Filtros</h4>
              {activeFiltersCount > 0 && (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  <X className="h-4 w-4 mr-1" />
                  Limpar
                </Button>
              )}
            </div>

            {/* Tipo */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Tipo</label>
              <Select
                value={filters.tipo || 'todos'}
                onValueChange={handleTipoChange}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todos" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="todos">Todos</SelectItem>
                  <SelectItem value="receita">Receitas</SelectItem>
                  <SelectItem value="despesa">Despesas</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Categoria */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Categoria</label>
              <Select
                value={filters.categoria_id?.toString() || 'todas'}
                onValueChange={handleCategoriaChange}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todas" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="todas">Todas</SelectItem>
                  {categories?.map((cat) => (
                    <SelectItem key={cat.id} value={cat.id.toString()}>
                      {cat.icone} {cat.nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Data Início */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Data inicial</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="date"
                  value={filters.data_inicio || ''}
                  onChange={handleDataInicioChange}
                  className="pl-9"
                />
              </div>
            </div>

            {/* Data Fim */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Data final</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="date"
                  value={filters.data_fim || ''}
                  onChange={handleDataFimChange}
                  className="pl-9"
                />
              </div>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
