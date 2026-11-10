"""
Testes das rotas da API, com base em db/dados_ficticios.sql.

Resumo dos dados fictícios:
  unidade 1  UBS FICTÍCIA CENTRO      ativa   médica ESF, enfermeiro, dentista (+ ACS oculto)
  unidade 2  UBS FICTÍCIA JARDIM ABC  ativa   médica clínica; horário manual
  unidade 3  HOSPITAL FICTÍCIO        ativa   pediatra, técnica de enfermagem; 24h
  unidade 4  SETOR ADMINISTRATIVO     OCULTA
  unidade 5  UBS FICTÍCIA SEM MAPA    ativa   sem coordenadas
  competência atual 2026-09; a de 2026-08 não deve aparecer.
"""

import pytest

from app.formatacao import chave_ordenacao, formatar_nome, texto_horario

# Um ponto ao lado da UBS FICTÍCIA CENTRO (-16.0920, -47.9260)
PERTO_DO_CENTRO = {"lat": -16.0921, "lng": -47.9261}


def nomes(resposta) -> list[str]:
    return [u["nome"] for u in resposta.json()["unidades"]]


# ---------------------------------------------------------------- básicas

def test_health(cliente):
    r = cliente.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_documentacao_automatica(cliente):
    assert cliente.get("/api/docs").status_code == 200
    assert cliente.get("/api/openapi.json").status_code == 200


def test_status(cliente):
    dados = cliente.get("/api/status").json()
    assert dados["competencia"] == "2026-09"
    assert dados["ultima_atualizacao"].startswith("2026-11-05")
    assert dados["ultima_verificacao"].startswith("2026-11-10")  # inclui "sem_novidade"
    assert dados["unidades"] == 4  # a unidade oculta não conta
    # Unidades 1, 2, 3 e 5 com ocupações de atendimento: 3 + 1 + 2 + 1
    assert dados["vinculos"] == 7


def test_bairros_nao_inclui_unidade_oculta(cliente):
    assert cliente.get("/api/bairros").json() == ["CENTRO", "JARDIM ABC", "ZONA RURAL"]


def test_especialidades(cliente):
    dados = cliente.get("/api/especialidades").json()
    cbos = {e["cbo"] for e in dados}
    assert "515105" not in cbos  # agente comunitário: atendimento = FALSE
    assert "223710" not in cbos  # nutricionista só existe na competência antiga
    enfermeiro = next(e for e in dados if e["cbo"] == "223505")
    assert enfermeiro == {"cbo": "223505", "nome": "Enfermeiro", "categoria": "Enfermagem", "total": 2}


def test_unidades_so_com_coordenadas(cliente):
    dados = cliente.get("/api/unidades").json()
    assert [u["nome"] for u in dados] == [
        "HOSPITAL FICTÍCIO", "UBS FICTÍCIA CENTRO", "UBS FICTÍCIA JARDIM ABC"]


def test_unidades_por_bairro(cliente):
    dados = cliente.get("/api/unidades", params={"bairro": "JARDIM ABC"}).json()
    assert len(dados) == 1
    assert dados[0]["horario"] == "Seg a sex, 13h às 19h"  # horário manual tem prioridade


# ---------------------------------------------------------------- /unidades/proximas

def test_proximas_sem_localizacao_ordem_alfabetica(cliente):
    r = cliente.get("/api/unidades/proximas")
    assert r.status_code == 200
    dados = r.json()
    assert dados["competencia"] == "2026-09"
    assert nomes(r) == ["HOSPITAL FICTÍCIO", "UBS FICTÍCIA CENTRO",
                        "UBS FICTÍCIA JARDIM ABC", "UBS FICTÍCIA SEM MAPA"]
    assert all(u["distancia_km"] is None for u in dados["unidades"])


def test_proximas_ordena_por_distancia(cliente):
    r = cliente.get("/api/unidades/proximas", params=PERTO_DO_CENTRO)
    unidades = r.json()["unidades"]
    assert nomes(r) == ["UBS FICTÍCIA CENTRO", "HOSPITAL FICTÍCIO",
                        "UBS FICTÍCIA JARDIM ABC", "UBS FICTÍCIA SEM MAPA"]
    assert unidades[0]["distancia_km"] < 0.1
    assert unidades[1]["distancia_km"] == pytest.approx(1.33, abs=0.1)
    assert unidades[-1]["distancia_km"] is None  # sem coordenadas: vai para o fim


def test_proximas_com_raio(cliente):
    r = cliente.get("/api/unidades/proximas", params={**PERTO_DO_CENTRO, "raio_km": 2})
    assert nomes(r) == ["UBS FICTÍCIA CENTRO", "HOSPITAL FICTÍCIO"]


