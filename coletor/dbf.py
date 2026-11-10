"""
Leitor mínimo de arquivos DBF (dBase), o formato dos dados do DATASUS.

Por que não usar uma biblioteca pronta (dbfread)? Os DBFs do DATASUS têm
o cabeçalho fora do padrão: o "tamanho do cabeçalho" não bate com o byte
terminador 0x0D, e a dbfread falha. Ler o formato à mão é simples e
também é didático.

Formato DBF, resumido:
    bytes 0-31   cabeçalho geral: nº de registros (4-7), tamanho do
                 cabeçalho (8-9), tamanho de cada registro (10-11)
    a cada 32    descrição de um campo: nome (0-10), tamanho (16)
    depois       os registros, um atrás do outro, todos do mesmo tamanho;
                 o 1º byte de cada registro marca se ele foi apagado ('*')
"""

import struct
from collections.abc import Iterator
from pathlib import Path


def ler_registros(caminho: Path, codificacao: str = "latin-1") -> Iterator[dict[str, str]]:
    """Lê o DBF registro a registro (sem carregar o arquivo todo na memória).

    Cada registro vira um dicionário {nome_do_campo: texto}. Os valores
    voltam como texto sem espaços nas pontas; a conversão fica com quem chama.
    """
    with open(caminho, "rb") as arquivo:
        cabecalho = arquivo.read(32)
        total, tamanho_cabecalho, tamanho_registro = struct.unpack("<IHH", cabecalho[4:12])

        # Os campos ficam entre o byte 32 e o fim do cabeçalho, 32 bytes cada
        campos: list[tuple[str, int]] = []
        for _ in range((tamanho_cabecalho - 33) // 32):
            descricao = arquivo.read(32)
            nome = descricao[:11].split(b"\0")[0].decode("ascii")
            campos.append((nome, descricao[16]))

        arquivo.seek(tamanho_cabecalho)
        for _ in range(total):
            bruto = arquivo.read(tamanho_registro)
            if len(bruto) < tamanho_registro:
                break  # arquivo truncado: para sem erro
            if bruto[0:1] == b"*":
                continue  # registro marcado como apagado
            registro, posicao = {}, 1
            for nome, tamanho in campos:
                registro[nome] = bruto[posicao:posicao + tamanho].decode(codificacao).strip()
                posicao += tamanho
            yield registro
