# KAIRIX FINANCEIRO - Plano de Redesign Completo

## Visao do Produto

**Missao:** Criar um assistente financeiro verdadeiramente inteligente e proativo, onde o WhatsApp e o canal principal e o usuario nao precisa pensar - apenas enviar informacoes de qualquer jeito.

**Diferenciais:**
- IA que ENTENDE contexto, nao apenas comandos
- Aprende padroes do usuario automaticamente
- Proativo: alerta, sugere, previne problemas
- Minimalista: zero fricao, direto ao ponto

---

## Decisoes de Produto

| Aspecto | Decisao |
|---------|---------|
| Publico | Flexivel (PF, MEI, Empresa) |
| Canal Principal | WhatsApp first |
| Automacao | Confirmar antes de salvar |
| Recorrencias | Deteccao + Previsao + Alertas |
| Multi-itens | Usuario escolhe (total ou detalhado) |
| Metas | Sistema avancado com objetivos |
| Personalidade IA | Configuravel pelo usuario |
| Storage | MinIO (S3 compatible) |
| Integracoes Futuras | Open Finance, PIX, Planilhas |
| Modelo de Negocio | 100% Pago |

---

## PARTE 1: ARQUITETURA DO AGENTE IA

### 1.1 Arquitetura Multi-Agente

```
                    +-------------------+
                    |   WHATSAPP API    |
                    +--------+----------+
                             |
                             v
                    +-------------------+
                    |   GATEWAY AGENT   |
                    |   (Orquestrador)  |
                    +--------+----------+
                             |
        +--------------------+--------------------+
        |          |          |          |        |
        v          v          v          v        v
   +--------+ +--------+ +--------+ +--------+ +--------+
   |EXTRATOR| |APREND. | | PROA-  | |CONSUL- | |PERSONA-|
   |  AGENT | | AGENT  | | TIVO   | |  TOR   | | LIDADE |
   +--------+ +--------+ +--------+ +--------+ +--------+
```

**Agentes:**

1. **Gateway Agent** - Orquestrador principal
   - Classifica intencao do usuario
   - Roteia para agente especializado
   - Gerencia fluxo de confirmacao

2. **Extractor Agent** - Extrai dados de:
   - Texto livre ("gastei 50 no mercado")
   - Fotos (notas fiscais, comprovantes, QR codes PIX)
   - Audios (transcreve e extrai)
   - PDFs (extratos bancarios)

3. **Learning Agent** - Aprende padroes:
   - Mapeia descricao -> categoria
   - Detecta transacoes recorrentes
   - Preve proximos lancamentos

4. **Proactive Agent** - Alertas automaticos:
   - Contas a vencer (3 dias antes)
   - Gastos acima do normal (30%+)
   - Resumos periodicos

5. **Consultant Agent** - Responde consultas:
   - Saldo atual
   - Gastos por categoria
   - Comparativos

6. **Personality Agent** - Aplica estilo:
   - Formal / Amigavel / Divertido
   - Configurado pelo usuario

### 1.2 Sistema de Memoria

```
+------------------+     +------------------+     +------------------+
|  MEMORIA CURTA   |     |  MEMORIA MEDIA   |     |  MEMORIA LONGA   |
|    (Redis)       |     |    (Redis)       |     |   (PostgreSQL)   |
+------------------+     +------------------+     +------------------+
| - Conversa ativa |     | - Padroes user   |     | - Transacoes     |
| - Contexto pend. |     | - Preferencias   |     | - Historico      |
| TTL: 24h         |     | TTL: 30 dias     |     | Permanente       |
+------------------+     +------------------+     +------------------+
```

### 1.3 Fluxo de Processamento

