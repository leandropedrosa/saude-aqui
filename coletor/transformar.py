"""
Transformações "puras" (sem banco e sem rede), fáceis de testar:

* estabelecimento da API do CNES  -> linha da tabela `unidade`
* ajustes manuais de db/unidades.csv aplicados por cima
* registro do arquivo PF          -> linha da tabela `vinculo`

PRIVACIDADE: `transformar_vinculo` só copia os campos permitidos.
CNS_PROF (Cartão SUS), CPF_PROF, CONSELHO e REGISTRO são descartados aqui.
"""

import csv
import logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# Tipos de estabelecimento do CNES encontrados no município (codigo_tipo_unidade)
TIPOS = {
    2: "Unidade Básica de Saúde",
    5: "Hospital",
    36: "Centro de especialidades",
    40: "Unidade móvel",
    42: "Atendimento móvel de urgência",
    43: "Farmácia",
    50: "Vigilância em saúde",
    61: "Centro de parto normal",
    68: "Gestão em saúde",
    70: "Centro de Atenção Psicossocial",
    74: "Academia da Saúde",
    81: "Central de regulação",
    84: "Central de abastecimento",
}

# Campos de ajuste manual em db/unidades.csv (vazio = usar o valor do CNES)
CAMPOS_AJUSTE = ("nome", "bairro", "horario", "telefone", "lat", "lng")


# ---------------------------------------------------------------- unidades

def eh_unidade_publica(estabelecimento: dict, cnpj_mantenedora: str) -> bool:
    """A API marca tudo como 'MUNICIPAL'; o CNPJ da mantenedora é o critério confiável."""
    return estabelecimento.get("numero_cnpj_entidade") == cnpj_mantenedora


def _texto(valor) -> str | None:
    """Converte para texto sem espaços nas pontas; vazio vira None."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def transformar_estabelecimento(e: dict) -> dict:
    """Converte um estabelecimento da API no formato da tabela `unidade`."""
    endereco = _texto(e.get("endereco_estabelecimento"))
    numero = _texto(e.get("numero_estabelecimento"))
    if endereco and numero and numero.upper() not in ("S/N", "SN", "0"):
        endereco = f"{endereco}, {numero}"

    return {
        "cnes": str(e["codigo_cnes"]).zfill(7),
        "nome": _texto(e.get("nome_fantasia")) or _texto(e.get("nome_razao_social")),
        "tipo": TIPOS.get(e.get("codigo_tipo_unidade"), "Estabelecimento de saúde"),
        "endereco": endereco,
        "bairro": _texto(e.get("bairro_estabelecimento")),
        "lat": e.get("latitude_estabelecimento_decimo_grau"),
        "lng": e.get("longitude_estabelecimento_decimo_grau"),
        "telefone": _texto(e.get("numero_telefone_estabelecimento")),
        "turno_codigo": _texto(e.get("codigo_identificador_turno_atendimento")),
        "turno_descricao": _texto(e.get("descricao_turno_atendimento")),
        "horario": None,
        "ativo": True,
    }


def ler_ajustes_unidades(caminho: Path) -> dict[str, dict]:
    """Lê db/unidades.csv e devolve {cnes: linha}."""
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return {linha["cnes"].strip().zfill(7): linha for linha in csv.DictReader(arquivo)}


def aplicar_ajustes(unidade: dict, ajuste: dict | None) -> dict:
    """Aplica os ajustes manuais por cima dos dados do CNES."""
    if not ajuste:
        return unidade
    resultado = dict(unidade)
    for campo in CAMPOS_AJUSTE:
        valor = (ajuste.get(campo) or "").strip()
        if not valor:
            continue
        if campo in ("lat", "lng"):
            resultado[campo] = float(valor.replace(",", "."))
        else:
            resultado[campo] = valor
    resultado["ativo"] = (ajuste.get("ativo") or "sim").strip().lower() != "nao"
    return resultado


# ---------------------------------------------------------------- ocupações

def ler_ocupacoes(caminho: Path) -> list[dict]:
    """Lê db/ocupacoes.csv no formato da tabela `ocupacao`."""
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return [
            {
                "cbo": linha["cbo"].strip(),
                "nome": linha["nome"].strip(),
                "categoria": linha["categoria"].strip(),
                "atendimento": linha["incluir"].strip().lower() == "sim",
            }
            for linha in csv.DictReader(arquivo)
        ]


# ---------------------------------------------------------------- vínculos

def competencia_para_data(aamm: str) -> date:
    """'2609' ou '202609' -> date(2026, 9, 1)."""
    if len(aamm) == 4:
        aamm = "20" + aamm
    return date(int(aamm[:4]), int(aamm[4:6]), 1)


def _horas(valor: str) -> int:
    try:
        return int(float(valor or 0))
    except ValueError:
        return 0


def transformar_vinculo(registro: dict) -> dict:
    """Converte um registro do PF em vínculo, copiando SÓ os campos permitidos."""
    return {
        "cnes": registro["CNES"].zfill(7),
        "profissional": " ".join(registro["NOMEPROF"].split()),  # tira espaços duplos
        "cbo": registro["CBO"],
        "carga_horaria_semanal": (
            _horas(registro.get("HORAOUTR")) + _horas(registro.get("HORAHOSP"))
            + _horas(registro.get("HORA_AMB"))
        ),
    }
