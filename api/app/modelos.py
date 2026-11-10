"""
Modelos de resposta da API (Pydantic v2).

Eles definem o formato do JSON e aparecem na documentação automática
em /api/docs.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Status(BaseModel):
    ultima_atualizacao: datetime | None = Field(
        description="Quando os dados foram importados pela última vez"
    )
    ultima_verificacao: datetime | None = Field(
        description="Quando o coletor verificou a fonte pela última vez (mesmo sem novidade)"
    )
    competencia: str | None = Field(
        description="Mês de referência do CNES dos dados exibidos (AAAA-MM)", examples=["2026-09"]
    )
    unidades: int = Field(description="Unidades exibidas no site")
    vinculos: int = Field(description="Vínculos de profissionais de atendimento na competência")


class Especialidade(BaseModel):
    cbo: str = Field(description="Código CBO da ocupação", examples=["225124"])
    nome: str = Field(examples=["Médico pediatra"])
    categoria: str = Field(examples=["Medicina"])
    total: int = Field(description="Quantos vínculos existem com essa ocupação")


class Unidade(BaseModel):
    id: int
    cnes: str
    nome: str
    tipo: str | None
    endereco: str | None
    bairro: str | None
    lat: float | None
    lng: float | None
    telefone: str | None
    horario: str | None = Field(description="Horário manual ou, na falta dele, o turno do CNES")


class Profissional(BaseModel):
    """Só nome, categoria, ocupação e carga horária. Nada além disso."""

    nome: str
    categoria: str
    ocupacao: str
    carga_horaria_semanal: int


class UnidadeComProfissionais(Unidade):
    distancia_km: float | None = Field(description="Só aparece quando lat/lng são informados")
    profissionais: list[Profissional]


class RespostaProximas(BaseModel):
    competencia: str | None
    total: int
    unidades: list[UnidadeComProfissionais]
