"""
Acesso ao banco de dados.

Usamos o psycopg 3 direto (sem ORM): as consultas ficam em SQL puro,
fácil de ler e de testar no psql. Um "pool" mantém poucas conexões
abertas e as reaproveita entre as requisições.
"""

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def abrir(url: str) -> None:
    """Abre o pool de conexões (chamado quando a API inicia)."""
    global _pool
    _pool = ConnectionPool(
        url,
        min_size=1,
        max_size=4,  # o Postgres aceita 20 conexões; a API usa no máximo 4
        kwargs={"row_factory": dict_row},  # cada linha vira um dicionário
        open=True,
    )


def fechar() -> None:
    """Fecha o pool (chamado quando a API encerra)."""
    if _pool is not None:
        _pool.close()


def consultar(sql: str, parametros: dict | None = None) -> list[dict]:
    """Executa um SELECT e devolve a lista de linhas como dicionários.

    Sempre passe valores em `parametros` (nunca concatene na string SQL):
    isso evita injeção de SQL.
    """
    assert _pool is not None, "o pool de conexões não foi aberto"
    with _pool.connection() as conexao:
        return conexao.execute(sql, parametros).fetchall()
