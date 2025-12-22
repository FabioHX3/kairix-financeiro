'use client'

import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUIStore } from '@/stores/ui-store'
import { formatMonth, getAvailableMonths } from '@/lib/utils/date'

export function PeriodSelector() {
  const { selectedMonth, selectedYear, setSelectedPeriod } = useUIStore()
  const availableMonths = getAvailableMonths()

  const goToPreviousMonth = () => {
    if (selectedMonth === 1) {
      setSelectedPeriod(12, selectedYear - 1)
    } else {
      setSelectedPeriod(selectedMonth - 1, selectedYear)
    }
  }

  const goToNextMonth = () => {
    const now = new Date()
    const currentMonth = now.getMonth() + 1
    const currentYear = now.getFullYear()

    // Don't go beyond current month
    if (selectedYear === currentYear && selectedMonth >= currentMonth) {
      return
    }

    if (selectedMonth === 12) {
      setSelectedPeriod(1, selectedYear + 1)
    } else {
      setSelectedPeriod(selectedMonth + 1, selectedYear)
    }
  }

  const isNextDisabled = () => {
    const now = new Date()
    return selectedYear === now.getFullYear() && selectedMonth >= now.getMonth() + 1
  }

  const handleSelectChange = (value: string) => {
    const [month, year] = value.split('-').map(Number)
    setSelectedPeriod(month, year)
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon"
        onClick={goToPreviousMonth}
        className="h-9 w-9"
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>

      <Select
        value={`${selectedMonth}-${selectedYear}`}
        onValueChange={handleSelectChange}
      >
        <SelectTrigger className="w-[180px]">
          <Calendar className="mr-2 h-4 w-4" />
          <SelectValue>
            {formatMonth(selectedMonth, selectedYear)}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {availableMonths.map((m) => (
            <SelectItem key={`${m.month}-${m.year}`} value={`${m.month}-${m.year}`}>
              {m.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        variant="outline"
        size="icon"
        onClick={goToNextMonth}
        disabled={isNextDisabled()}
        className="h-9 w-9"
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  )
}
