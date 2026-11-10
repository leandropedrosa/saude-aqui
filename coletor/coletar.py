"""
Coletor do Saúde Aqui: importa os dados do CNES/DATASUS para o banco.

Passos de cada execução:
  1. Sincroniza as ocupações (db/ocupacoes.csv -> tabela ocupacao)
  2. Busca as unidades na API de dados abertos e aplica db/unidades.csv
  3. Descobre a competência (mês) mais recente no FTP do DATASUS
  4. Baixa o arquivo PF, calcula o SHA-256 e, se ele já foi importado, para aqui
  5. Descomprime, lê só os registros do município e grava os vínculos

Cada execução gera uma linha na tabela `coleta` (sucesso, sem_novidade ou erro).

Uso:
    python coletar.py                    # execução normal (é o que o agendador roda)
    python coletar.py --forcar           # reimporta mesmo que o arquivo já tenha sido importado
    python coletar.py --competencia 2608 # importa uma competência específica (AAMM)

Com Docker:
    docker compose run --rm coletor python coletar.py
"""

import argparse
import logging
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import datasus_dbc
import psycopg

from dbf import ler_registros
from fontes import baixar_pf, buscar_estabelecimentos, competencias_disponiveis, sha256
from transformar import (
    aplicar_ajustes, competencia_para_data, eh_unidade_publica, ler_ajustes_unidades,
    ler_ocupacoes, transformar_estabelecimento, transformar_vinculo,
)

log = logging.getLogger("coletor")

# ---------------------------------------------------------------- configuração (variáveis de ambiente)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
CNES_FTP_PF = os.environ.get("CNES_FTP_PF", "ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/PF/")
CNES_API_URL = os.environ.get("CNES_API_URL", "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos")
MUNICIPIO_IBGE = os.environ.get("MUNICIPIO_IBGE", "520549")
UF = os.environ.get("UF", "GO")
CNPJ_MANTENEDORA = os.environ.get("CNPJ_MANTENEDORA", "36862621000121")
# Pasta com unidades.csv e ocupacoes.csv (na imagem Docker: /app/db)
PASTA_CSV = Path(os.environ.get("PASTA_CSV", Path(__file__).resolve().parent.parent / "db"))
# Onde guardar os arquivos originais baixados (volume no Docker)
PASTA_BRUTOS = Path(os.environ.get("PASTA_BRUTOS", "/dados/brutos"))


# ---------------------------------------------------------------- etapas que mexem no banco

def sincronizar_ocupacoes(con: psycopg.Connection, ocupacoes: list[dict]) -> int:
    """Insere ou atualiza as ocupações a partir do CSV (nunca apaga)."""
    with con.cursor() as cur:
        cur.executemany("""
            INSERT INTO ocupacao (cbo, nome, categoria, atendimento)
            VALUES (%(cbo)s, %(nome)s, %(categoria)s, %(atendimento)s)
            ON CONFLICT (cbo) DO UPDATE
               SET nome = EXCLUDED.nome, categoria = EXCLUDED.categoria,
                   atendimento = EXCLUDED.atendimento
        """, ocupacoes)
    log.info("Ocupações sincronizadas: %d (%d aparecem no site)",
             len(ocupacoes), sum(o["atendimento"] for o in ocupacoes))
    return len(ocupacoes)


