import { montarParametros, type Unidade } from './api'
import {
  agruparPorCategoria, filtrarPorTexto, formatarCompetencia, formatarData, formatarDistancia,
  formatarTelefone, formatarTitulo, linkComoChegar, numeroParaLigar,
} from './util'

describe('formatarDistancia', () => {
  it('usa metros abaixo de 1 km', () => {
    expect(formatarDistancia(0.02)).toBe('20 m')
    expect(formatarDistancia(0.654)).toBe('650 m')
  })
  it('usa km com vírgula a partir de 1 km', () => {
    expect(formatarDistancia(1.333)).toBe('1,3 km')
    expect(formatarDistancia(12)).toBe('12 km')
  })
})

it('linkComoChegar usa o link gratuito do Google Maps', () => {
  expect(linkComoChegar(-16.09, -47.93))
    .toBe('https://www.google.com/maps/dir/?api=1&destination=-16.09,-47.93')
})

it('formatarCompetencia', () => {
  expect(formatarCompetencia('2026-09')).toBe('setembro de 2026')
})

it('formatarData usa o fuso de Brasília', () => {
  expect(formatarData('2026-11-05T01:00:00Z')).toBe('04/11/2026') // 22h do dia 4 em Brasília
})

describe('formatarTitulo', () => {
  it('mantém siglas e põe partículas em minúsculas', () => {
    expect(formatarTitulo('UBS FAMILIA SQ 11')).toBe('UBS Familia SQ 11')
    expect(formatarTitulo('CAPS II CENTRO DE ATENCAO PSICOSSOCIAL')).toBe('CAPS II Centro de Atencao Psicossocial')
    expect(formatarTitulo('HOSPITAL FICTÍCIO')).toBe('Hospital Fictício')
  })
  it('não mexe em textos já corrigidos à mão', () => {
    expect(formatarTitulo('UBS Família Parque Nápoles A')).toBe('UBS Família Parque Nápoles A')
    expect(formatarTitulo('UBS Recreio Mossoró (horário estendido)')).toBe('UBS Recreio Mossoró (horário estendido)')
  })
})

it('formatarTelefone', () => {
  expect(formatarTelefone('6136054227')).toBe('(61) 3605-4227')
  expect(formatarTelefone('61 996767128')).toBe('(61) 99676-7128')
  expect(formatarTelefone('36252544')).toBe('(61) 3625-2544')  // sem DDD no CNES
  expect(formatarTelefone('192')).toBe('192')
})

it('numeroParaLigar acrescenta o DDD 61 quando falta', () => {
  expect(numeroParaLigar('36252544')).toBe('6136252544')
  expect(numeroParaLigar('(61) 3605-4227')).toBe('6136054227')
})

describe('montarParametros', () => {
  it('sem filtros e sem posição fica vazio', () => {
    expect(montarParametros({ bairro: '', especialidade: '' }, null).toString()).toBe('')
  })
  it('converte posição, bairro e especialidade', () => {
    const p = montarParametros(
      { bairro: 'JARDIM ABC', especialidade: 'cbo:225124' },
      { lat: -16.0921234, lng: -47.9261 },
    )
    expect(Object.fromEntries(p)).toEqual({
      lat: '-16.09212', lng: '-47.92610', bairro: 'JARDIM ABC', cbo: '225124',
    })
  })
  it('aceita categoria', () => {
    const p = montarParametros({ bairro: '', especialidade: 'categoria:Medicina' }, null)
    expect(p.get('categoria')).toBe('Medicina')
  })
})

const base: Omit<Unidade, 'id' | 'nome' | 'bairro'> = {
  cnes: '1', tipo: null, endereco: null, lat: null, lng: null, telefone: null,
  horario: null, distancia_km: null, profissionais: [],
}

it('filtrarPorTexto ignora acentos e maiúsculas e busca no bairro', () => {
  const unidades: Unidade[] = [
    { ...base, id: 1, nome: 'UBS FAMILIA PARQUE NAPOLIS A', bairro: 'PARQUE NAPOLIS A' },
    { ...base, id: 2, nome: 'UBS FAMILIA DOM BOSCO', bairro: 'DOM BOSCO' },
  ]
  expect(filtrarPorTexto(unidades, 'nápolis').map((u) => u.id)).toEqual([1])
  expect(filtrarPorTexto(unidades, '  bosco ').map((u) => u.id)).toEqual([2])
  expect(filtrarPorTexto(unidades, '')).toHaveLength(2)
})

it('agruparPorCategoria mantém a ordem', () => {
  const p = (nome: string, categoria: string) =>
    ({ nome, categoria, ocupacao: 'x', carga_horaria_semanal: 40 })
  const grupos = agruparPorCategoria([p('A', 'Enfermagem'), p('B', 'Medicina'), p('C', 'Enfermagem')])
  expect(grupos.map(([c, l]) => [c, l.map((x) => x.nome)])).toEqual([
    ['Enfermagem', ['A', 'C']],
    ['Medicina', ['B']],
  ])
})
