"""
Coletor do Saúde Aqui: importa os dados do CNES/DATASUS para o banco.

Passos de cada execução:
  1. Sincroniza as ocupações (db/ocupacoes.csv -> tabela ocupacao)
  2. Busca as unidades na API de dados abertos e aplica db/unidades.csv
  3. Consulta o portal de escalas da Prefeitura (só publicações de 2026 em diante):
     grava o horário de funcionamento e verifica se apareceu escala nova
  4. Descobre a competência (mês) mais recente no FTP do DATASUS
  5. Baixa o arquivo PF, calcula o SHA-256 e, se ele já foi importado, para aqui
  6. Descomprime, lê só os registros do município e grava os vínculos

Cada execução gera uma linha na tabela `coleta` (sucesso, sem_novidade ou erro),
com os avisos do portal na coluna `avisos`.

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
from fontes import (
    baixar_arquivo_portal, baixar_pf, buscar_escalas_portal, buscar_estabelecimentos,
    competencias_disponiveis, sha256,
)
from transformar import (
    aplicar_ajustes, competencia_para_data, eh_listagem_cnes, eh_unidade_publica, escalas_desde,
    horarios_por_cnes, ler_ajustes_unidades, ler_ocupacoes, mapa_portal_cnes, texto_primeira_pagina,
    transformar_estabelecimento, transformar_vinculo,
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
# Portal de escalas da Prefeitura (fonte complementar)
PORTAL_URL = os.environ.get("PORTAL_URL", "https://acessoainformacao.cidadeocidental.go.gov.br")
PORTAL_ARQUIVOS_URL = os.environ.get(
    "PORTAL_ARQUIVOS_URL", "https://nucleogov.s3.us-east-2.amazonaws.com/pf_cidadeocidental/outros/")
PORTAL_DESDE = date.fromisoformat(os.environ.get("PORTAL_DESDE", "2026-01-01"))


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


def classificar_arquivo(midia: str) -> str:
    """Baixa um anexo do portal e diz se é a listagem do CNES ou uma possível escala."""
    if not midia.lower().endswith(".pdf"):
        return "possivel_escala"  # planilhas e outros formatos: só podem ser escala
    texto = texto_primeira_pagina(baixar_arquivo_portal(PORTAL_ARQUIVOS_URL, midia))
    return "listagem_cnes" if eh_listagem_cnes(texto) else "possivel_escala"


def processar_portal(con: psycopg.Connection, ajustes: dict[str, dict]) -> list[str]:
    """Usa o portal da Prefeitura (publicações a partir de PORTAL_DESDE):

    * grava o horário de funcionamento escrito pela Prefeitura em unidade.horario_portal;
    * verifica cada arquivo novo UMA vez e avisa se não for a listagem do CNES.

    Devolve a lista de avisos (vazia quando não há nada de novo).
    """
    escalas = escalas_desde(buscar_escalas_portal(PORTAL_URL), PORTAL_DESDE)
    log.info("Portal: %d publicações desde %s", len(escalas), PORTAL_DESDE)

    # 1) Horários de funcionamento
    horarios = horarios_por_cnes(escalas, mapa_portal_cnes(ajustes))
    with con.cursor() as cur:
        cur.execute("UPDATE unidade SET horario_portal = NULL")
        cur.executemany("UPDATE unidade SET horario_portal = %s WHERE cnes = %s",
                        [(h, c) for c, h in horarios.items()])
    log.info("Portal: horário de funcionamento gravado em %d unidades", len(horarios))

    # 2) Arquivos novos (cada um é baixado e verificado só uma vez)
    ja_vistos = {m for (m,) in con.execute("SELECT midia FROM arquivo_portal").fetchall()}
    avisos = []
    for e in escalas:
        midia = e.get("midia")
        if not midia or midia in ja_vistos:
            continue
        ja_vistos.add(midia)
        try:
            tipo = classificar_arquivo(midia)
        except Exception as erro:  # um anexo com problema não derruba a coleta
            log.warning("Portal: não foi possível verificar %s: %s", midia, erro)
            tipo = "erro"
        con.execute("""
            INSERT INTO arquivo_portal (midia, portal_unidade_id, unidade_nome, data_inicio, data_fim, titulo, tipo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (midia, str(e.get("unidade_id")), (e.get("nome") or "").strip(),
              e.get("data_inicio"), e.get("data_fim"), e.get("titulo_midia"), tipo))
        if tipo == "possivel_escala":
            aviso = (f"Possível escala nova no portal: {(e.get('nome') or '').strip()} "
                     f"({e.get('data_inicio')} a {e.get('data_fim')}), arquivo {e.get('titulo_midia')}")
            log.warning(aviso)
            avisos.append(aviso)
    return avisos


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
            ajustes = ler_ajustes_unidades(PASTA_CSV / "unidades.csv")
            importar_unidades(con, estabelecimentos, ajustes)
            con.commit()

            # 3: portal da Prefeitura (complementar: se falhar, a coleta do CNES continua)
            try:
                avisos = processar_portal(con, ajustes)
                con.commit()
            except Exception as erro:
                con.rollback()
                log.warning("Portal da Prefeitura indisponível: %s", erro)
                avisos = [f"Portal da Prefeitura indisponível: {type(erro).__name__}: {erro}"[:500]]
            if avisos:
                atualizar_coleta(con, coleta_id, avisos="\n".join(avisos))

            # 4 e 5: arquivo de profissionais
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

            # 6: descomprime (DBC -> DBF) numa pasta temporária e importa
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
