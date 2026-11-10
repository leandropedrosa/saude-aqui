// =====================================================================
// Comunicação com a API (/api). Os tipos espelham os modelos da API
// (api/app/modelos.py). Se mudar lá, mude aqui também.
// =====================================================================

export interface Profissional {
  nome: string
  categoria: string // ex.: "Medicina"
  ocupacao: string // ex.: "Médico pediatra"
  carga_horaria_semanal: number
}

export interface Unidade {
  id: number
  cnes: string
  nome: string
  tipo: string | null
  endereco: string | null
  bairro: string | null
  lat: number | null
  lng: number | null
  telefone: string | null
  horario: string | null
  distancia_km: number | null
  profissionais: Profissional[]
}

export interface RespostaUnidades {
  competencia: string | null // "2026-09"
  total: number
  unidades: Unidade[]
}

export interface Status {
  ultima_atualizacao: string | null
  ultima_verificacao: string | null
  competencia: string | null
  unidades: number
  vinculos: number
}

export interface Especialidade {
  cbo: string
  nome: string
  categoria: string
  total: number
}

/** Filtros escolhidos pela pessoa. */
export interface Filtros {
  bairro: string // "" = todos
  // "" = todas | "categoria:Medicina" | "cbo:225124"
  especialidade: string
}

export interface Posicao {
  lat: number
  lng: number
}

async function obter<T>(caminho: string, sinal?: AbortSignal): Promise<T> {
  const resposta = await fetch(`/api${caminho}`, { signal: sinal })
  if (!resposta.ok) {
    throw new Error(`Erro ${resposta.status} ao consultar ${caminho}`)
  }
  return resposta.json() as Promise<T>
}

export const buscarStatus = () => obter<Status>('/status')
export const buscarBairros = () => obter<string[]>('/bairros')
export const buscarEspecialidades = () => obter<Especialidade[]>('/especialidades')

/** Monta a query string de /unidades/proximas a partir dos filtros e da posição. */
export function montarParametros(filtros: Filtros, posicao: Posicao | null): URLSearchParams {
  const p = new URLSearchParams()
  if (posicao) {
    p.set('lat', posicao.lat.toFixed(5))
    p.set('lng', posicao.lng.toFixed(5))
  }
  if (filtros.bairro) p.set('bairro', filtros.bairro)
  if (filtros.especialidade) {
    // "categoria:Medicina" -> categoria=Medicina ; "cbo:225124" -> cbo=225124
    const [tipo, valor] = filtros.especialidade.split(':', 2)
    if ((tipo === 'categoria' || tipo === 'cbo') && valor) p.set(tipo, valor)
  }
  return p
}

export function buscarUnidades(filtros: Filtros, posicao: Posicao | null, sinal?: AbortSignal) {
  const consulta = montarParametros(filtros, posicao).toString()
  return obter<RespostaUnidades>(`/unidades/proximas${consulta ? `?${consulta}` : ''}`, sinal)
}
