"""
Testes para rotas de autenticação.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.models import Usuario


class TestCadastro:
    """Testes para endpoint de cadastro."""

    def test_cadastro_sucesso(self, client: TestClient, db: Session):
        """Cadastro com dados válidos deve criar usuário."""
        response = client.post(
            "/api/auth/cadastro",
            json={
                "nome": "Novo Usuario",
                "email": "novo@example.com",
                "senha": "SenhaForte123",
                "whatsapp": "11987654321",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["nome"] == "Novo Usuario"
        assert data["email"] == "novo@example.com"
        assert data["whatsapp"] == "11987654321"
        assert "senha" not in data
        assert "senha_hash" not in data

    def test_cadastro_email_duplicado(
        self, client: TestClient, db: Session, test_user: Usuario
    ):
        """Cadastro com email existente deve falhar."""
        response = client.post(
            "/api/auth/cadastro",
            json={
                "nome": "Outro Usuario",
                "email": test_user.email,
                "senha": "SenhaForte123",
            },
        )
        assert response.status_code == 400
        assert "Email já cadastrado" in response.json()["detail"]

    def test_cadastro_whatsapp_duplicado(
        self, client: TestClient, db: Session, test_user: Usuario
    ):
        """Cadastro com WhatsApp existente deve falhar."""
        response = client.post(
            "/api/auth/cadastro",
            json={
                "nome": "Outro Usuario",
                "email": "outro@example.com",
                "senha": "SenhaForte123",
                "whatsapp": test_user.whatsapp,
            },
        )
        assert response.status_code == 400
        assert "WhatsApp já cadastrado" in response.json()["detail"]

    def test_cadastro_senha_fraca(self, client: TestClient, db: Session):
        """Cadastro com senha fraca deve falhar."""
        # Senha muito curta
        response = client.post(
            "/api/auth/cadastro",
            json={
                "nome": "Usuario",
                "email": "user@example.com",
                "senha": "abc123",
            },
        )
        assert response.status_code == 422

    def test_cadastro_senha_sem_maiuscula(self, client: TestClient, db: Session):
        """Senha sem letra maiúscula deve falhar."""
        response = client.post(
            "/api/auth/cadastro",
            json={
                "nome": "Usuario",
                "email": "user@example.com",
                "senha": "senhafraca123",
            },
        )
        assert response.status_code == 422

    def test_cadastro_senha_sem_numero(self, client: TestClient, db: Session):
        """Senha sem número deve falhar."""
        response = client.post(
            "/api/auth/cadastro",
            json={
                "nome": "Usuario",
                "email": "user@example.com",
                "senha": "SenhaFraca",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """Testes para endpoint de login."""

    def test_login_sucesso(self, client: TestClient, test_user: Usuario):
        """Login com credenciais válidas deve retornar token."""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "senha": "TestPass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_login_email_invalido(self, client: TestClient, test_user: Usuario):
        """Login com email inválido deve falhar."""
        response = client.post(
            "/api/auth/login",
            json={"email": "naoexiste@example.com", "senha": "TestPass123"},
        )
        assert response.status_code == 401
        assert "Email ou senha incorretos" in response.json()["detail"]

    def test_login_senha_invalida(self, client: TestClient, test_user: Usuario):
        """Login com senha inválida deve falhar."""
        response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "senha": "SenhaErrada123"},
        )
        assert response.status_code == 401
        assert "Email ou senha incorretos" in response.json()["detail"]

    def test_login_usuario_inativo(self, client: TestClient, inactive_user: Usuario):
        """Login de usuário inativo deve falhar."""
        response = client.post(
            "/api/auth/login",
            json={"email": "inactive@example.com", "senha": "TestPass123"},
        )
        assert response.status_code == 401


class TestMe:
    """Testes para endpoint /me."""

    def test_me_autenticado(
        self, client: TestClient, test_user: Usuario, auth_headers: dict
    ):
        """Usuário autenticado deve ver seus dados."""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["nome"] == test_user.nome

    def test_me_nao_autenticado(self, client: TestClient):
        """Requisição sem token deve falhar."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401


class TestLogout:
    """Testes para endpoint de logout."""

    def test_logout_sucesso(self, client: TestClient, test_user: Usuario):
        """Logout deve retornar sucesso."""
        # Primeiro faz login
        login_response = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "senha": "TestPass123"},
        )
        assert login_response.status_code == 200

        # Depois faz logout
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        assert "Logout realizado" in response.json()["message"]


class TestAlterarSenha:
    """Testes para alteração de senha."""

    def test_alterar_senha_sucesso(
        self, client: TestClient, test_user: Usuario, auth_headers: dict
    ):
        """Alteração de senha com dados válidos deve funcionar."""
        response = client.put(
            "/api/auth/alterar-senha",
            headers=auth_headers,
            json={
                "senha_atual": "TestPass123",
                "senha_nova": "NovaSenha456",
            },
        )
        assert response.status_code == 200
        assert "Senha alterada" in response.json()["message"]

    def test_alterar_senha_atual_incorreta(
        self, client: TestClient, test_user: Usuario, auth_headers: dict
    ):
        """Alteração com senha atual incorreta deve falhar."""
        response = client.put(
            "/api/auth/alterar-senha",
            headers=auth_headers,
            json={
                "senha_atual": "SenhaErrada123",
                "senha_nova": "NovaSenha456",
            },
        )
        assert response.status_code == 400
        assert "Senha atual incorreta" in response.json()["detail"]

    def test_alterar_senha_nova_fraca(
        self, client: TestClient, test_user: Usuario, auth_headers: dict
    ):
        """Nova senha fraca deve falhar validação."""
        response = client.put(
            "/api/auth/alterar-senha",
            headers=auth_headers,
            json={
                "senha_atual": "TestPass123",
                "senha_nova": "fraca",
            },
        )
        assert response.status_code == 422
