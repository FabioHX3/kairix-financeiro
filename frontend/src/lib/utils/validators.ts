import { z } from 'zod'

// Login schema
export const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  senha: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres'),
})

export type LoginFormData = z.infer<typeof loginSchema>

// Register schema
export const registerSchema = z.object({
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  email: z.string().email('Email inválido'),
  senha: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres'),
  confirmarSenha: z.string(),
  telefone: z.string().optional(),
  whatsapp: z.string().optional(),
}).refine((data) => data.senha === data.confirmarSenha, {
  message: 'Senhas não conferem',
  path: ['confirmarSenha'],
})

export type RegisterFormData = z.infer<typeof registerSchema>

// Transaction schema
export const transactionSchema = z.object({
  tipo: z.enum(['receita', 'despesa'], { message: 'Selecione o tipo' }),
  valor: z.number({ message: 'Informe o valor' }).positive('Valor deve ser maior que zero'),
  descricao: z.string().optional(),
  data_transacao: z.date({ message: 'Informe a data' }),
  categoria_id: z.number().optional(),
})

export type TransactionFormData = z.infer<typeof transactionSchema>

// Category schema
export const categorySchema = z.object({
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  tipo: z.enum(['receita', 'despesa'], { message: 'Selecione o tipo' }),
  cor: z.string().regex(/^#[0-9A-Fa-f]{6}$/, 'Cor inválida'),
  icone: z.string().min(1, 'Selecione um ícone'),
})

export type CategoryFormData = z.infer<typeof categorySchema>

// Profile schema
export const profileSchema = z.object({
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  email: z.string().email('Email inválido'),
  telefone: z.string().optional(),
  whatsapp: z.string().optional(),
})

export type ProfileFormData = z.infer<typeof profileSchema>

// Change password schema
export const changePasswordSchema = z.object({
  senhaAtual: z.string().min(1, 'Informe a senha atual'),
  senhaNova: z.string().min(6, 'Nova senha deve ter pelo menos 6 caracteres'),
  confirmarSenha: z.string(),
}).refine((data) => data.senhaNova === data.confirmarSenha, {
  message: 'Senhas não conferem',
  path: ['confirmarSenha'],
})

export type ChangePasswordFormData = z.infer<typeof changePasswordSchema>

// Family member schema
export const familyMemberSchema = z.object({
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  telefone: z.string().min(10, 'Telefone inválido'),
})

export type FamilyMemberFormData = z.infer<typeof familyMemberSchema>

// Preferences schema
export const preferencesSchema = z.object({
  personalidade: z.enum(['formal', 'amigavel', 'divertido']),
  alertar_vencimentos: z.boolean(),
  dias_antes_vencimento: z.number().min(1).max(30),
  alertar_gastos_anomalos: z.boolean(),
  limite_anomalia_percentual: z.number().min(10).max(100),
  resumo_diario: z.boolean(),
  resumo_semanal: z.boolean(),
  resumo_mensal: z.boolean(),
  horario_resumo: z.string(),
  auto_confirmar_confianca: z.number().min(0.5).max(1),
})

export type PreferencesFormData = z.infer<typeof preferencesSchema>
