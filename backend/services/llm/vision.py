"""
Análise de imagens usando Gemini Vision via OpenRouter.
"""

import base64
import logging
from datetime import UTC, datetime

import httpx

from backend.services.llm.client import OpenRouterClient, parse_llm_response

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """Analisa imagens de documentos financeiros."""

    def __init__(self, client: OpenRouterClient):
        self.client = client

    async def extract_from_url(self, image_url: str, caption: str = "") -> dict:
        """
        Extrai informações de uma imagem via URL.

        Args:
            image_url: URL da imagem
            caption: Legenda/contexto opcional

        Returns:
            Dicionário com dados extraídos
        """
        try:
            logger.debug(f"[Vision] Baixando imagem de: {image_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=30)
                response.raise_for_status()

            image_base64 = base64.b64encode(response.content).decode("utf-8")

            content_type = response.headers.get("content-type", "image/jpeg")
            if "png" in content_type:
                mime_type = "image/png"
            elif "webp" in content_type:
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            return await self.extract_from_base64(image_base64, mime_type, caption)

        except Exception as e:
            logger.error(f"[Vision] Erro ao processar imagem: {e}")
            return self._error_result()

    async def extract_from_base64(
        self,
        base64_data: str,
        mimetype: str = "image/jpeg",
        caption: str = "",
    ) -> dict:
        """
        Extrai informações de uma imagem em base64.

        Args:
            base64_data: Imagem em base64
            mimetype: Tipo MIME da imagem
            caption: Legenda/contexto opcional

        Returns:
            Dicionário com dados extraídos
        """
        try:
            logger.debug(f"[Vision] Processando imagem base64 ({len(base64_data)} chars)")

            prompt = self._get_vision_prompt(caption)

            content = await self.client.call_with_image(
                prompt=prompt,
                image_base64=base64_data,
                mimetype=mimetype,
                max_tokens=1000,
                timeout=60,
            )

            resultado = parse_llm_response(content)

            if resultado.get("data_documento"):
                try:
                    resultado["data_transacao"] = datetime.strptime(
                        resultado["data_documento"], "%Y-%m-%d"
                    ).replace(tzinfo=UTC)
                except ValueError:
                    resultado["data_transacao"] = datetime.now(UTC)
            else:
                resultado["data_transacao"] = datetime.now(UTC)

            logger.debug(
                f"[Vision] Extração: valor={resultado.get('valor')}, tipo={resultado.get('tipo')}"
            )
            return resultado

        except Exception as e:
            logger.error(f"[Vision] Erro ao processar imagem base64: {e}")
            return self._error_result()

    async def extract_statement(
        self,
        base64_data: str,
        mimetype: str = "image/jpeg",
        caption: str = "",
    ) -> dict:
        """
        Extrai MÚLTIPLAS transações de um extrato bancário/fatura.

        Args:
            base64_data: Imagem em base64
            mimetype: Tipo MIME da imagem
            caption: Legenda/contexto opcional

        Returns:
            Dicionário com lista de transações
        """
        try:
            logger.debug(f"[Vision Extrato] Processando extrato ({len(base64_data)} chars)")

            prompt = self._get_statement_prompt(caption)

            content = await self.client.call_with_image(
                prompt=prompt,
                image_base64=base64_data,
                mimetype=mimetype,
                max_tokens=4000,
                timeout=90,
            )

            resultado = parse_llm_response(content)

            # Converte datas
            for t in resultado.get("transacoes", []):
                if t.get("data"):
                    try:
                        t["data_transacao"] = datetime.strptime(t["data"], "%Y-%m-%d").replace(
                            tzinfo=UTC
                        )
                    except ValueError:
                        t["data_transacao"] = datetime.now(UTC)
                else:
                    t["data_transacao"] = datetime.now(UTC)

            logger.info(
                f"[Vision Extrato] Extraídas {len(resultado.get('transacoes', []))} transações"
            )
            return resultado

        except Exception as e:
            logger.error(f"[Vision Extrato] Erro: {e}")
            return {"tipo_documento": "erro", "transacoes": [], "observacoes": str(e)}

    async def extract_from_pdf(self, base64_data: str) -> dict:
        """
        Extrai transações de um PDF de extrato bancário.

        Args:
            base64_data: PDF em base64

        Returns:
            Dicionário com lista de transações
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
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")

                # Processa a imagem da página
                resultado = await self.extract_statement(img_base64, "image/png")

                if resultado.get("transacoes"):
                    todas_transacoes.extend(resultado["transacoes"])

                if not info_documento and resultado.get("banco_ou_emissor"):
                    info_documento = {
                        "tipo_documento": resultado.get("tipo_documento"),
                        "banco_ou_emissor": resultado.get("banco_ou_emissor"),
                        "periodo": resultado.get("periodo"),
                    }

            doc.close()

            logger.info(
                f"[PDF] Total de {len(todas_transacoes)} transações extraídas de {doc.page_count} páginas"
            )

            return {
                **info_documento,
                "transacoes": todas_transacoes,
                "total_transacoes": len(todas_transacoes),
                "paginas_processadas": min(doc.page_count, 5),
            }

        except ImportError:
            logger.warning("[PDF] PyMuPDF não instalado, usando fallback")
            return {
                "tipo_documento": "erro",
                "transacoes": [],
                "observacoes": "Suporte a PDF não disponível",
            }
        except Exception as e:
            logger.error(f"[PDF] Erro: {e}")
            return {"tipo_documento": "erro", "transacoes": [], "observacoes": str(e)}

    def _get_vision_prompt(self, caption: str = "") -> str:
        """Retorna prompt para análise de imagem."""
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

    def _get_statement_prompt(self, caption: str = "") -> str:
        """Retorna prompt para análise de extrato."""
        return f"""Você é um especialista em analisar documentos financeiros.

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

    def _error_result(self) -> dict:
        """Retorna resultado padrão quando não consegue processar imagem."""
        return {
            "tipo": "despesa",
            "valor": 0.0,
            "descricao": "Não foi possível ler a imagem",
            "categoria_sugerida": "Outros",
            "data_transacao": datetime.now(UTC),
            "confianca": 0.0,
            "entendeu": False,
            "pergunta": "Não consegui ler a imagem. Pode me dizer o valor e o que foi?",
        }
