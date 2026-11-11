"""Testes da integração com o portal de escalas da Prefeitura (sem rede)."""

import json
from datetime import date

import pytest

import coletar
from conftest import AMOSTRAS, RAIZ
from transformar import (
    eh_listagem_cnes, escalas_desde, formatar_horario_portal, horarios_por_cnes,
    ler_ajustes_unidades, mapa_portal_cnes,
)
from test_coletar import preparar_cadastros

DESDE_2026 = date(2026, 1, 1)


@pytest.fixture(scope="session")
def escalas() -> list[dict]:
    """Resposta real do portal (65 publicações, de 2023 a 2026), sem os links assinados."""
    return json.loads((AMOSTRAS / "escalas_lista.json").read_text(encoding="utf-8"))


def test_so_publicacoes_de_2026_em_diante(escalas):
    recentes = escalas_desde(escalas, DESDE_2026)
    assert len(escalas) == 65
    assert len(recentes) == 10
    assert all(e["data_inicio"] >= "2026-01-01" for e in recentes)


@pytest.mark.parametrize("entrada, esperado", [
    (" SEGUNDA A SEXTA FEIRA DAS 8H ÁS 17H", "Segunda a sexta feira das 8h às 17h"),
    ("24H", "24 horas"),
    ("SEGUNDA A SEXTA DAS 8H ÀS 22H E SÁBADOS DAS 8H ÀS 12H",
     "Segunda a sexta das 8h às 22h e sábados das 8h às 12h"),
    ("", None),
    (None, None),
])
def test_formatar_horario_portal(entrada, esperado):
    assert formatar_horario_portal(entrada) == esperado


def test_mapa_portal_cobre_unidades_duplas():
    mapa = mapa_portal_cnes(ler_ajustes_unidades(RAIZ / "db" / "unidades.csv"))
    assert sorted(mapa["18"]) == ["3005070", "3042677"]   # "UBSF SQ 11/12" -> SQ 11 e SQ 12
    assert mapa["13"] == ["7713304"]                       # UBSF Dom Bosco


def test_horarios_por_cnes(escalas):
    mapa = mapa_portal_cnes(ler_ajustes_unidades(RAIZ / "db" / "unidades.csv"))
    horarios = horarios_por_cnes(escalas_desde(escalas, DESDE_2026), mapa)
    assert horarios["7713304"] == "Segunda a sexta feira das 8h às 17h"   # Dom Bosco
    assert horarios["2569728"] == "24 horas"                              # Hospital
    assert horarios["3005070"] == horarios["3042677"]                     # SQ 11 e SQ 12
    assert "3005100" not in horarios   # SQ 15 só tem publicações antigas (2024/2025)


def test_reconhece_listagem_do_cnes():
    assert eh_listagem_cnes("CNES Cadastro Nacional de ... Listagem de Profissionais ...")
    assert not eh_listagem_cnes("ESCALA DE PLANTÃO - NOVEMBRO/2026 - DIURNO")


# ---------------------------------------------------------------- com banco

@pytest.fixture
def portal_falso(monkeypatch, escalas):
    """Portal com as 65 publicações reais; os PDFs de 2026 são listagens do CNES."""
    lista = list(escalas)
    baixados = []

    def classificar(midia):
        baixados.append(midia)
        return "possivel_escala" if not midia.endswith(".pdf") else "listagem_cnes"

    monkeypatch.setattr(coletar, "buscar_escalas_portal", lambda url: lista)
    monkeypatch.setattr(coletar, "classificar_arquivo", classificar)
    return {"lista": lista, "baixados": baixados}


def test_processar_portal(con, estabelecimentos, portal_falso):
    preparar_cadastros(con, estabelecimentos)
    ajustes = ler_ajustes_unidades(RAIZ / "db" / "unidades.csv")

    avisos = coletar.processar_portal(con, ajustes)
    con.commit()
    assert avisos == []                                    # 2026: só listagens do CNES
    assert len(portal_falso["baixados"]) == 10
    horario = con.execute("SELECT horario_portal FROM unidade WHERE cnes = '7713304'").fetchone()[0]
    assert horario == "Segunda a sexta feira das 8h às 17h"
    assert con.execute("SELECT count(*) FROM arquivo_portal").fetchone()[0] == 10

    # Segunda execução: nada é baixado de novo
    assert coletar.processar_portal(con, ajustes) == []
    assert len(portal_falso["baixados"]) == 10

    # A Prefeitura publica uma planilha de escala nova -> aviso
    portal_falso["lista"].append({
        "unidade_id": "26", "nome": "HOSPITAL MUNICIPAL DE CIDADE OCIDENTAL",
        "data_inicio": "2026-12-01", "data_fim": "2026-12-31", "horario_funcionamento": "24H",
        "midia": "abc123.xlsx", "titulo_midia": "ESCALA DEZEMBRO.xlsx",
    })
    avisos = coletar.processar_portal(con, ajustes)
    assert len(avisos) == 1 and "ESCALA DEZEMBRO.xlsx" in avisos[0]
    tipo = con.execute("SELECT tipo FROM arquivo_portal WHERE midia = 'abc123.xlsx'").fetchone()[0]
    assert tipo == "possivel_escala"
