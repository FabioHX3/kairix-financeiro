"""
LLM Service - Processamento com OpenRouter (Gemini)

Funções:
- Extração de transações de texto
- Transcrição de áudio (Gemini)
- Extração de dados de imagens (Gemini Vision)
- Extração de extratos/faturas
"""

import json
import logging
import re
import base64
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
from typing import Dict, Tuple
import httpx

from backend.config import settings


class LLMService:
    """Serviço para processar mensagens com LLM via OpenRouter"""

    def __init__(self):
        self.openrouter_api_key = settings.OPENROUTER_API_KEY
        self.openrouter_model = settings.OPENROUTER_MODEL

    async def _chamar_openrouter(self, prompt: str, model: str = None) -> str:
        """Chama API do OpenRouter"""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model or self.openrouter_model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

        return response.json()['choices'][0]['message']['content']

    def _parsear_resposta_llm(self, response: str) -> Dict:
        """Parseia a resposta do LLM removendo markdown se necessário"""
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        response = response.strip()

        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            response = json_match.group()

        return json.loads(response)

    def _converter_data_relativa(self, data_relativa: str) -> datetime:
        """Converte data relativa em datetime"""
        if not data_relativa or data_relativa == "hoje":
            return datetime.now(timezone.utc)
        elif data_relativa == "ontem":
            return datetime.now(timezone.utc) - timedelta(days=1)
        elif data_relativa == "anteontem":
            return datetime.now(timezone.utc) - timedelta(days=2)
        else:
            try:
                return datetime.strptime(data_relativa, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return datetime.now(timezone.utc)

    # =========================================================================
    # EXTRAÇÃO DE TEXTO
    # =========================================================================

    async def extrair_transacao_de_texto(self, texto: str, categorias_disponiveis: list) -> Dict:
        """Extrai informações de transação financeira de um texto usando LLM"""

        cats_receitas = [c for c in categorias_disponiveis if c['tipo'] == 'receita']
        cats_despesas = [c for c in categorias_disponiveis if c['tipo'] == 'despesa']

        categorias_texto = "RECEITAS: " + ", ".join([f"{c['nome']}" for c in cats_receitas])
        categorias_texto += "\nDESPESAS: " + ", ".join([f"{c['nome']}" for c in cats_despesas])

        prompt = f"""Você é um assistente financeiro brasileiro especializado em extrair informações de transações financeiras de mensagens informais.

Analise a seguinte mensagem do usuário e extraia as informações financeiras:
"{texto}"

Categorias disponíveis no sistema:
{categorias_texto}

IMPORTANTE: Retorne APENAS um JSON válido (sem markdown, sem explicações, sem ```json```) com esta estrutura:
{{
  "tipo": "receita" ou "despesa",
  "valor": número decimal (ex: 150.50),
  "descricao": "descrição clara e curta da transação",
  "categoria_sugerida": "nome exato de uma das categorias disponíveis acima",
  "data_relativa": "hoje", "ontem", ou data no formato "YYYY-MM-DD",
  "confianca": número de 0 a 1,
  "entendeu": true ou false,
  "pergunta": "pergunta para o usuário se não entendeu algo" ou null
}}

REGRAS DE CLASSIFICAÇÃO:
- Palavras como "gastei", "paguei", "comprei", "despesa", "conta", "boleto" = DESPESA
- Palavras como "recebi", "ganhei", "entrou", "salário", "pagamento", "vendi" = RECEITA
- Valor sempre POSITIVO (apenas números)
- Se a data não for mencionada, use "hoje"
- Escolha a categoria mais adequada da lista acima

REGRAS DE CONFIANÇA:
- confianca >= 0.8: Informações claras e completas
- confianca 0.5-0.7: Algumas informações ambíguas
- confianca < 0.5: Muita ambiguidade, precisa confirmar
- entendeu = false: Não conseguiu extrair informações essenciais (valor ou tipo)

REGRAS DE PERGUNTA:
- Se não encontrar o VALOR, pergunte: "Qual foi o valor?"
- Se não souber se é receita ou despesa, pergunte: "Isso foi um gasto ou um recebimento?"
- Se encontrou tudo claramente, pergunta deve ser null

Exemplos:
- "gastei 50 no almoço" → tipo: despesa, valor: 50, categoria: Alimentação, confianca: 0.95
- "recebi 1500 de salário" → tipo: receita, valor: 1500, categoria: Salário, confianca: 0.95
- "comprei umas coisas" → entendeu: false, pergunta: "Qual foi o valor da compra?"
- "150 reais" → entendeu: false, pergunta: "Isso foi um gasto ou um recebimento?"
"""

        try:
            response = await self._chamar_openrouter(prompt)
            resultado = self._parsear_resposta_llm(response)

            resultado['data_transacao'] = self._converter_data_relativa(
                resultado.get('data_relativa', 'hoje')
            )

            if 'entendeu' not in resultado:
                resultado['entendeu'] = resultado.get('confianca', 0) >= 0.5
            if 'pergunta' not in resultado:
                resultado['pergunta'] = None

            return resultado

        except Exception as e:
            logger.error(f"Erro ao processar com LLM: {e}")
            return self._extracao_basica(texto, categorias_disponiveis)

    def _extracao_basica(self, texto: str, categorias_disponiveis: list) -> Dict:
        """Extração básica sem LLM como fallback"""

        padroes_valor = [
            r'R?\$?\s*(\d+(?:[.,]\d{1,2})?)',
            r'(\d+(?:[.,]\d{1,2})?)\s*(?:reais?|conto|pila)',
        ]

        valor = 0.0
        for padrao in padroes_valor:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                valor_str = match.group(1).replace(',', '.')
                valor = float(valor_str)
                break

        palavras_receita = ['recebi', 'recebimento', 'ganho', 'ganhei', 'salário', 'salario',
                          'pagamento recebido', 'entrou', 'vendi', 'vendeu']
        palavras_despesa = ['gastei', 'paguei', 'comprei', 'despesa', 'gasto', 'conta',
                          'boleto', 'pagar', 'comprar', 'gastar']

        tipo = None
        for palavra in palavras_receita:
            if palavra in texto.lower():
                tipo = "receita"
                break

        if not tipo:
            for palavra in palavras_despesa:
                if palavra in texto.lower():
                    tipo = "despesa"
                    break

        entendeu = True
        pergunta = None

        if valor == 0:
            entendeu = False
            pergunta = "Qual foi o valor?"
        elif not tipo:
            entendeu = False
            pergunta = "Isso foi um gasto ou um recebimento?"
            tipo = "despesa"

        return {
            "tipo": tipo or "despesa",
            "valor": valor,
            "descricao": texto[:200],
            "categoria_sugerida": "Outros",
            "data_transacao": datetime.now(timezone.utc),
            "confianca": 0.3,
            "entendeu": entendeu,
            "pergunta": pergunta
        }

    # =========================================================================
    # TRANSCRIÇÃO DE ÁUDIO (Gemini)
    # =========================================================================

    async def transcrever_audio(self, audio_url: str) -> Tuple[str, bool]:
        """Transcreve áudio para texto usando Gemini via OpenRouter"""
        if not self.openrouter_api_key:
            logger.warning("[Audio] OPENROUTER_API_KEY não configurada")
            return "", False

        try:
            logger.debug(f"[Audio] Baixando áudio de: {audio_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url, timeout=30)
                response.raise_for_status()

            audio_base64 = base64.b64encode(response.content).decode('utf-8')

            # Detecta formato do áudio
            content_type = response.headers.get('content-type', 'audio/ogg')
            if 'mp3' in content_type or 'mpeg' in content_type:
                audio_format = 'mp3'
            elif 'wav' in content_type:
                audio_format = 'wav'
            elif 'mp4' in content_type or 'm4a' in content_type:
                audio_format = 'mp4'
            else:
                audio_format = 'ogg'

            return await self._transcrever_com_gemini(audio_base64, audio_format)

        except Exception as e:
            logger.error(f"[Audio] Erro: {e}")
            return "", False

    async def transcrever_audio_base64(self, base64_data: str, mimetype: str = "audio/ogg") -> Tuple[str, bool]:
        """Transcreve áudio a partir de base64 usando Gemini via OpenRouter"""
        if not self.openrouter_api_key:
            logger.warning("[Audio] OPENROUTER_API_KEY não configurada")
            return "", False

        # Extrai formato do mimetype
        if 'mp3' in mimetype or 'mpeg' in mimetype:
            audio_format = 'mp3'
        elif 'wav' in mimetype:
            audio_format = 'wav'
        elif 'mp4' in mimetype or 'm4a' in mimetype:
            audio_format = 'mp4'
        elif 'webm' in mimetype:
            audio_format = 'webm'
        else:
            audio_format = 'ogg'

        return await self._transcrever_com_gemini(base64_data, audio_format)

    async def _transcrever_com_gemini(self, audio_base64: str, audio_format: str = "ogg") -> Tuple[str, bool]:
        """Transcreve áudio usando Gemini via OpenRouter"""
        try:
            logger.debug(f"[Audio] Transcrevendo áudio ({audio_format}, {len(audio_base64)} chars)")

            url = "https://openrouter.ai/api/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.openrouter_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Transcreva este áudio em português brasileiro.
Retorne APENAS o texto transcrito, sem explicações ou formatação adicional.
Se o áudio estiver inaudível ou vazio, retorne: [INAUDÍVEL]"""
                            },
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_base64,
                                    "format": audio_format
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }

            logger.debug(f"[Audio] Usando modelo: {self.openrouter_model}")

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                texto = response.json()['choices'][0]['message']['content'].strip()
                logger.debug(f"[Audio] Transcrição: {texto[:100]}...")
                if texto and texto != "[INAUDÍVEL]":
                    return texto, True
                else:
                    logger.warning("[Audio] Áudio inaudível")
                    return "", False
            else:
                logger.error(f"[Audio] Erro: {response.status_code} - {response.text[:200]}")
                return "", False

        except Exception as e:
            logger.error(f"[Audio] Erro ao transcrever: {e}")
            return "", False

    # =========================================================================
    # EXTRAÇÃO DE IMAGEM (Gemini Vision)
    # =========================================================================

    async def extrair_de_imagem(self, image_url: str, caption: str = "") -> Dict:
        """Extrai informações de nota fiscal/recibo de uma imagem"""
        try:
            logger.debug(f"[Vision] Baixando imagem de: {image_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=30)
                response.raise_for_status()

            image_base64 = base64.b64encode(response.content).decode('utf-8')

            content_type = response.headers.get('content-type', 'image/jpeg')
            if 'png' in content_type:
                mime_type = 'image/png'
            elif 'webp' in content_type:
                mime_type = 'image/webp'
            else:
                mime_type = 'image/jpeg'

            return await self.extrair_de_imagem_base64(image_base64, mime_type, caption)

        except Exception as e:
            logger.error(f"[Vision] Erro ao processar imagem: {e}")
            return self._resultado_imagem_erro()

    async def extrair_de_imagem_base64(self, base64_data: str, mimetype: str = "image/jpeg", caption: str = "") -> Dict:
        """Extrai informações de imagem a partir de base64"""
        try:
            logger.debug(f"[Vision] Processando imagem base64 ({len(base64_data)} chars)")

            prompt_texto = self._get_prompt_visao(caption)

            url = "https://openrouter.ai/api/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.openrouter_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_texto},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mimetype};base64,{base64_data}"}
                            }
                        ]
                    }
                ],
                "max_tokens": 1000
            }

            logger.debug(f"[Vision] Usando modelo: {self.openrouter_model}")

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                resultado = self._parsear_resposta_llm(content)

                if resultado.get('data_documento'):
                    try:
                        resultado['data_transacao'] = datetime.strptime(
                            resultado['data_documento'], "%Y-%m-%d"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        resultado['data_transacao'] = datetime.now(timezone.utc)
                else:
                    resultado['data_transacao'] = datetime.now(timezone.utc)

                logger.debug(f"[Vision] Extração: valor={resultado.get('valor')}, tipo={resultado.get('tipo')}")
                return resultado
            else:
                logger.error(f"[Vision] Erro: {response.status_code} - {response.text}")
                return self._resultado_imagem_erro()

        except Exception as e:
            logger.error(f"[Vision] Erro ao processar imagem base64: {e}")
            return self._resultado_imagem_erro()

    def _get_prompt_visao(self, caption: str = "") -> str:
        """Retorna o prompt padrão para análise de imagem"""
        return f"""Você é um assistente financeiro especializado em analisar imagens de documentos financeiros.

Analise esta imagem cuidadosamente. Pode ser:
- Nota fiscal / cupom fiscal
- Comprovante de pagamento (PIX, cartão, transferência)
- Recibo
- Boleto
- Extrato bancário
- Qualquer documento com informação financeira
- Ou uma imagem comum (foto, print, etc.)

{"O usuário disse: " + caption if caption else ""}

INSTRUÇÕES:
1. Se conseguir identificar um documento financeiro com valor claro, extraia os dados
2. Se a imagem estiver borrada, cortada ou ilegível, pergunte ao usuário
3. Se for uma imagem comum (não financeira), pergunte o que o usuário deseja registrar
4. Se tiver múltiplos valores, pergunte qual é o valor principal

Retorne APENAS um JSON válido (sem markdown, sem ```):
{{
  "entendeu": true ou false,
  "tipo": "despesa" ou "receita" (se entendeu),
  "valor": número decimal do valor total (se entendeu),
  "descricao": "descrição clara do que foi comprado/pago",
  "estabelecimento": "nome do estabelecimento se visível",
  "categoria_sugerida": "Alimentação", "Transporte", "Combustível", "Saúde", "Educação", "Lazer", "Casa", "Vestuário", "Mercado", "Restaurante", "Farmácia" ou "Outros",
  "data_documento": "YYYY-MM-DD" se visível ou null,
  "confianca": número de 0.0 a 1.0 baseado na clareza,
  "pergunta": null se entendeu tudo, ou "sua pergunta aqui" se precisar de esclarecimento,
  "observacoes": "detalhes extras que notou na imagem"
}}

IMPORTANTE: Se não entendeu ou precisa de mais informações, coloque entendeu: false e faça uma pergunta clara e amigável.
"""

    def _resultado_imagem_erro(self) -> Dict:
        """Retorna resultado padrão quando não consegue processar imagem"""
        return {
            "tipo": "despesa",
            "valor": 0.0,
            "descricao": "Não foi possível ler a imagem",
            "categoria_sugerida": "Outros",
            "data_transacao": datetime.now(timezone.utc),
            "confianca": 0.0,
            "entendeu": False,
            "pergunta": "Não consegui ler a imagem. Pode me dizer o valor e o que foi?"
        }

    # =========================================================================
    # EXTRAÇÃO DE EXTRATO/FATURA
    # =========================================================================

    async def extrair_extrato_multiplo(self, base64_data: str, mimetype: str = "image/jpeg", caption: str = "") -> Dict:
        """
        Extrai MÚLTIPLAS transações de um extrato bancário/fatura.
        Retorna lista de transações para registro em lote.
        """
        try:
            logger.debug(f"[Vision Extrato] Processando extrato ({len(base64_data)} chars)")

            prompt = f"""Você é um especialista em analisar documentos financeiros.

Analise esta imagem e identifique o tipo de documento.

{"Contexto do usuário: " + caption if caption else ""}

TIPOS DE DOCUMENTO:
1. "extrato_bancario" - Extrato de conta corrente com múltiplas transações
2. "fatura_cartao" - Fatura de cartão de crédito
3. "documento_fiscal" - DAS, DARF, Simples Nacional, guias de impostos, notas fiscais
4. "comprovante" - Comprovante de pagamento único (PIX, transferência)
5. "outro" - Outros documentos

REGRAS IMPORTANTES:
- Para EXTRATO/FATURA: extraia cada transação individualmente
- Para DOCUMENTO FISCAL (DAS, Simples Nacional, DARF, guias): NÃO quebre em itens, retorne valor_total único
- Para COMPROVANTE único: retorne como transação única

Retorne APENAS um JSON válido (sem markdown):
{{
  "tipo_documento": "extrato_bancario" | "fatura_cartao" | "documento_fiscal" | "comprovante" | "outro",
  "banco_ou_emissor": "nome do banco/órgão emissor",
  "periodo": "período/competência se visível",
  "valor_total": número (para documento_fiscal ou comprovante),
  "descricao_documento": "descrição do documento fiscal",
  "data_vencimento": "YYYY-MM-DD" se visível,
  "transacoes": [
    {{
      "data": "YYYY-MM-DD",
      "descricao": "descrição da transação",
      "valor": número positivo,
      "tipo": "despesa" ou "receita",
      "categoria_sugerida": "categoria"
    }}
  ],
  "observacoes": "observações"
}}

CATEGORIAS:
- Impostos/DAS/Simples Nacional/DARF: "Impostos"
- PIX/Transferência: "Transferência"
- Uber/99: "Transporte"
- Alimentação/restaurante: "Alimentação"
- Mercado: "Mercado"
- Outros: "Outros"

Para documento fiscal, retorne transacoes vazio e preencha valor_total e descricao_documento.
"""

            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.openrouter_model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mimetype};base64,{base64_data}"}
                        }
                    ]
                }],
                "max_tokens": 4000  # Mais tokens para extratos longos
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=90)

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                resultado = self._parsear_resposta_llm(content)

                # Converte datas
                for t in resultado.get('transacoes', []):
                    if t.get('data'):
                        try:
                            t['data_transacao'] = datetime.strptime(t['data'], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        except ValueError:
                            t['data_transacao'] = datetime.now(timezone.utc)
                    else:
                        t['data_transacao'] = datetime.now(timezone.utc)

                logger.info(f"[Vision Extrato] Extraídas {len(resultado.get('transacoes', []))} transações")
                return resultado
            else:
                logger.error(f"[Vision Extrato] Erro: {response.status_code}")
                return {"tipo_documento": "erro", "transacoes": [], "observacoes": "Erro ao processar"}

        except Exception as e:
            logger.error(f"[Vision Extrato] Erro: {e}")
            return {"tipo_documento": "erro", "transacoes": [], "observacoes": str(e)}

    async def extrair_de_pdf_base64(self, base64_data: str) -> Dict:
        """
        Extrai transações de um PDF de extrato bancário.
        Converte PDF para imagens e processa cada página.
        """
        try:
            import fitz  # PyMuPDF

            logger.debug(f"[PDF] Processando PDF ({len(base64_data)} chars)")

            # Decodifica base64 para bytes
            pdf_bytes = base64.b64decode(base64_data)

            # Abre o PDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            todas_transacoes = []
            info_documento = {}

            for page_num in range(min(doc.page_count, 5)):  # Máximo 5 páginas
                page = doc[page_num]

                # Converte página para imagem
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom para melhor qualidade
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                # Processa a imagem da página
                resultado = await self.extrair_extrato_multiplo(img_base64, "image/png")

                if resultado.get('transacoes'):
                    todas_transacoes.extend(resultado['transacoes'])

                if not info_documento and resultado.get('banco_ou_emissor'):
                    info_documento = {
                        'tipo_documento': resultado.get('tipo_documento'),
                        'banco_ou_emissor': resultado.get('banco_ou_emissor'),
                        'periodo': resultado.get('periodo')
                    }

            doc.close()

            logger.info(f"[PDF] Total de {len(todas_transacoes)} transações extraídas de {doc.page_count} páginas")

            return {
                **info_documento,
                'transacoes': todas_transacoes,
                'total_transacoes': len(todas_transacoes),
                'paginas_processadas': min(doc.page_count, 5)
            }

        except ImportError:
            logger.warning("[PDF] PyMuPDF não instalado, usando fallback")
            return {"tipo_documento": "erro", "transacoes": [], "observacoes": "Suporte a PDF não disponível"}
        except Exception as e:
            logger.error(f"[PDF] Erro: {e}")
            return {"tipo_documento": "erro", "transacoes": [], "observacoes": str(e)}

    # =========================================================================
    # MENSAGENS AUXILIARES
    # =========================================================================

    def gerar_mensagem_confirmacao(self, transacao_info: Dict, transacao_id: int = None) -> str:
        """Gera mensagem de confirmação para enviar ao usuário"""
        tipo_emoji = "💸" if transacao_info['tipo'] == 'despesa' else "💰"
        tipo_texto = "Despesa" if transacao_info['tipo'] == 'despesa' else "Receita"

        valor = transacao_info.get('valor', 0)
        descricao = transacao_info.get('descricao', 'Sem descrição')
        categoria = transacao_info.get('categoria_sugerida', 'Outros')

        mensagem = f"""{tipo_emoji} *{tipo_texto} registrada!*

💵 *Valor:* R$ {valor:.2f}
📝 *Descrição:* {descricao}
🏷️ *Categoria:* {categoria}

✅ Está correto? Responda:
• *SIM* para confirmar
• *CORRIGIR* para editar
• Ou envie nova transação"""

        return mensagem

    def gerar_pergunta_esclarecimento(self, pergunta: str) -> str:
        """Gera mensagem de pergunta quando não entendeu algo"""
        return f"""🤔 *Preciso de uma informação*

{pergunta}

Por favor, responda para eu registrar corretamente."""

    def gerar_mensagem_erro(self) -> str:
        """Gera mensagem de erro genérica"""
        return """❌ *Ops! Algo deu errado*

Não consegui processar sua mensagem. Por favor, tente novamente.

💡 *Dica:* Envie mensagens como:
• "Gastei 50 reais no almoço"
• "Recebi 1500 de salário"
• Foto de nota fiscal"""


# Instância global
llm_service = LLMService()