```
Usuario envia foto de nota fiscal
         |
         v
Gateway detecta: IMAGEM
         |
         v
Extractor processa:
- Detecta: nota fiscal do Supermercado X
- 8 itens totalizando R$ 245,50
         |
         v
Learning sugere:
- Categoria: Alimentacao (95% confianca)
- Historico: usuario compra toda semana neste mercado
         |
         v
Gateway pergunta:
"Nota do Supermercado X - R$ 245,50
 8 itens. Registrar:
 1. Total unico
 2. Cada item separado?"
         |
         v
Usuario: "1"
         |
         v
Salva + Confirma:
"Registrado! R$ 245,50 - Alimentacao
 Codigo: AB12C. Algo errado? Me avisa!"
```

### 1.4 Novas Tabelas para IA

```sql
-- Padroes aprendidos do usuario
user_patterns (
  id, usuario_id, keywords[], merchant_name,
  category_id, occurrences, confidence
)

-- Transacoes recorrentes detectadas
recurring_transactions (
  id, usuario_id, description_pattern,
  frequency, next_expected, average_amount
)

-- Preferencias do usuario
user_preferences (
  id, usuario_id, personality,
  alert_due_bills, alert_spending_anomaly,
  daily_summary, weekly_summary
)

-- Contas agendadas
scheduled_bills (
  id, usuario_id, description, amount,
  due_date, is_recurring, paid
)
```

---

## PARTE 2: MODELO DE DADOS (Novo)

### 2.1 Estrutura Multi-Tenant

```
tenants (empresa/familia)
   |
   +-- tenant_members (usuarios com roles)
   +-- accounts (contas bancarias, carteiras, cartoes)
   +-- categories (hierarquicas: categoria > subcategoria)
   +-- transactions (com status, parcelas, recorrencia)
   +-- recurrences (contas fixas)
   +-- budgets (orcamentos por categoria)
   +-- goals (metas de economia)
   +-- attachments (comprovantes no MinIO)
```

### 2.2 Tabelas Principais

**transactions** - Campos novos:
- `code` - Codigo curto para referencia (ex: TX12AB)
- `status` - pending, confirmed, cancelled, scheduled
- `origin` - whatsapp_text, whatsapp_audio, whatsapp_image, web
- `ai_confidence` - Confianca da IA (0.00-1.00)
- `recurrence_id` - Vinculo com recorrencia
- `installment_number` / `total_installments` - Parcelamento
- `statement_id` - Fatura do cartao

**accounts** - Tipos:
- checking (corrente)
- savings (poupanca)
- wallet (carteira)
- credit_card (com fatura, fechamento, vencimento)
- investment

**budgets** - Orcamentos:
- Por categoria + periodo (mes/trimestre/ano)
- Alert threshold (ex: 80%)
- Auto-calculo de spent_amount

**goals** - Metas:
- target_amount / current_amount
- deadline
- monthly_target calculado

### 2.3 Regras de Negocio

- **RN001:** Todo usuario pode criar ate 3 tenants
- **RN002:** Roles: owner, admin, member, viewer
- **RN003:** Codigo curto em transacoes para facil referencia
- **RN004:** Transferencias geram 2 transacoes (entrada/saida)
- **RN005:** Recorrencias podem auto-confirmar ou apenas lembrar
- **RN006:** Orcamento alerta quando >= threshold
- **RN007:** Auto-categorizacao com confianca minima 0.70

---

## PARTE 3: FRONTEND (Next.js 15 + shadcn)

### 3.1 Stack

- Next.js 15 (App Router)
- Tailwind CSS v4
- shadcn/ui
- TypeScript
- Zustand (estado minimo)
- React Query (data fetching)

### 3.2 Principios de Design

1. **Mobile-first** - WhatsApp e principal, web e consulta
2. **Minimalista** - Zero clutter, so o essencial
3. **Dashboard unico** - Tudo visivel em uma tela
4. **Edicao inline** - Sem modais pesados
5. **Performance** - SSR + cache agressivo

### 3.3 Estrutura de Rotas

```
/                     -> Dashboard (saldo, stats, ultimas transacoes)
/transacoes           -> Lista com filtros e busca
/relatorios           -> Graficos e exportacao
/metas                -> Orcamentos e objetivos
/configuracoes
  /perfil             -> Dados do usuario
  /familia            -> Membros
  /categorias         -> Gerenciar categorias
  /assistente         -> Personalidade da IA
```

