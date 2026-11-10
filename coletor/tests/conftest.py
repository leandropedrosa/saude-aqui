"""
Preparação dos testes do coletor.

Fixtures (dados de entrada) vêm de coletor/amostras/:
  cnes_estabelecimentos_520549.json       resposta real da API do CNES (unidades)
  cnes_pf_cidade_ocidental_202609.json    registros reais do PF de set/2026, já SEM CNS/CPF

Os testes de banco usam um Postgres de verdade (o do docker compose) num banco
separado, "saude_aqui_teste_coletor", recriado a cada execução.

    docker compose up -d db
    cd coletor && pytest
"""

import json
import os
import struct
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
AMOSTRAS = RAIZ / "coletor" / "amostras"
URL_TESTE = os.environ.get(
    "TEST_DATABASE_URL_COLETOR",
    "postgresql://saude_aqui:troque-esta-senha@localhost:5432/saude_aqui_teste_coletor",
)


@pytest.fixture(scope="session")
def estabelecimentos() -> list[dict]:
    return json.loads((AMOSTRAS / "cnes_estabelecimentos_520549.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def registros_pf() -> list[dict]:
    return json.loads((AMOSTRAS / "cnes_pf_cidade_ocidental_202609.json").read_text(encoding="utf-8"))


def escrever_dbf(caminho: Path, campos: list[tuple[str, int]], registros: list[dict],
                 apagados: set[int] = frozenset()) -> None:
    """Gera um DBF pequeno, imitando o defeito dos arquivos do DATASUS:
    o byte terminador do cabeçalho é 0x00 em vez de 0x0D (a dbfread falha nisso)."""
    tamanho_cabecalho = 32 + 32 * len(campos) + 1
    tamanho_registro = 1 + sum(t for _, t in campos)
    cab = bytearray(32)
    cab[0] = 0x03
    cab[4:12] = struct.pack("<IHH", len(registros), tamanho_cabecalho, tamanho_registro)
    for nome, tamanho in campos:
        descricao = bytearray(32)
        descricao[:len(nome)] = nome.encode("ascii")
        descricao[11] = ord("C")
        descricao[16] = tamanho
        cab += descricao
    cab += b"\x00"  # o certo seria 0x0D
    corpo = bytearray()
    for i, r in enumerate(registros):
        corpo += b"*" if i in apagados else b" "
        for nome, tamanho in campos:
            corpo += str(r.get(nome, "")).encode("latin-1").ljust(tamanho)[:tamanho]
    caminho.write_bytes(bytes(cab + corpo))


# Campos do PF usados nos testes (inclui CNS e CPF, que o coletor deve descartar)
CAMPOS_PF = [("CNES", 7), ("CODUFMUN", 6), ("CBO", 6), ("NOMEPROF", 60), ("CNS_PROF", 15),
             ("CPF_PROF", 11), ("CONSELHO", 2), ("REGISTRO", 13),
             ("HORAOUTR", 3), ("HORAHOSP", 3), ("HORA_AMB", 3), ("COMPETEN", 6)]


@pytest.fixture
def con():
    """Conexão com um banco de teste novo (schema do db/init.sql, sem dados)."""
    nome = URL_TESTE.rsplit("/", 1)[1]
    admin = URL_TESTE.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{nome}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{nome}"')
    with psycopg.connect(URL_TESTE, autocommit=True) as c:
        c.execute((RAIZ / "db" / "init.sql").read_text(encoding="utf-8"))
    with psycopg.connect(URL_TESTE) as c:
        yield c
