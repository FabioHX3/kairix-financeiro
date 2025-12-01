import os
import json
import re
import base64
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
import requests

from backend.config import settings


class LLMService:
    """Serviço para processar mensagens com LLM, transcrição de áudio e OCR"""

    def __init__(self):
        self.llm_opcao = settings.LLM_OPCAO
        self.ollama_url = settings.OLLAMA_URL
        self.ollama_model = settings.OLLAMA_MODEL
        self.openrouter_api_key = settings.OPENROUTER_API_KEY
        self.openrouter_model = settings.OPENROUTER_MODEL
        self.openai_api_key = settings.OPENAI_API_KEY

    def extrair_transacao_de_texto(self, texto: str, categorias_disponiveis: list) -> Dict:
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
            if self.llm_opcao == 1:
                response = self._chamar_ollama(prompt)
            else:
                response = self._chamar_openrouter(prompt)

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
            print(f"Erro ao processar com LLM: {e}")
            return self._extracao_basica(texto, categorias_disponiveis)

    def _chamar_ollama(self, prompt: str) -> str:
        """Chama API do Ollama"""
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        return response.json()['response']

    def _chamar_openrouter(self, prompt: str, model: str = None) -> str:
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

        response = requests.post(url, headers=headers, json=payload, timeout=30)
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
            return datetime.now()
        elif data_relativa == "ontem":
            return datetime.now() - timedelta(days=1)
        elif data_relativa == "anteontem":
            return datetime.now() - timedelta(days=2)
        else:
            try:
                return datetime.strptime(data_relativa, "%Y-%m-%d")
            except:
                return datetime.now()

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
            "data_transacao": datetime.now(),
            "confianca": 0.3,
            "entendeu": entendeu,
            "pergunta": pergunta
        }

    def transcrever_audio(self, audio_url: str) -> Tuple[str, bool]:
        """Transcreve áudio para texto usando OpenAI Whisper API"""
        if not self.openai_api_key:
            print("[Whisper] OPENAI_API_KEY não configurada")
            return "", False

        try:
            print(f"[Whisper] Baixando áudio de: {audio_url}")
            response = requests.get(audio_url, timeout=30)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name

            try:
                url = "https://api.openai.com/v1/audio/transcriptions"

                headers = {
                    "Authorization": f"Bearer {self.openai_api_key}"
                }

                with open(tmp_path, 'rb') as audio_file:
                    files = {
                        'file': ('audio.ogg', audio_file, 'audio/ogg'),
                    }
                    data = {
                        'model': 'whisper-1',
                        'language': 'pt'
                    }

                    response = requests.post(url, headers=headers, files=files, data=data, timeout=60)

                if response.status_code == 200:
                    texto = response.json().get('text', '')
                    print(f"[Whisper] Transcrição: {texto}")
                    return texto, True
                else:
                    print(f"[Whisper] Erro: {response.status_code} - {response.text}")
                    return "", False

            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            print(f"[Whisper] Erro ao transcrever áudio: {e}")
            return "", False

    def extrair_de_imagem(self, image_url: str, caption: str = "") -> Dict:
        """Extrai informações de nota fiscal/recibo de uma imagem usando GPT-4 Vision"""
        try:
            print(f"[Vision] Baixando imagem de: {image_url}")
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()

            image_base64 = base64.b64encode(response.content).decode('utf-8')

            content_type = response.headers.get('content-type', 'image/jpeg')
            if 'png' in content_type:
                mime_type = 'image/png'
            elif 'webp' in content_type:
                mime_type = 'image/webp'
            else:
                mime_type = 'image/jpeg'

            prompt_texto = f"""Analise esta imagem de um comprovante, nota fiscal ou recibo e extraia as informações financeiras.

{"Contexto adicional do usuário: " + caption if caption else ""}

Retorne APENAS um JSON válido (sem markdown) com:
{{
  "tipo": "despesa" (para compras/pagamentos) ou "receita" (para recebimentos),
  "valor": número decimal do valor total,
  "descricao": "descrição do que foi comprado/recebido",
  "estabelecimento": "nome do estabelecimento se visível",
  "categoria_sugerida": uma dessas categorias: "Alimentação", "Transporte", "Saúde", "Educação", "Lazer", "Casa", "Vestuário", "Outros",
  "data_documento": "YYYY-MM-DD" se visível na imagem ou null,
  "confianca": número de 0 a 1 baseado na clareza da imagem,
  "entendeu": true se conseguiu extrair valor, false se não,
  "pergunta": null se entendeu, ou pergunta de esclarecimento
}}

Se não conseguir ler a imagem claramente, retorne confianca baixa e entendeu: false.
"""

            url = "https://openrouter.ai/api/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_texto},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                "max_tokens": 500
            }

            response = requests.post(url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                resultado = self._parsear_resposta_llm(content)

                if resultado.get('data_documento'):
                    try:
                        resultado['data_transacao'] = datetime.strptime(
                            resultado['data_documento'], "%Y-%m-%d"
                        )
                    except:
                        resultado['data_transacao'] = datetime.now()
                else:
                    resultado['data_transacao'] = datetime.now()

                if resultado.get('estabelecimento') and resultado.get('descricao'):
                    resultado['descricao'] = f"{resultado['descricao']} - {resultado['estabelecimento']}"

                print(f"[Vision] Extração: valor={resultado.get('valor')}, tipo={resultado.get('tipo')}")
                return resultado
            else:
                print(f"[Vision] Erro: {response.status_code} - {response.text}")
                return self._resultado_imagem_erro()

        except Exception as e:
            print(f"[Vision] Erro ao processar imagem: {e}")
            return self._resultado_imagem_erro()

    def _resultado_imagem_erro(self) -> Dict:
        """Retorna resultado padrão quando não consegue processar imagem"""
        return {
            "tipo": "despesa",
            "valor": 0.0,
            "descricao": "Não foi possível ler a imagem",
            "categoria_sugerida": "Outros",
            "data_transacao": datetime.now(),
            "confianca": 0.0,
            "entendeu": False,
            "pergunta": "Não consegui ler a imagem. Pode me dizer o valor e o que foi?"
        }

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