def test_proximas_profissionais_da_unidade(cliente):
    r = cliente.get("/api/unidades/proximas", params=PERTO_DO_CENTRO)
    centro = r.json()["unidades"][0]
    assert centro["horario"] == "Manhã e tarde"  # turno 03 do CNES
    # Ordenados por categoria; sem o agente comunitário e sem a competência antiga
    assert centro["profissionais"] == [
        {"nome": "Joao Ficticio dos Santos", "categoria": "Enfermagem",
         "ocupacao": "Enfermeiro", "carga_horaria_semanal": 40},
        {"nome": "Maria Exemplo da Silva", "categoria": "Medicina",
         "ocupacao": "Médico da estratégia de saúde da família", "carga_horaria_semanal": 40},
        {"nome": "Ana Teste de Oliveira", "categoria": "Odontologia",
         "ocupacao": "Cirurgião-dentista da estratégia de saúde da família",
         "carga_horaria_semanal": 40},
    ]


def test_proximas_so_expoe_campos_permitidos(cliente):
    """Profissional: só nome, categoria, ocupação e carga horária. Nada além disso."""
    for u in cliente.get("/api/unidades/proximas").json()["unidades"]:
        for p in u["profissionais"]:
            assert set(p) == {"nome", "categoria", "ocupacao", "carga_horaria_semanal"}


def test_proximas_filtro_categoria(cliente):
    r = cliente.get("/api/unidades/proximas", params={"categoria": "Enfermagem"})
    assert nomes(r) == ["HOSPITAL FICTÍCIO", "UBS FICTÍCIA CENTRO", "UBS FICTÍCIA SEM MAPA"]
    for u in r.json()["unidades"]:
        assert {p["categoria"] for p in u["profissionais"]} == {"Enfermagem"}


def test_proximas_filtro_cbo(cliente):
    r = cliente.get("/api/unidades/proximas", params={"cbo": "225124"})
    assert nomes(r) == ["HOSPITAL FICTÍCIO"]
    assert [p["nome"] for p in r.json()["unidades"][0]["profissionais"]] == ["Lucas Ficticio Pediatra"]


def test_proximas_filtro_bairro(cliente):
    r = cliente.get("/api/unidades/proximas", params={"bairro": "CENTRO"})
    assert nomes(r) == ["HOSPITAL FICTÍCIO", "UBS FICTÍCIA CENTRO"]


def test_proximas_nunca_mostra_unidade_oculta(cliente):
    r = cliente.get("/api/unidades/proximas", params={"cbo": "225125"})
    assert nomes(r) == ["UBS FICTÍCIA JARDIM ABC"]


def test_proximas_sem_resultado(cliente):
    r = cliente.get("/api/unidades/proximas", params={"categoria": "Inexistente"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


@pytest.mark.parametrize("params", [
    {"lat": -16.09},                       # falta lng
    {"raio_km": 5},                        # raio sem localização
    {"lat": -100, "lng": -47.9},           # latitude inválida
    {**PERTO_DO_CENTRO, "raio_km": 0},     # raio precisa ser > 0
])
def test_proximas_parametros_invalidos(cliente, params):
    assert cliente.get("/api/unidades/proximas", params=params).status_code == 422


# ---------------------------------------------------------------- CORS

def test_cors_permite_origem_configurada(cliente):
    r = cliente.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_bloqueia_outras_origens(cliente):
    r = cliente.get("/api/health", headers={"Origin": "https://site-qualquer.example"})
    assert "access-control-allow-origin" not in r.headers


# ---------------------------------------------------------------- formatação

@pytest.mark.parametrize("entrada, esperado", [
    ("MARIA DA SILVA E SOUZA", "Maria da Silva e Souza"),
    ("  JOAO   DOS SANTOS ", "Joao dos Santos"),
    ("DE ASSIS FERREIRA", "De Assis Ferreira"),  # partícula no início fica maiúscula
])
def test_formatar_nome(entrada, esperado):
    assert formatar_nome(entrada) == esperado


def test_texto_horario():
    assert texto_horario("Seg a sex, 8h às 17h", "03", "x") == "Seg a sex, 8h às 17h"
    assert texto_horario(None, "06", None).startswith("24 horas")
    assert texto_horario(None, "99", "ATENDIMENTO ESPECIAL") == "Atendimento especial"
    assert texto_horario(None, None, None) is None


def test_ordem_alfabetica_ignora_acentos():
    bairros = ["Setor de Mansões Sul", "São Matheus", "Centro", "Ábaco"]
    assert sorted(bairros, key=chave_ordenacao) == ["Ábaco", "Centro", "São Matheus", "Setor de Mansões Sul"]
