"""
Pequenas funções de formatação de texto para exibição.
"""

import unicodedata

# Palavras que ficam em minúsculas no meio de nomes próprios
_PARTICULAS = {"da", "das", "de", "di", "do", "dos", "du", "e"}

# Texto curto para os códigos de turno do CNES encontrados em Cidade Ocidental
# (ver coletor/amostras/ACHADOS.md, seção 8). Códigos fora desta lista usam a
# descrição oficial que vem do CNES.
TURNOS = {
    "02": "Somente à tarde",
    "03": "Manhã e tarde",
    "04": "Manhã, tarde e noite",
    "06": "24 horas (inclui fins de semana e feriados)",
}


def formatar_nome(nome: str) -> str:
    """'MARIA DA SILVA E SOUZA' -> 'Maria da Silva e Souza'."""
    palavras = nome.strip().lower().split()
    return " ".join(
        p if (i > 0 and p in _PARTICULAS) else p.capitalize()
        for i, p in enumerate(palavras)
    )


def texto_horario(horario: str | None, turno_codigo: str | None,
                  turno_descricao: str | None, horario_portal: str | None = None) -> str | None:
    """Ordem de prioridade: 1) digitado em unidades.csv; 2) portal da Prefeitura;
    3) turno do CNES (texto curto ou descrição oficial)."""
    if horario:
        return horario
    if horario_portal:
        return horario_portal
    if turno_codigo in TURNOS:
        return TURNOS[turno_codigo]
    if turno_descricao:
        return turno_descricao.capitalize()
    return None


def chave_ordenacao(texto: str) -> str:
    """Chave para ordem alfabética "humana": 'São Matheus' fica antes de 'Setor'."""
    sem_acento = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()