def importar_unidades(con: psycopg.Connection, estabelecimentos: list[dict],
                      ajustes: dict[str, dict]) -> int:
    """Grava as unidades públicas (upsert pelo CNES), já com os ajustes manuais."""
    publicas = [transformar_estabelecimento(e) for e in estabelecimentos
                if eh_unidade_publica(e, CNPJ_MANTENEDORA)]
    cnes_api = {u["cnes"] for u in publicas}

    for cnes in sorted(set(ajustes) - cnes_api):
        log.warning("unidades.csv: CNES %s (%s) não veio na API do CNES",
                    cnes, ajustes[cnes].get("nome_cnes"))
    for u in publicas:
        if u["cnes"] not in ajustes:
            log.warning("Unidade nova no CNES, adicione ao unidades.csv: %s %s", u["cnes"], u["nome"])

    linhas = [aplicar_ajustes(u, ajustes.get(u["cnes"])) for u in publicas]
    with con.cursor() as cur:
        cur.executemany("""
            INSERT INTO unidade (cnes, nome, tipo, endereco, bairro, lat, lng, telefone,
                                 turno_codigo, turno_descricao, horario, ativo, atualizado_em)
            VALUES (%(cnes)s, %(nome)s, %(tipo)s, %(endereco)s, %(bairro)s, %(lat)s, %(lng)s,
                    %(telefone)s, %(turno_codigo)s, %(turno_descricao)s, %(horario)s, %(ativo)s, now())
            ON CONFLICT (cnes) DO UPDATE SET
                nome = EXCLUDED.nome, tipo = EXCLUDED.tipo, endereco = EXCLUDED.endereco,
                bairro = EXCLUDED.bairro, lat = EXCLUDED.lat, lng = EXCLUDED.lng,
                telefone = EXCLUDED.telefone, turno_codigo = EXCLUDED.turno_codigo,
                turno_descricao = EXCLUDED.turno_descricao, horario = EXCLUDED.horario,
                ativo = EXCLUDED.ativo, atualizado_em = now()
        """, linhas)
    log.info("Unidades públicas gravadas: %d (%d visíveis no site)",
             len(linhas), sum(u["ativo"] for u in linhas))
    return len(linhas)


def importar_vinculos(con: psycopg.Connection, registros, competencia: date, coleta_id: int) -> int:
    """Grava os vínculos do município na competência (substitui os que já existiam nela).

    Só entram vínculos de unidades cadastradas na tabela `unidade` (públicas)
    e de ocupações com atendimento = TRUE.
    """
    with con.cursor() as cur:
        unidades = dict(cur.execute("SELECT cnes, id FROM unidade").fetchall())
        cbos = {c for (c,) in cur.execute("SELECT cbo FROM ocupacao WHERE atendimento").fetchall()}

    lidos = fora_unidade = fora_ocupacao = 0
    linhas = []
    for registro in registros:
        if registro.get("CODUFMUN") != MUNICIPIO_IBGE:
            continue
        lidos += 1
        v = transformar_vinculo(registro)
        if v["cnes"] not in unidades:
            fora_unidade += 1
            continue
        if v["cbo"] not in cbos:
            fora_ocupacao += 1
            continue
        linhas.append({**v, "unidade_id": unidades[v["cnes"]],
                       "competencia": competencia, "coleta_id": coleta_id})

    with con.cursor() as cur:
        # Reprocessar a mesma competência não duplica: apaga e grava de novo (na mesma transação)
        cur.execute("DELETE FROM vinculo WHERE competencia = %s", (competencia,))
        # Mesma pessoa, unidade e ocupação em duas linhas (ex.: dois tipos de vínculo): soma as horas
        cur.executemany("""
            INSERT INTO vinculo (unidade_id, profissional, cbo, carga_horaria_semanal, competencia, coleta_id)
            VALUES (%(unidade_id)s, %(profissional)s, %(cbo)s, %(carga_horaria_semanal)s,
                    %(competencia)s, %(coleta_id)s)
            ON CONFLICT ON CONSTRAINT uq_vinculo DO UPDATE
               SET carga_horaria_semanal = vinculo.carga_horaria_semanal + EXCLUDED.carga_horaria_semanal
        """, linhas)

    log.info("Registros do município: %d | gravados: %d | de unidades privadas/fora da lista: %d | "
             "de ocupações fora do site: %d", lidos, len(linhas), fora_unidade, fora_ocupacao)
    return len(linhas)


