"""
API do Saúde Aqui (FastAPI).

Todas as rotas ficam sob /api. A documentação interativa fica em /api/docs.

Rodar localmente (fora do Docker):
    cd api
    DATABASE_URL=postgresql://saude_aqui:SENHA@localhost:5432/saude_aqui \
        uvicorn app.main:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import banco
from .formatacao import chave_ordenacao, formatar_nome, texto_horario
from .modelos import (
    Especialidade,
    Profissional,
    RespostaProximas,
    Status,
    Unidade,
    UnidadeComProfissionais,
)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Abre o pool de conexões ao iniciar e fecha ao encerrar."""
    banco.abrir(os.environ["DATABASE_URL"])
    yield
    banco.fechar()


app = FastAPI(
    title="Saúde Aqui",
    description="Unidades públicas de saúde de Cidade Ocidental (GO) e os profissionais "
    "vinculados a elas, segundo o CNES/DATASUS.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=ciclo_de_vida,
)

# CORS: só os domínios listados em CORS_ORIGINS podem chamar a API pelo navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_methods=["GET"],
    allow_headers=["*"],
)

rotas = APIRouter(prefix="/api")

# Subconsulta reutilizada: a competência (mês) mais recente importada.
COMPETENCIA_ATUAL = "(SELECT max(competencia) FROM vinculo)"


def _competencia_texto(data) -> str | None:
    """date(2026, 9, 1) -> '2026-09'."""
    return data.strftime("%Y-%m") if data else None


def _montar_unidade(linha: dict) -> dict:
    """Converte uma linha da tabela unidade no formato do modelo Unidade."""
    return {
        **linha,
        "horario": texto_horario(linha["horario"], linha["turno_codigo"], linha["turno_descricao"]),
    }


# ---------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------

@rotas.get("/health", summary="Verificação de saúde")
def health():
    banco.consultar("SELECT 1")
    return {"status": "ok"}


@rotas.get("/status", response_model=Status, summary="Data da última atualização e competência")
def status():
    linha = banco.consultar(f"""
        SELECT
            (SELECT max(baixado_em) FROM coleta WHERE status = 'sucesso') AS ultima_atualizacao,
            (SELECT max(baixado_em) FROM coleta
              WHERE status IN ('sucesso', 'sem_novidade'))                AS ultima_verificacao,
            {COMPETENCIA_ATUAL}                                          AS competencia,
            (SELECT count(*) FROM unidade WHERE ativo)                    AS unidades,
            (SELECT count(*) FROM vinculo v
               JOIN ocupacao o USING (cbo)
               JOIN unidade u ON u.id = v.unidade_id
              WHERE o.atendimento AND u.ativo
                AND v.competencia = {COMPETENCIA_ATUAL})                  AS vinculos
    """)[0]
    linha["competencia"] = _competencia_texto(linha["competencia"])
    return linha


@rotas.get("/bairros", response_model=list[str], summary="Bairros que têm unidades")
def bairros():
    linhas = banco.consultar("""
        SELECT DISTINCT bairro FROM unidade
         WHERE ativo AND bairro IS NOT NULL
         ORDER BY bairro
    """)
    # Ordena em Python ignorando acentos: no banco, "São" viria depois de "Setor"
    return sorted((l["bairro"] for l in linhas), key=chave_ordenacao)


@rotas.get("/especialidades", response_model=list[Especialidade],
           summary="Ocupações presentes nas unidades (para o filtro)")
def especialidades():
    return banco.consultar(f"""
        SELECT o.cbo, o.nome, o.categoria, count(*) AS total
          FROM vinculo v
          JOIN ocupacao o USING (cbo)
          JOIN unidade  u ON u.id = v.unidade_id
         WHERE o.atendimento AND u.ativo
           AND v.competencia = {COMPETENCIA_ATUAL}
         GROUP BY o.cbo, o.nome, o.categoria
         ORDER BY o.categoria, o.nome
    """)


@rotas.get("/unidades", response_model=list[Unidade], summary="Unidades com coordenadas")
def unidades(bairro: str | None = Query(None, description="Filtrar por bairro (como em /bairros)")):
    linhas = banco.consultar("""
        SELECT id, cnes, nome, tipo, endereco, bairro, lat, lng, telefone,
               horario, turno_codigo, turno_descricao
          FROM unidade
         WHERE ativo
           AND lat IS NOT NULL AND lng IS NOT NULL
           AND (%(bairro)s::text IS NULL OR bairro = %(bairro)s)
         ORDER BY nome
    """, {"bairro": bairro})
    linhas.sort(key=lambda l: chave_ordenacao(l["nome"]))  # ordem alfabética ignorando acentos
    return [_montar_unidade(l) for l in linhas]


@rotas.get("/unidades/proximas", response_model=RespostaProximas,
           summary="Unidades com os profissionais vinculados, ordenadas por distância")
