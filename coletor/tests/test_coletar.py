"""
Testes de integração do coletor com o banco (Postgres de teste).

A rede não é usada: a API do CNES e o FTP do DATASUS são substituídos
(monkeypatch) pelas amostras reais em coletor/amostras/.
"""

import shutil

import pytest

import coletar
from conftest import CAMPOS_PF, RAIZ, URL_TESTE, escrever_dbf
from transformar import competencia_para_data, ler_ajustes_unidades, ler_ocupacoes

SET_2026 = competencia_para_data("2609")


def preparar_cadastros(con, estabelecimentos):
    coletar.sincronizar_ocupacoes(con, ler_ocupacoes(RAIZ / "db" / "ocupacoes.csv"))
    coletar.importar_unidades(con, estabelecimentos, ler_ajustes_unidades(RAIZ / "db" / "unidades.csv"))
    con.commit()


def com_dados_pessoais(registros):
    """Acrescenta CNS/CPF falsos, como no arquivo original do DATASUS."""
    return [{**r, "CNS_PROF": "700999999999999", "CPF_PROF": "99988877766", "REGISTRO": "54321"}
            for r in registros]


def test_importa_unidades(con, estabelecimentos):
    preparar_cadastros(con, estabelecimentos)
    total, ativas = con.execute("SELECT count(*), count(*) FILTER (WHERE ativo) FROM unidade").fetchone()
    assert (total, ativas) == (47, 38)
    bairro = con.execute("SELECT bairro FROM unidade WHERE cnes = '2438690'").fetchone()[0]
    assert bairro == "Friburgo B"  # corrigido pelo unidades.csv (no CNES: "FIBURGO B")


def test_importa_vinculos_reais_de_setembro(con, estabelecimentos, registros_pf):
    preparar_cadastros(con, estabelecimentos)
    gravados = coletar.importar_vinculos(con, iter(com_dados_pessoais(registros_pf)), SET_2026, None)
    con.commit()
    assert gravados == 414  # 815 do município - privados - ocupações fora do site

    # Agentes comunitários de saúde ficam de fora
    acs = con.execute("SELECT count(*) FROM vinculo WHERE cbo IN ('515105', '322255')").fetchone()[0]
    assert acs == 0

    # Nenhum dado pessoal foi parar no banco
    despejo = con.execute("SELECT string_agg(v::text, '|') FROM vinculo v").fetchone()[0]
    for proibido in ("700999999999999", "99988877766", "54321"):
        assert proibido not in despejo


def test_reimportar_nao_duplica(con, estabelecimentos, registros_pf):
    preparar_cadastros(con, estabelecimentos)
    for _ in range(2):
        coletar.importar_vinculos(con, iter(registros_pf), SET_2026, None)
        con.commit()
    assert con.execute("SELECT count(*) FROM vinculo").fetchone()[0] == 414


def test_mesma_pessoa_em_duas_linhas_soma_horas(con, estabelecimentos):
    preparar_cadastros(con, estabelecimentos)
    linha = {"CNES": "7713304", "CODUFMUN": "520549", "CBO": "225142", "NOMEPROF": "FULANA",
             "HORAOUTR": "0", "HORAHOSP": "0", "HORA_AMB": "20"}
    coletar.importar_vinculos(con, iter([linha, linha]), SET_2026, None)
    con.commit()
    assert con.execute("SELECT carga_horaria_semanal FROM vinculo").fetchone()[0] == 40


# ---------------------------------------------------------------- execução completa

@pytest.fixture
def fontes_falsas(monkeypatch, tmp_path, estabelecimentos, registros_pf):
    """Troca rede e descompressão por arquivos locais gerados a partir das amostras."""
    dbf_amostra = tmp_path / "amostra.dbf"
    escrever_dbf(dbf_amostra, CAMPOS_PF, com_dados_pessoais(registros_pf))
    conteudo = {"dbc": b"arquivo-dbc-falso-v1"}

    def baixar(url, uf, aamm, pasta):
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"PF{uf}{aamm}.dbc"
        destino.write_bytes(conteudo["dbc"])
        return destino

    monkeypatch.setattr(coletar, "DATABASE_URL", URL_TESTE)
    monkeypatch.setattr(coletar, "PASTA_BRUTOS", tmp_path / "brutos")
    monkeypatch.setattr(coletar, "buscar_estabelecimentos", lambda url, mun: estabelecimentos)
    monkeypatch.setattr(coletar, "competencias_disponiveis", lambda url, uf: ["2609", "2608"])
    monkeypatch.setattr(coletar, "baixar_pf", baixar)
    monkeypatch.setattr(coletar.datasus_dbc, "decompress", lambda dbc, dbf: shutil.copy(dbf_amostra, dbf))
    return conteudo


def ultima_coleta(con):
    return con.execute("""SELECT status, registros_importados, competencia, erro
                            FROM coleta ORDER BY id DESC LIMIT 1""").fetchone()


def test_executar_sucesso_e_depois_sem_novidade(con, fontes_falsas):
    assert coletar.executar() == 0
    status, total, competencia, erro = ultima_coleta(con)
    assert (status, total, competencia, erro) == ("sucesso", 414, SET_2026, None)

    # Mesmo arquivo (mesmo SHA-256): não reimporta
    assert coletar.executar() == 0
    assert ultima_coleta(con)[0] == "sem_novidade"

    # Com --forcar reimporta, sem duplicar
    assert coletar.executar(forcar=True) == 0
    assert ultima_coleta(con)[0] == "sucesso"
    assert con.execute("SELECT count(*) FROM vinculo").fetchone()[0] == 414

    # Arquivo novo (conteúdo diferente) é importado
    fontes_falsas["dbc"] = b"arquivo-dbc-falso-v2"
    assert coletar.executar() == 0
    assert ultima_coleta(con)[0] == "sucesso"


def test_executar_registra_erro(con, fontes_falsas, monkeypatch):
    def falhar(url, mun):
        raise ConnectionError("API fora do ar")
    monkeypatch.setattr(coletar, "buscar_estabelecimentos", falhar)

    assert coletar.executar() == 1
    status, _, _, erro = ultima_coleta(con)
    assert status == "erro"
    assert "API fora do ar" in erro
