import { format, parseISO, isToday, isYesterday, differenceInDays } from 'date-fns'
import { ptBR } from 'date-fns/locale'

/**
 * Format date to Brazilian format
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date
  return format(d, 'dd/MM/yyyy', { locale: ptBR })
}

/**
 * Format date with time
 */
export function formatDateTime(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date
  return format(d, 'dd/MM/yyyy HH:mm', { locale: ptBR })
}

/**
 * Format date relative (hoje, ontem, etc)
 */
export function formatRelativeDate(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date

  if (isToday(d)) {
    return 'Hoje'
  }

  if (isYesterday(d)) {
    return 'Ontem'
  }

  const days = differenceInDays(new Date(), d)

  if (days < 7) {
    return format(d, "EEEE", { locale: ptBR })
  }

  return format(d, 'dd/MM/yyyy', { locale: ptBR })
}

/**
 * Format month name
 */
export function formatMonth(month: number, year: number): string {
  const date = new Date(year, month - 1, 1)
  return format(date, 'MMMM yyyy', { locale: ptBR })
}

/**
 * Format month short
 */
export function formatMonthShort(month: number): string {
  const date = new Date(2024, month - 1, 1)
  return format(date, 'MMM', { locale: ptBR })
}

/**
 * Get month name from string like "2024-01"
 */
export function parseMonthString(monthStr: string): string {
  const [year, month] = monthStr.split('-').map(Number)
  return formatMonth(month, year)
}

/**
 * Convert date to ISO string for API
 */
export function toISODate(date: Date): string {
  return format(date, 'yyyy-MM-dd')
}

/**
 * Get available months for filter (last 12 months)
 */
export function getAvailableMonths(): { month: number; year: number; label: string }[] {
  const months = []
  const now = new Date()

  for (let i = 0; i < 12; i++) {
    const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
    months.push({
      month: date.getMonth() + 1,
      year: date.getFullYear(),
      label: format(date, 'MMMM yyyy', { locale: ptBR }),
    })
  }

  return months
}
