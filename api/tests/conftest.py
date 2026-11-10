"""
Preparação dos testes da API.

Os testes usam um Postgres de verdade (o mesmo do docker compose), mas em
um banco separado, "saude_aqui_teste", recriado do zero a cada execução com:
    db/init.sql            (schema)
    db/dados_ficticios.sql (dados inventados)

Como rodar (com o banco no ar: docker compose up -d db):
    cd api
    pytest

Variável opcional: TEST_DATABASE_URL (padrão abaixo, igual ao .env.example).
"""

import os
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
URL_TESTE = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://saude_aqui:troque-esta-senha@localhost:5432/saude_aqui_teste",
)
ORIGEM_PERMITIDA = "http://localhost:5173"


def _recriar_banco_de_teste() -> None:
    """Apaga e cria de novo o banco de teste, carregando schema e dados fictícios."""
    nome_banco = URL_TESTE.rsplit("/", 1)[1]
    url_admin = URL_TESTE.rsplit("/", 1)[0] + "/postgres"

    # CREATE/DROP DATABASE não podem rodar dentro de transação: autocommit
    with psycopg.connect(url_admin, autocommit=True) as con:
        con.execute(f'DROP DATABASE IF EXISTS "{nome_banco}" WITH (FORCE)')
        con.execute(f'CREATE DATABASE "{nome_banco}"')

    with psycopg.connect(URL_TESTE, autocommit=True) as con:
        con.execute((RAIZ / "db" / "init.sql").read_text(encoding="utf-8"))
        con.execute((RAIZ / "db" / "dados_ficticios.sql").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def cliente():
    """Cliente HTTP de teste (usa httpx por baixo) com a API apontando para o banco de teste."""
    _recriar_banco_de_teste()
    os.environ["DATABASE_URL"] = URL_TESTE
    os.environ["CORS_ORIGINS"] = ORIGEM_PERMITIDA

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:  # o "with" dispara a abertura/fechamento do pool
        yield c
