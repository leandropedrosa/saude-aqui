import { forwardRef } from 'react'
import type { Especialidade, Filtros as TipoFiltros } from '../api'
import { formatarTitulo } from '../util'
import { IconeBusca, IconeLocalizacao } from './Icones'

interface Props {
  filtros: TipoFiltros
  aoMudarFiltros: (f: TipoFiltros) => void
  busca: string
  aoMudarBusca: (texto: string) => void
  bairros: string[]
  especialidades: Especialidade[]
  aoUsarLocalizacao: () => void
  localizando: boolean
  usandoLocalizacao: boolean
}

/** Agrupa as especialidades por categoria, para montar os <optgroup>. */
function porCategoria(lista: Especialidade[]): [string, Especialidade[]][] {
  const grupos = new Map<string, Especialidade[]>()
  for (const e of lista) {
    if (!grupos.has(e.categoria)) grupos.set(e.categoria, [])
    grupos.get(e.categoria)!.push(e)
  }
  return [...grupos.entries()]
}

/**
 * Busca por nome, filtros de especialidade e bairro e o botão de localização.
 * O ref aponta para o seletor de bairro, para receber o foco quando a
 * localização for negada.
 */
export const Filtros = forwardRef<HTMLSelectElement, Props>(function Filtros(props, refBairro) {
  const { filtros, aoMudarFiltros, busca, aoMudarBusca, bairros, especialidades } = props

  return (
    <div className="filtros">
      <label className="busca">
        <IconeBusca />
        <span className="visualmente-oculto">Buscar unidade por nome ou bairro</span>
        <input
          type="search"
          placeholder="Buscar unidade por nome ou bairro"
          value={busca}
          onChange={(e) => aoMudarBusca(e.target.value)}
        />
      </label>

      <div className="filtros-linha">
        <label>
          <span>Especialidade</span>
          <select
            value={filtros.especialidade}
            onChange={(e) => aoMudarFiltros({ ...filtros, especialidade: e.target.value })}
          >
            <option value="">Todas</option>
            {porCategoria(especialidades).map(([categoria, itens]) => (
              <optgroup key={categoria} label={categoria}>
                <option value={`categoria:${categoria}`}>{categoria}: todas</option>
                {itens.map((e) => (
                  <option key={e.cbo} value={`cbo:${e.cbo}`}>{e.nome}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label>
          <span>Bairro</span>
          <select
            ref={refBairro}
            value={filtros.bairro}
            onChange={(e) => aoMudarFiltros({ ...filtros, bairro: e.target.value })}
          >
            <option value="">Todos</option>
            {bairros.map((b) => (
              <option key={b} value={b}>{formatarTitulo(b)}</option>
            ))}
          </select>
        </label>
      </div>

      <button
        type="button"
        className={`botao-localizacao${props.usandoLocalizacao ? ' ativo' : ''}`}
        onClick={props.aoUsarLocalizacao}
        disabled={props.localizando}
      >
        <IconeLocalizacao />
        {props.localizando
          ? 'Obtendo localização…'
          : props.usandoLocalizacao ? 'Ordenado pela sua localização' : 'Usar minha localização'}
      </button>
    </div>
  )
})
