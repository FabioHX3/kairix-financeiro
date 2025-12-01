#!/usr/bin/env python3
"""
Script para iniciar o Kairix Financeiro
"""

import sys


def main():
    print("=" * 60)
    print("   KAIRIX FINANCEIRO - Sistema de Gestão Financeira com IA")
    print("=" * 60)
    print()

    print("📋 Verificando banco de dados...")

    try:
        from backend.models import criar_tabelas, inserir_categorias_padrao

        print("🔨 Criando/Verificando tabelas...")
        criar_tabelas()

        print("📦 Inserindo categorias padrão...")
        inserir_categorias_padrao()

        print("✅ Banco de dados configurado!")
        print()

    except Exception as e:
        print(f"❌ Erro ao configurar banco: {e}")
        print("   Verifique as configurações no arquivo .env")
        sys.exit(1)

    print("🚀 Iniciando servidor...")
    print()

    from backend.config import settings
    import uvicorn

    print(f"   🌐 Interface Web: http://localhost:{settings.PORT}")
    print(f"   📚 API Docs: http://localhost:{settings.PORT}/docs")
    print(f"   💬 WhatsApp Webhook: http://localhost:{settings.PORT}/api/whatsapp/webhook")
    print()
    print("=" * 60)
    print()

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )


if __name__ == "__main__":
    main()