### 3.4 Cores do Sistema

```css
--background: #121212        /* Fundo escuro */
--card: #1e1e1e              /* Cards */
--primary: #FF5A5A           /* Vermelho Kairix */
--success: #00D95F           /* Verde Receita */
--danger: #EF4444            /* Vermelho Despesa */
--accent: #0EA5E9            /* Azul Info */
```

### 3.5 Componentes Chave

- `BalanceCard` - Saldo com destaque
- `QuickActions` - Botoes rapidos (+ Receita, - Despesa)
- `TransactionItem` - Com edicao inline
- `FlowChart` - Receita vs Despesa (6 meses)
- `CategoryBreakdown` - Pizza por categoria

---

## PARTE 4: PLANO DE IMPLEMENTACAO (MVPs Incrementais)

> **Estrategia:** Backend IA primeiro, frontend depois
> **Frontend legado:** Manter temporariamente enquanto novo nao esta pronto
> **Entregas:** MVPs incrementais - cada fase entrega algo funcional

---

### MVP 1: Agente Inteligente Basico ✅ CONCLUIDO
**Entrega:** IA que extrai transacoes com confirmacao e aprende padroes

#### Fase 1.1: Estrutura Base
- [x] Criar pasta `backend/services/agents/`
- [x] Criar `base_agent.py` com classe abstrata
- [x] Criar `memory_service.py` (Redis + Postgres)
- [x] Adicionar campo `origin` em transacoes (whatsapp_text, whatsapp_image, web)

#### Fase 1.2: Gateway Agent
- [x] Refatorar `agent.py` atual para `gateway_agent.py`
- [x] Implementar classificacao de intencao (registrar, consultar, configurar)
- [x] Implementar fluxo de confirmacao antes de salvar
- [x] Gerar codigo curto para cada transacao (ex: AB12C)

#### Fase 1.3: Extractor Agent Melhorado
- [x] Mover logica de `llm.py` para `extractor_agent.py`
- [x] Melhorar extracao de texto (valor, descricao, tipo)
- [x] Implementar deteccao de multiplos itens em notas
- [x] Perguntar "total ou detalhado" quando detectar lista

---

### MVP 2: Aprendizado de Padroes ✅ CONCLUIDO
**Entrega:** IA que aprende e sugere categorias automaticamente

#### Fase 2.1: Tabelas de Aprendizado
- [x] Criar tabela `user_patterns` (keywords, categoria, confianca)
- [x] Criar tabela `user_preferences` (personalidade, alertas)

#### Fase 2.2: Learning Agent
- [x] Salvar padrao apos cada transacao confirmada
- [x] Sugerir categoria baseada em historico
- [x] Aumentar confianca conforme uso repetido
- [x] Auto-confirmar quando confianca > 90%

#### Fase 2.3: Personality Agent
- [x] Criar endpoint `/api/auth/preferences`
- [x] Implementar 3 personalidades (formal, amigavel, divertido)
- [x] Aplicar estilo nas respostas

---

### MVP 3: Deteccao de Recorrencias ✅ CONCLUIDO
**Entrega:** IA que detecta e preve contas fixas

#### Fase 3.1: Tabelas de Recorrencia
- [x] Criar tabela `recurring_transactions`
- [x] Criar tabela `scheduled_bills`

#### Fase 3.2: Deteccao Automatica
- [x] Analisar historico para encontrar padroes (mesmo valor, mesma data)
- [x] Sugerir criar recorrencia quando detectar
- [x] Prever proxima ocorrencia

#### Fase 3.3: Consultas de Recorrencia
- [x] Consultant Agent: "quais minhas contas fixas?"
- [x] Listar recorrencias detectadas
- [x] Mostrar previsao do mes

---

### MVP 4: Alertas Proativos ✅ CONCLUIDO
**Entrega:** Sistema que avisa antes de vencer/gastar demais

