// =====================================================================
// Funções pequenas de formatação (testadas em util.test.ts)
// =====================================================================

import type { Profissional, Unidade } from './api'

/** 0.65 -> "650 m" ; 1.333 -> "1,3 km" */
export function formatarDistancia(km: number): string {
  if (km < 1) return `${Math.round((km * 1000) / 10) * 10} m`
  return `${km.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} km`
}

/** Link gratuito que abre o Google Maps (ou o app no celular) com a rota até o destino. */
export function linkComoChegar(lat: number, lng: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
}

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho',
  'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

/** "2026-09" -> "setembro de 2026" */
export function formatarCompetencia(competencia: string): string {
  const [ano, mes] = competencia.split('-').map(Number)
  return `${MESES[mes - 1]} de ${ano}`
}

/** "2026-11-05T06:15:00-03:00" -> "05/11/2026" (no fuso de Brasília) */
export function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' })
}

// Siglas que devem continuar em maiúsculas e palavras que ficam em minúsculas
const SIGLAS = new Set(['UBS', 'UBSF', 'SAMU', 'CAPS', 'CTA', 'SAE', 'SQ', 'CEO', 'ABC',
  'UPA', 'CAF', 'I', 'II', 'III', 'IV'])
const PARTICULAS = new Set(['a', 'as', 'da', 'das', 'de', 'do', 'dos', 'e', 'em'])

/** "UBS FAMILIA DOM BOSCO" -> "UBS Familia Dom Bosco" (o CNES manda tudo em maiúsculas). */
export function formatarTitulo(texto: string): string {
  return texto
    .trim()
    .split(/\s+/)
    .map((palavra, i) => {
      if (SIGLAS.has(palavra.toUpperCase())) return palavra.toUpperCase()
      const minuscula = palavra.toLowerCase()
      if (i > 0 && PARTICULAS.has(minuscula)) return minuscula
      return minuscula.charAt(0).toUpperCase() + minuscula.slice(1)
    })
    .join(' ')
}

/** Remove acentos e passa para minúsculas, para comparar textos ("Nápoles" == "napoles"). */
export function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/** Filtra as unidades pelo texto digitado na busca (nome ou bairro). */
export function filtrarPorTexto(unidades: Unidade[], texto: string): Unidade[] {
  const busca = normalizar(texto.trim())
  if (!busca) return unidades
  return unidades.filter((u) => normalizar(`${u.nome} ${u.bairro ?? ''}`).includes(busca))
}

/** Agrupa os profissionais por categoria, mantendo a ordem que veio da API. */
export function agruparPorCategoria(profissionais: Profissional[]): [string, Profissional[]][] {
  const grupos = new Map<string, Profissional[]>()
  for (const p of profissionais) {
    if (!grupos.has(p.categoria)) grupos.set(p.categoria, [])
    grupos.get(p.categoria)!.push(p)
  }
  return [...grupos.entries()]
}

// Todas as unidades ficam em Cidade Ocidental (GO): DDD 61
const DDD_PADRAO = '61'

/** Só os dígitos, com DDD: o CNES às vezes manda o telefone sem DDD ("36252544"). */
export function numeroParaLigar(telefone: string): string {
  const d = telefone.replace(/\D/g, '')
  return d.length === 8 || d.length === 9 ? DDD_PADRAO + d : d
}

/** "6136054227" -> "(61) 3605-4227" ; "36252544" -> "(61) 3625-2544" ; outros voltam como vieram. */
export function formatarTelefone(telefone: string): string {
  const d = numeroParaLigar(telefone)
  if (d.length === 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`
  if (d.length === 11) return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`
  return telefone
}
