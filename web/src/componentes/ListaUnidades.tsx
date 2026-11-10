import type { KeyboardEvent } from 'react'
import type { Unidade } from '../api'
import { CartaoUnidade } from './CartaoUnidade'

interface Props {
  unidades: Unidade[]
  selecionada: number | null
  aoSelecionar: (id: number) => void
}

/**
 * Lista de cartões. Navegação por teclado: Tab chega na lista; as setas
 * para cima/baixo passam de um cartão para o outro; Enter abre/fecha.
 */
export function ListaUnidades({ unidades, selecionada, aoSelecionar }: Props) {
  function aoTeclar(e: KeyboardEvent<HTMLUListElement>) {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    const botoes = [...e.currentTarget.querySelectorAll<HTMLButtonElement>('.cartao-topo')]
    const atual = botoes.indexOf(document.activeElement as HTMLButtonElement)
    if (atual === -1) return
    e.preventDefault()
    const proximo = e.key === 'ArrowDown' ? Math.min(atual + 1, botoes.length - 1) : Math.max(atual - 1, 0)
    botoes[proximo].focus()
  }

  return (
    <ul className="lista" aria-label="Unidades de saúde" onKeyDown={aoTeclar}>
      {unidades.map((u) => (
        <CartaoUnidade
          key={u.id}
          unidade={u}
          selecionada={u.id === selecionada}
          aoSelecionar={aoSelecionar}
        />
      ))}
    </ul>
  )
}