def ja_importado(con: psycopg.Connection, hash_arquivo: str) -> bool:
    linha = con.execute(
        "SELECT 1 FROM coleta WHERE hash_sha256 = %s AND status = 'sucesso' LIMIT 1", (hash_arquivo,)
    ).fetchone()
    return linha is not None


def atualizar_coleta(con: psycopg.Connection, coleta_id: int, **campos) -> None:
    """Atualiza colunas da linha da coleta atual e confirma (commit) na hora."""
    atribuicoes = ", ".join(f"{c} = %({c})s" for c in campos)
    con.execute(f"UPDATE coleta SET {atribuicoes} WHERE id = %(id)s", {**campos, "id": coleta_id})
    con.commit()


# ---------------------------------------------------------------- programa principal

def executar(forcar: bool = False, competencia_aamm: str | None = None) -> int:
    """Roda uma coleta completa. Devolve 0 (ok) ou 1 (erro), como código de saída."""
    with psycopg.connect(DATABASE_URL) as con:
        coleta_id = con.execute(
            "INSERT INTO coleta (fonte, status) VALUES ('CNES/DATASUS', 'em_andamento') RETURNING id"
        ).fetchone()[0]
        con.commit()
        log.info("Coleta %d iniciada", coleta_id)

        try:
            # 1 e 2: ocupações e unidades (sempre: os CSVs podem ter mudado)
            sincronizar_ocupacoes(con, ler_ocupacoes(PASTA_CSV / "ocupacoes.csv"))
            estabelecimentos = buscar_estabelecimentos(CNES_API_URL, MUNICIPIO_IBGE)
            importar_unidades(con, estabelecimentos, ler_ajustes_unidades(PASTA_CSV / "unidades.csv"))
            con.commit()

            # 3 e 4: arquivo de profissionais
            aamm = competencia_aamm or competencias_disponiveis(CNES_FTP_PF, UF)[0]
            arquivo = baixar_pf(CNES_FTP_PF, UF, aamm, PASTA_BRUTOS)
            hash_arquivo = sha256(arquivo)
            competencia = competencia_para_data(aamm)
            atualizar_coleta(con, coleta_id, competencia=competencia,
                             url_origem=f"{CNES_FTP_PF}{arquivo.name}", hash_sha256=hash_arquivo)

            if not forcar and ja_importado(con, hash_arquivo):
                log.info("Arquivo %s já importado antes (mesmo SHA-256). Nada a fazer.", arquivo.name)
                atualizar_coleta(con, coleta_id, status="sem_novidade")
                return 0

            # 5: descomprime (DBC -> DBF) numa pasta temporária e importa
            with tempfile.TemporaryDirectory() as pasta_tmp:
                dbf = Path(pasta_tmp) / arquivo.with_suffix(".dbf").name
                datasus_dbc.decompress(str(arquivo), str(dbf))
                total = importar_vinculos(con, ler_registros(dbf), competencia, coleta_id)

            con.commit()
            atualizar_coleta(con, coleta_id, status="sucesso", registros_importados=total)
            log.info("Coleta %d concluída: competência %s, %d vínculos", coleta_id, aamm, total)
            return 0

        except Exception as erro:  # registra qualquer falha na tabela coleta
            log.exception("Coleta %d falhou", coleta_id)
            con.rollback()
            atualizar_coleta(con, coleta_id, status="erro", erro=f"{type(erro).__name__}: {erro}"[:2000])
            return 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Importa os dados do CNES/DATASUS")
    parser.add_argument("--forcar", action="store_true", help="reimporta mesmo sem novidade")
    parser.add_argument("--competencia", help="competência no formato AAMM (ex.: 2609)")
    args = parser.parse_args()
    if not DATABASE_URL:
        sys.exit("Defina a variável DATABASE_URL")
    sys.exit(executar(forcar=args.forcar, competencia_aamm=args.competencia))


if __name__ == "__main__":
    main()