#### Fase 4.1: Scheduler Service
- [x] Configurar arq worker (substituiu APScheduler)
- [x] Job para verificar contas a vencer (diario)
- [x] Job para verificar anomalias (diario)

#### Fase 4.2: Proactive Agent
- [x] Alertar 3 dias antes do vencimento
- [x] Alertar no dia do vencimento
- [x] Detectar gasto 30% acima da media
- [x] Enviar via WhatsApp

#### Fase 4.3: Resumos Automaticos
- [x] Resumo diario (opcional, configuravel)
- [x] Resumo semanal (segunda-feira)
- [x] Resumo mensal (dia 1)

---

### MVP 5: Frontend Next.js ❌ PENDENTE
**Entrega:** Interface web moderna e responsiva

#### Fase 5.1: Setup Projeto
- [ ] Criar projeto Next.js 15
- [ ] Configurar Tailwind v4 + shadcn/ui
- [ ] Configurar estrutura de pastas
- [ ] Cliente API + stores

#### Fase 5.2: Autenticacao
- [ ] Tela de login
- [ ] Tela de cadastro
- [ ] Middleware de protecao

#### Fase 5.3: Dashboard
- [ ] BalanceCard
- [ ] StatsGrid
- [ ] QuickActions
- [ ] RecentTransactions

#### Fase 5.4: Transacoes
- [ ] Lista com filtros
- [ ] Edicao inline
- [ ] Sheet de criacao

#### Fase 5.5: Demais Telas
- [ ] Relatorios
- [ ] Metas
- [ ] Configuracoes

**Teste:** Acessar dashboard, ver saldo, criar transacao
**Resultado esperado:** Experiencia fluida, mobile-first, sem loading excessivo

---

### MVP 6: Integracao Final 🔄 EM ANDAMENTO
**Entrega:** Sistema completo funcionando

#### Fase 6.1: Integracao
- [x] Conectar frontend ao backend (frontend legado)
- [x] Testar todos os fluxos WhatsApp
- [ ] Testar todos os fluxos web (aguardando novo frontend)

#### Fase 6.2: Polish
- [x] Otimizar prompts
- [ ] Ajustar UX (aguardando novo frontend)
- [x] Performance tuning (httpx async, logging)

#### Fase 6.3: Deploy
- [ ] Configurar MinIO para anexos
- [x] Ajustar Docker Compose
- [ ] Documentacao basica

---

## ARQUIVOS IMPLEMENTADOS

### Backend - Agentes ✅
```
backend/services/agents/
├── __init__.py
├── base_agent.py          ✅ Classe abstrata
├── gateway_agent.py       ✅ Orquestrador
├── extractor_agent.py     ✅ Extrai transacoes
├── learning_agent.py      ✅ Aprende padroes
├── proactive_agent.py     ✅ Alertas
├── consultant_agent.py    ✅ Consultas
├── recurrence_agent.py    ✅ Recorrencias
├── personality_agent.py   ✅ Estilo de resposta
└── processor.py           ✅ Ponto de entrada
```

### Backend - Servicos ✅
```
backend/services/
├── __init__.py
├── llm.py                 ✅ Processamento LLM (async httpx)
├── whatsapp.py            ✅ Envio WhatsApp
├── memory_service.py      ✅ Memoria Redis
└── queue_service.py       ✅ Fila arq
```

### Backend - Worker ✅
```
backend/
└── worker.py              ✅ Worker arq com jobs agendados
```

### Frontend - Pendente
- `app/(dashboard)/page.tsx` - Dashboard principal
- `lib/api/client.ts` - Cliente HTTP
- `stores/auth-store.ts` - Autenticacao
- `components/transactions/transaction-item.tsx` - Edicao inline

---

## PROXIMOS PASSOS

1. **MVP 5** - Criar frontend Next.js 15
2. **MVP 6** - Integracao final e deploy

---

*Plano criado em: 10/12/2025*
*Ultima atualizacao: 22/12/2025*
*Versao: 1.1*
