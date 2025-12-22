/**
 * Format a number as Brazilian currency (BRL)
 */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value)
}

/**
 * Format a number as Brazilian currency without the symbol
 */
export function formatCurrencyValue(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

/**
 * Parse a Brazilian currency string to number
 */
export function parseCurrency(value: string): number {
  // Remove currency symbol and spaces
  const cleaned = value.replace(/[R$\s]/g, '')
  // Replace dots (thousands) and commas (decimals)
  const normalized = cleaned.replace(/\./g, '').replace(',', '.')
  return parseFloat(normalized) || 0
}

/**
 * Format percentage
 */
export function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`
}
