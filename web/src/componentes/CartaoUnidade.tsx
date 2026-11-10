import { useEffect, useRef } from 'react'
import type { Unidade } from '../api'
import {
  agruparPorCategoria, formatarDistancia, formatarTelefone,
  formatarTitulo, linkComoChegar, numeroParaLigar,
} from '../util'
import { IconeDoTipo } from './Icones'

interface Props {
  unidade: Unidade
  selecionada: boolean
  aoSelecionar: (id: number) => void
}

/**
 * Cartão de uma unidade na lista. Fechado, mostra nome, distância e tipo.
 * Selecionado, mostra também endereço, horário, telefone, "Como chegar" e
 * os profissionais vinculados.
 */
export function CartaoUnidade({ unidade: u, selecionada, aoSelecionar }: Props) {
  const ref = useRef<HTMLLIElement>(null)

  // Quando a unidade é escolhida pelo mapa, rola a lista até o cartão
  useEffect(() => {
    if (selecionada) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selecionada])

  const idDetalhes = `detalhes-${u.id}`
  const temMapa = u.lat !== null && u.lng !== null

  return (
    <li ref={ref} className={`cartao${selecionada ? ' selecionado' : ''}`}>
      <button
        type="button"
        className="cartao-topo"
        aria-expanded={selecionada}
        aria-controls={idDetalhes}
        onClick={() => aoSelecionar(u.id)}
        data-unidade={u.id}
      >
        <span className="cartao-icone"><IconeDoTipo tipo={u.tipo} /></span>
        <span className="cartao-texto">
          <span className="cartao-nome">{formatarTitulo(u.nome)}</span>
          <span className="cartao-etiquetas">
            {u.tipo && <span className="etiqueta">{u.tipo}</span>}
            {u.bairro && <span className="cartao-bairro">{formatarTitulo(u.bairro)}</span>}
          </span>
        </span>
        {u.distancia_km !== null && (
          <span className="distancia" aria-label={`a ${formatarDistancia(u.distancia_km)}`}>
            {formatarDistancia(u.distancia_km)}
          </span>
        )}
      </button>

      {selecionada && (
        <div className="cartao-detalhes" id={idDetalhes}>
          {u.endereco && <p><strong>Endereço:</strong> {u.endereco}{u.bairro && `, ${formatarTitulo(u.bairro)}`}</p>}
          {u.horario && <p><strong>Funcionamento:</strong> {u.horario}</p>}
          <p>
            <strong>Telefone:</strong>{' '}
            {u.telefone
              ? <a href={`tel:${numeroParaLigar(u.telefone)}`}>{formatarTelefone(u.telefone)}</a>
              : 'não informado'}
          </p>

          <div className="cartao-acoes">
            {temMapa ? (
              <a className="botao" href={linkComoChegar(u.lat!, u.lng!)} target="_blank" rel="noopener noreferrer">
                Como chegar
              </a>
            ) : (
              <span className="sem-mapa">Esta unidade não tem localização no mapa.</span>
            )}
          </div>

          <h3>Profissionais vinculados a esta unidade</h3>
          {u.profissionais.length === 0 ? (
            <p className="vazio">Nenhum profissional de atendimento cadastrado no CNES.</p>
          ) : (
            agruparPorCategoria(u.profissionais).map(([categoria, lista]) => (
              <div key={categoria} className="grupo-profissionais">
                <h4>{categoria}</h4>
                <ul>
                  {lista.map((p, i) => (
                    <li key={`${p.nome}-${p.ocupacao}-${i}`}>
                      <span className="prof-nome">{p.nome}</span>
                      <span className="prof-detalhe">
                        {p.ocupacao} · {p.carga_horaria_semanal} h/semana
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>
      )}
    </li>
  )
}
