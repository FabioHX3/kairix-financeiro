// Enums
export type TipoTransacao = 'receita' | 'despesa'
export type StatusTransacao = 'pendente' | 'confirmada' | 'cancelada'
export type OrigemRegistro = 'whatsapp_texto' | 'whatsapp_audio' | 'whatsapp_imagem' | 'web' | 'api'
export type PersonalidadeIA = 'formal' | 'amigavel' | 'divertido'
export type FrequenciaRecorrencia = 'diaria' | 'semanal' | 'quinzenal' | 'mensal' | 'bimestral' | 'trimestral' | 'semestral' | 'anual'
export type StatusRecorrencia = 'ativa' | 'pausada' | 'cancelada'
export type StatusConta = 'pendente' | 'paga' | 'atrasada' | 'cancelada'
export type TipoAgendamento = 'diario' | 'semanal' | 'mensal'

// User
export interface Usuario {
  id: number
  nome: string
  email: string
  whatsapp?: string
  ativo: boolean
  criado_em: string
}

export interface UsuarioCriar {
  nome: string
  email: string
  senha: string
  whatsapp?: string
}

export interface UsuarioAtualizar {
  nome?: string
  email?: string
  whatsapp?: string
}

// Auth
export interface LoginRequest {
  email: string
  senha: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

// Category
export interface Categoria {
  id: number
  usuario_id?: number
  nome: string
  tipo: TipoTransacao
  cor: string
  icone: string
  padrao: boolean
  criado_em: string
}

export interface CategoriaCriar {
  nome: string
  tipo: TipoTransacao
  cor?: string
  icone?: string
}

export interface CategoriaAtualizar {
  nome?: string
  cor?: string
  icone?: string
}

// Transaction
export interface Transacao {
  id: number
  codigo: string
  usuario_id: number
  categoria_id?: number
  membro_familia_id?: number
  recorrencia_id?: number
  tipo: TipoTransacao
  valor: number
  descricao?: string
  data_transacao: string
  status: StatusTransacao
  origem: OrigemRegistro
  mensagem_original?: string
  arquivo_url?: string
  confianca_ia?: number
  categoria?: Categoria
  criado_em: string
  atualizado_em: string
}

export interface TransacaoCriar {
  tipo: TipoTransacao
  valor: number
  descricao?: string
  data_transacao: string
  categoria_id?: number
  origem?: OrigemRegistro
}

export interface TransacaoAtualizar {
  tipo?: TipoTransacao
  valor?: number
  descricao?: string
  data_transacao?: string
  categoria_id?: number
  status?: StatusTransacao
}

export interface TransacaoFiltros {
  tipo?: TipoTransacao
  categoria_id?: number
  data_inicio?: string
  data_fim?: string
  skip?: number
  limit?: number
}

// Dashboard
export interface ResumoPeriodo {
  total_receitas: number
  total_despesas: number
  saldo: number
  quantidade_receitas: number
  quantidade_despesas: number
}

export interface ResumoCategoria {
  categoria_id: number
  categoria_nome: string
  categoria_icone: string
  categoria_cor: string
  total: number
  quantidade: number
  percentual: number
}

export interface EvolucaoMensal {
  mes: string
  receitas: number
  despesas: number
  saldo: number
}

export interface DashboardData {
  periodo: string
  resumo_geral: ResumoPeriodo
  receitas_por_categoria: ResumoCategoria[]
  despesas_por_categoria: ResumoCategoria[]
  ultimas_transacoes: Transacao[]
  evolucao_mensal: EvolucaoMensal[]
}

// Family
export interface MembroFamilia {
  id: number
  usuario_id: number
  nome: string
  whatsapp: string
  ativo: boolean
  criado_em: string
}

export interface MembroFamiliaCriar {
  nome: string
  whatsapp: string
}

export interface MembroFamiliaAtualizar {
  nome?: string
  whatsapp?: string
}

// Preferences
export interface UserPreferences {
  id: number
  usuario_id: number
  personalidade: PersonalidadeIA
  alertar_vencimentos: boolean
  dias_antes_vencimento: number
  alertar_gastos_anomalos: boolean
  limite_anomalia_percentual: number
  resumo_diario: boolean
  resumo_semanal: boolean
  resumo_mensal: boolean
  horario_resumo: string
  timezone: string
  auto_confirmar_confianca: number
}

export interface UserPreferencesAtualizar {
  personalidade?: PersonalidadeIA
  alertar_vencimentos?: boolean
  dias_antes_vencimento?: number
  alertar_gastos_anomalos?: boolean
  limite_anomalia_percentual?: number
  resumo_diario?: boolean
  resumo_semanal?: boolean
  resumo_mensal?: boolean
  horario_resumo?: string
  auto_confirmar_confianca?: number
}

// Recurrence
export interface RecurringTransaction {
  id: number
  usuario_id: number
  categoria_id?: number
  descricao_padrao: string
  tipo: TipoTransacao
  valor_medio: number
  valor_minimo: number
  valor_maximo: number
  frequencia: FrequenciaRecorrencia
  dia_mes?: number
  dia_semana?: number
  status: StatusRecorrencia
  auto_confirmar: boolean
  ocorrencias: number
  ultima_ocorrencia?: string
  proxima_esperada?: string
  detectada_automaticamente: boolean
  confianca_deteccao: number
  categoria?: Categoria
  criado_em: string
  atualizado_em: string
}

export interface RecurringTransactionCriar {
  descricao_padrao: string
  tipo: TipoTransacao
  valor_medio: number
  frequencia: FrequenciaRecorrencia
  dia_mes?: number
  dia_semana?: number
  categoria_id?: number
  auto_confirmar?: boolean
}

// Scheduled Bills
export interface ScheduledBill {
  id: number
  usuario_id: number
  categoria_id?: number
  recorrencia_id?: number
  descricao: string
  valor: number
  tipo: TipoTransacao
  data_vencimento: string
  data_pagamento?: string
  status: StatusConta
  alerta_enviado: boolean
  dias_antecedencia_alerta: number
  transacao_id?: number
  criado_em: string
  atualizado_em: string
}

// Schedule
export interface Agendamento {
  id: number
  usuario_id: number
  tipo: TipoAgendamento
  hora: string
  dia_semana?: number
  dia_mes?: number
  ativo: boolean
  criado_em: string
  atualizado_em: string
}

export interface AgendamentoCriar {
  tipo: TipoAgendamento
  hora: string
  dia_semana?: number
  dia_mes?: number
  ativo?: boolean
}

// Alerts
export interface ContaVencer {
  id: number
  descricao: string
  valor: number
  data_vencimento: string
  dias_restantes: number
  categoria?: string
  icone?: string
}

export interface Anomalia {
  categoria_id: number
  categoria: string
  icone: string
  media_historica: number
  gasto_atual: number
  percentual_acima: number
  diferenca: number
}

// Patterns
export interface UserPattern {
  id: number
  usuario_id: number
  categoria_id: number
  palavras_chave: string
  tipo: TipoTransacao
  ocorrencias: number
  confianca: number
  categoria?: Categoria
  criado_em: string
}

// Recurrence Forecast
export interface RecurrenceForecast {
  mes: number
  ano: number
  receitas_previstas: number
  despesas_previstas: number
  saldo_previsto: number
  itens: RecurrenceForecastItem[]
}

export interface RecurrenceForecastItem {
  recorrencia_id: number
  descricao: string
  tipo: TipoTransacao
  valor: number
  data_prevista: string
  categoria?: string
}

// Recurrence Summary
export interface RecurrenceSummary {
  total_recorrencias: number
  receitas_mensais: number
  despesas_mensais: number
  saldo_mensal: number
  por_frequencia: Record<FrequenciaRecorrencia, number>
}

// Recurrence Balance
export interface RecurrenceBalance {
  receitas_fixas: number
  despesas_fixas: number
  saldo_fixo: number
  percentual_comprometido: number
}

// Alert Summaries
export interface AlertSummary {
  periodo: string
  total_receitas: number
  total_despesas: number
  saldo: number
  quantidade_transacoes: number
  principais_categorias: AlertCategorySummary[]
}

export interface AlertCategorySummary {
  categoria: string
  total: number
  percentual: number
}

// Verification Result
export interface VerificationResult {
  success: boolean
  job_id?: string
  message: string
}

// API Response Types
export interface ApiError {
  detail: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}
