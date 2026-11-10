"""Testes sem banco: leitor DBF e transformações."""

from datetime import date

import pytest

from conftest import CAMPOS_PF, RAIZ, escrever_dbf
from dbf import ler_registros
from transformar import (
    aplicar_ajustes, competencia_para_data, eh_unidade_publica, ler_ajustes_unidades,
    ler_ocupacoes, transformar_estabelecimento, transformar_vinculo,
)

CNPJ = "36862621000121"


# ---------------------------------------------------------------- DBF

def test_le_dbf_com_cabecalho_do_datasus(tmp_path):
    arquivo = tmp_path / "PF.dbf"
    escrever_dbf(arquivo, [("CNES", 7), ("NOMEPROF", 30)], [
        {"CNES": "7713304", "NOMEPROF": "MARIA DA SILVA"},
        {"CNES": "0000001", "NOMEPROF": "APAGADO"},
        {"CNES": "2569728", "NOMEPROF": "JOSÉ ÇÃO"},  # acentos em latin-1
    ], apagados={1})
    assert list(ler_registros(arquivo)) == [
        {"CNES": "7713304", "NOMEPROF": "MARIA DA SILVA"},
        {"CNES": "2569728", "NOMEPROF": "JOSÉ ÇÃO"},
    ]


# ---------------------------------------------------------------- unidades

def test_filtra_so_unidades_publicas(estabelecimentos):
    publicas = [e for e in estabelecimentos if eh_unidade_publica(e, CNPJ)]
    assert len(estabelecimentos) == 69
    assert len(publicas) == 47
    assert not any("DROGASIL" in e["nome_fantasia"] for e in publicas)


def test_transformar_estabelecimento(estabelecimentos):
    dom_bosco = next(e for e in estabelecimentos if e["codigo_cnes"] == 7713304)
    u = transformar_estabelecimento(dom_bosco)
    assert u["cnes"] == "7713304"
    assert u["nome"] == "UBS FAMILIA DOM BOSCO"
    assert u["tipo"] == "Unidade Básica de Saúde"
    assert u["bairro"] == "DOM BOSCO"
    assert u["turno_codigo"] == "03"
    assert u["lat"] is not None and u["lng"] is not None
    assert u["ativo"] is True


def test_cnes_com_zeros_a_esquerda(estabelecimentos):
    sao_matheus = next(e for e in estabelecimentos if e["codigo_cnes"] == 68837)
    assert transformar_estabelecimento(sao_matheus)["cnes"] == "0068837"


def test_endereco_sem_numero_quando_s_n():
    u = transformar_estabelecimento({"codigo_cnes": 1, "nome_fantasia": "X",
                                     "endereco_estabelecimento": "QUADRA 47", "numero_estabelecimento": "S/N"})
    assert u["endereco"] == "QUADRA 47"
    u = transformar_estabelecimento({"codigo_cnes": 1, "nome_fantasia": "X",
                                     "endereco_estabelecimento": "RUA 5", "numero_estabelecimento": "10"})
    assert u["endereco"] == "RUA 5, 10"
    u = transformar_estabelecimento({"codigo_cnes": 1, "nome_fantasia": "X",
                                     "endereco_estabelecimento": "QUADRA 109 LOTE", "numero_estabelecimento": "09"})
    assert u["endereco"] == "QUADRA 109 LOTE 09"


def test_aplicar_ajustes():
    base = {"nome": "UBS X", "bairro": "FIBURGO B", "horario": None, "telefone": None,
            "lat": -16.0, "lng": -47.0, "ativo": True}
    ajuste = {"nome": "", "bairro": "FRIBURGO B", "horario": "Seg a sex, 7h às 17h",
              "telefone": "", "lat": "-16,1", "lng": "", "ativo": "sim"}
    r = aplicar_ajustes(base, ajuste)
    assert r == {**base, "bairro": "FRIBURGO B", "horario": "Seg a sex, 7h às 17h", "lat": -16.1}
    assert aplicar_ajustes(base, {"ativo": "nao"})["ativo"] is False
    assert aplicar_ajustes(base, None) == base


def test_csvs_reais_do_repositorio():
    ajustes = ler_ajustes_unidades(RAIZ / "db" / "unidades.csv")
    assert len(ajustes) == 47
    assert ajustes["3866718"]["ativo"] == "nao"  # Secretaria de Saúde: oculta

    ocupacoes = {o["cbo"]: o for o in ler_ocupacoes(RAIZ / "db" / "ocupacoes.csv")}
    assert ocupacoes["225125"]["atendimento"] is True    # médico clínico
    assert ocupacoes["515105"]["atendimento"] is False   # agente comunitário de saúde
    assert ocupacoes["322255"]["atendimento"] is False   # técnico em ACS
    assert ocupacoes["515140"]["atendimento"] is False   # agente de endemias


# ---------------------------------------------------------------- vínculos

def test_transformar_vinculo_descarta_dados_pessoais():
    registro = {"CNES": "7713304", "CODUFMUN": "520549", "CBO": "225142",
                "NOMEPROF": "MARIA  DA   SILVA", "CNS_PROF": "700000000000000",
                "CPF_PROF": "12345678901", "CONSELHO": "71", "REGISTRO": "12345",
                "HORAOUTR": "4", "HORAHOSP": "", "HORA_AMB": "36"}
    v = transformar_vinculo(registro)
    assert v == {"cnes": "7713304", "profissional": "MARIA DA SILVA", "cbo": "225142",
                 "carga_horaria_semanal": 40}
    texto = str(v)
    for proibido in ("700000000000000", "12345678901", "12345"):
        assert proibido not in texto


def test_campos_pf_de_teste_incluem_os_proibidos():
    """Garante que os testes de integração realmente exercitam o descarte."""
    nomes = {n for n, _ in CAMPOS_PF}
    assert {"CNS_PROF", "CPF_PROF", "REGISTRO"} <= nomes


@pytest.mark.parametrize("aamm, esperado", [("2609", date(2026, 9, 1)), ("202512", date(2025, 12, 1))])
def test_competencia_para_data(aamm, esperado):
    assert competencia_para_data(aamm) == esperado