def unidades_proximas(
    lat: float | None = Query(None, ge=-90, le=90, description="Latitude de quem pesquisa"),
    lng: float | None = Query(None, ge=-180, le=180, description="Longitude de quem pesquisa"),
    raio_km: float | None = Query(None, gt=0, le=100, description="Só unidades até essa distância"),
    bairro: str | None = Query(None, description="Filtrar por bairro"),
    categoria: str | None = Query(None, description="Ex.: Medicina, Enfermagem, Odontologia"),
    cbo: str | None = Query(None, description="Código CBO de uma ocupação (ver /especialidades)"),
):
    """
    Sem lat/lng, as unidades vêm em ordem alfabética e `distancia_km` é nulo.
    Com lat/lng, vêm da mais próxima para a mais distante.

    Com `categoria` ou `cbo`, só aparecem as unidades que têm esse tipo de
    profissional, e a lista de profissionais também é filtrada.
    """
    if (lat is None) != (lng is None):
        raise HTTPException(422, "Informe lat e lng juntos.")
    if raio_km is not None and lat is None:
        raise HTTPException(422, "raio_km só pode ser usado junto com lat e lng.")

    p = {"lat": lat, "lng": lng, "raio_km": raio_km, "bairro": bairro,
         "categoria": categoria, "cbo": cbo, "filtra_profissional": bool(categoria or cbo)}

    # Condição reaproveitada nas duas consultas: "esta ocupação passa nos filtros?"
    filtro_ocupacao = """
        o.atendimento
        AND (%(categoria)s::text IS NULL OR o.categoria = %(categoria)s)
        AND (%(cbo)s::text       IS NULL OR o.cbo       = %(cbo)s)
    """

    # 1) As unidades (com a distância calculada no banco, por Haversine)
    unidades_encontradas = banco.consultar(f"""
        SELECT * FROM (
            SELECT u.id, u.cnes, u.nome, u.tipo, u.endereco, u.bairro, u.lat, u.lng,
                   u.telefone, u.horario, u.turno_codigo, u.turno_descricao,
                   CASE WHEN %(lat)s::float8 IS NULL OR u.lat IS NULL THEN NULL
                        ELSE round(distancia_km(%(lat)s, %(lng)s, u.lat, u.lng)::numeric, 2)::float8
                   END AS distancia_km
              FROM unidade u
             WHERE u.ativo
               AND (%(bairro)s::text IS NULL OR u.bairro = %(bairro)s)
               AND (NOT %(filtra_profissional)s OR EXISTS (
                        SELECT 1 FROM vinculo v JOIN ocupacao o USING (cbo)
                         WHERE v.unidade_id = u.id
                           AND v.competencia = {COMPETENCIA_ATUAL}
                           AND {filtro_ocupacao}))
        ) AS t
        WHERE %(raio_km)s::float8 IS NULL OR distancia_km <= %(raio_km)s
        ORDER BY distancia_km NULLS LAST, nome
    """, p)

    # Ordem: mais próxima primeiro (sem distância vai para o fim); empate pelo nome,
    # ignorando acentos (no banco, "São" viria depois de "Setor")
    unidades_encontradas.sort(key=lambda u: (
        u["distancia_km"] is None, u["distancia_km"] or 0, chave_ordenacao(u["nome"])))

    # 2) Os profissionais dessas unidades, numa única consulta
    ids = [u["id"] for u in unidades_encontradas]
    vinculos = banco.consultar(f"""
        SELECT v.unidade_id, v.profissional, o.categoria, o.nome AS ocupacao,
               v.carga_horaria_semanal
          FROM vinculo v
          JOIN ocupacao o USING (cbo)
         WHERE v.unidade_id = ANY(%(ids)s::int[])
           AND v.competencia = {COMPETENCIA_ATUAL}
           AND {filtro_ocupacao}
         ORDER BY o.categoria, o.nome, v.profissional
    """, {**p, "ids": ids})

    # 3) Agrupa os profissionais por unidade (em Python, para ficar legível)
    por_unidade: dict[int, list[Profissional]] = {i: [] for i in ids}
    for v in vinculos:
        por_unidade[v["unidade_id"]].append(Profissional(
            nome=formatar_nome(v["profissional"]),
            categoria=v["categoria"],
            ocupacao=v["ocupacao"],
            carga_horaria_semanal=v["carga_horaria_semanal"],
        ))

    competencia = banco.consultar(f"SELECT {COMPETENCIA_ATUAL} AS c")[0]["c"]
    resultado = [
        UnidadeComProfissionais(**_montar_unidade(u), profissionais=por_unidade[u["id"]])
        for u in unidades_encontradas
    ]
    return RespostaProximas(
        competencia=_competencia_texto(competencia),
        total=len(resultado),
        unidades=resultado,
    )


app.include_router(rotas)
