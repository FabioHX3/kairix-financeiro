import { describe, expect, it } from 'vitest'

/**
 * Valida força da senha
 */
function validatePassword(password: string): { valid: boolean; error?: string } {
  if (password.length < 8) {
    return { valid: false, error: 'Senha deve ter no mínimo 8 caracteres' }
  }
  if (!/[a-z]/.test(password)) {
    return { valid: false, error: 'Senha deve conter pelo menos uma letra minúscula' }
  }
  if (!/[A-Z]/.test(password)) {
    return { valid: false, error: 'Senha deve conter pelo menos uma letra maiúscula' }
  }
  if (!/\d/.test(password)) {
    return { valid: false, error: 'Senha deve conter pelo menos um número' }
  }
  return { valid: true }
}

/**
 * Formata valor em Real brasileiro
 */
function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(value)
}

/**
 * Valida formato de WhatsApp
 */
function validateWhatsApp(phone: string): boolean {
  const cleaned = phone.replace(/\D/g, '')
  return cleaned.length >= 10 && cleaned.length <= 15
}

describe('Password Validation', () => {
  it('should accept valid password', () => {
    const result = validatePassword('SenhaForte123')
    expect(result.valid).toBe(true)
    expect(result.error).toBeUndefined()
  })

  it('should reject short password', () => {
    const result = validatePassword('Ab1')
    expect(result.valid).toBe(false)
    expect(result.error).toContain('8 caracteres')
  })

  it('should reject password without lowercase', () => {
    const result = validatePassword('SENHAFORTE123')
    expect(result.valid).toBe(false)
    expect(result.error).toContain('minúscula')
  })

  it('should reject password without uppercase', () => {
    const result = validatePassword('senhafraca123')
    expect(result.valid).toBe(false)
    expect(result.error).toContain('maiúscula')
  })

  it('should reject password without number', () => {
    const result = validatePassword('SenhaFraca')
    expect(result.valid).toBe(false)
    expect(result.error).toContain('número')
  })
})

describe('Currency Formatting', () => {
  it('should format positive values', () => {
    const result = formatCurrency(1234.56)
    expect(result).toContain('R$')
    expect(result).toContain('1.234,56')
  })

  it('should format zero', () => {
    const result = formatCurrency(0)
    expect(result).toContain('R$')
    expect(result).toContain('0,00')
  })

  it('should format negative values', () => {
    const result = formatCurrency(-100.5)
    expect(result).toContain('R$')
    expect(result).toContain('100,50')
  })
})

describe('WhatsApp Validation', () => {
  it('should accept valid phone with 11 digits', () => {
    expect(validateWhatsApp('11999999999')).toBe(true)
  })

  it('should accept valid phone with 13 digits (country code)', () => {
    expect(validateWhatsApp('5511999999999')).toBe(true)
  })

  it('should accept formatted phone', () => {
    expect(validateWhatsApp('(11) 99999-9999')).toBe(true)
  })

  it('should reject short phone', () => {
    expect(validateWhatsApp('123456789')).toBe(false)
  })

  it('should reject too long phone', () => {
    expect(validateWhatsApp('1234567890123456')).toBe(false)
  })
})
