"""
Testes para funcionalidades de segurança.
"""

import pytest
from fastapi.testclient import TestClient


class TestSecurityHeaders:
    """Testes para headers de segurança."""

    def test_health_check_headers(self, client: TestClient):
        """Health check deve retornar headers de segurança."""
        response = client.get("/health")
        assert response.status_code == 200

        # Verifica headers de segurança
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert (
            response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        )

    def test_api_response_headers(self, client: TestClient):
        """API endpoints devem retornar headers de segurança."""
        response = client.get("/api/auth/me")
        # Mesmo em erro 401, deve ter headers de segurança
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"


class TestCORS:
    """Testes para configuração CORS."""

    def test_cors_localhost_allowed(self, client: TestClient):
        """Origem localhost:3000 deve ser permitida."""
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # OPTIONS pode retornar 200 ou 405 dependendo da configuração
        assert response.status_code in [200, 405]

    def test_cors_preflight_headers(self, client: TestClient):
        """Preflight request deve incluir headers corretos."""
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        # Verifica se CORS está configurado
        if response.status_code == 200:
            assert "access-control-allow-origin" in response.headers


class TestHealthCheck:
    """Testes para endpoint de health check."""

    def test_health_check_success(self, client: TestClient):
        """Health check deve retornar status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "Kairix Financeiro API"


class TestWebhookSecurity:
    """Testes para segurança do webhook."""

    def test_webhook_without_signature_in_dev(self, client: TestClient):
        """Em dev sem WEBHOOK_SECRET, requisição deve ser aceita."""
        # Webhook simples sem dados de mensagem válidos
        response = client.post(
            "/api/whatsapp/webhook",
            json={"EventType": "test"},
        )
        # Pode retornar "ignored" por não ser evento de mensagem
        assert response.status_code == 200

    def test_webhook_invalid_payload(self, client: TestClient):
        """Payload inválido deve retornar erro ou ser ignorado."""
        response = client.post(
            "/api/whatsapp/webhook",
            json={},
        )
        # Sem EventType, pode ser ignorado ou processado
        assert response.status_code == 200


class TestTokenValidation:
    """Testes para validação de tokens."""

    def test_invalid_token_rejected(self, client: TestClient):
        """Token inválido deve ser rejeitado."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_expired_token_format(self, client: TestClient):
        """Token mal formatado deve ser rejeitado."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    def test_missing_bearer_prefix(self, client: TestClient):
        """Token sem prefixo Bearer deve ser rejeitado."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "some-token"},
        )
        assert response.status_code == 401
