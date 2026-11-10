import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import type { Unidade } from '../api'
import { ListaUnidades } from './ListaUnidades'

const unidades: Unidade[] = [
  {
    id: 1, cnes: '9000001', nome: 'UBS FICTÍCIA CENTRO', tipo: 'Unidade Básica de Saúde',
    endereco: 'Quadra 10', bairro: 'CENTRO', lat: -16.09, lng: -47.92, telefone: '6136000001',
    horario: 'Manhã e tarde', distancia_km: 0.4,
    profissionais: [
      { nome: 'Maria Exemplo', categoria: 'Medicina', ocupacao: 'Médico clínico', carga_horaria_semanal: 40 },
    ],
  },
  {
    id: 2, cnes: '9000005', nome: 'UBS FICTÍCIA SEM MAPA', tipo: 'Unidade Básica de Saúde',
    endereco: null, bairro: 'ZONA RURAL', lat: null, lng: null, telefone: null,
    horario: null, distancia_km: null, profissionais: [],
  },
]

/** Envolve a lista com o estado de seleção, como o App faz. */
function ListaComEstado() {
  const [sel, setSel] = useState<number | null>(null)
  return <ListaUnidades unidades={unidades} selecionada={sel} aoSelecionar={(id) => setSel((a) => (a === id ? null : id))} />
}

it('mostra nome, distância e abre os detalhes ao clicar', async () => {
  render(<ListaComEstado />)
  const botao = screen.getByRole('button', { name: /UBS Fictícia Centro/ })
  expect(botao).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByText('400 m')).toBeInTheDocument()

  await userEvent.click(botao)
  expect(botao).toHaveAttribute('aria-expanded', 'true')
  expect(screen.getByText('Profissionais vinculados a esta unidade')).toBeInTheDocument()
  expect(screen.getByText('Maria Exemplo')).toBeInTheDocument()
  expect(screen.getByText('Médico clínico · 40 h/semana')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Como chegar' }))
    .toHaveAttribute('href', 'https://www.google.com/maps/dir/?api=1&destination=-16.09,-47.92')
  expect(screen.getByRole('link', { name: '(61) 3600-0001' })).toHaveAttribute('href', 'tel:6136000001')
})

it('nunca usa a expressão "disponíveis agora"', async () => {
  const { container } = render(<ListaComEstado />)
  await userEvent.click(screen.getByRole('button', { name: /UBS Fictícia Centro/ }))
  expect(container.textContent).not.toMatch(/dispon[ií]ve(l|is) agora/i)
})

it('unidade sem coordenadas não tem "Como chegar" e avisa a falta de profissionais', async () => {
  render(<ListaComEstado />)
  await userEvent.click(screen.getByRole('button', { name: /Sem Mapa/ }))
  expect(screen.queryByRole('link', { name: 'Como chegar' })).not.toBeInTheDocument()
  expect(screen.getByText(/não tem localização no mapa/)).toBeInTheDocument()
  expect(screen.getByText(/Nenhum profissional de atendimento/)).toBeInTheDocument()
})

it('as setas do teclado passam de um cartão para o outro', async () => {
  render(<ListaComEstado />)
  const [primeiro, segundo] = screen.getAllByRole('button')
  primeiro.focus()
  await userEvent.keyboard('{ArrowDown}')
  expect(segundo).toHaveFocus()
  await userEvent.keyboard('{ArrowUp}')
  expect(primeiro).toHaveFocus()
  await userEvent.keyboard('{Enter}')
  expect(primeiro).toHaveAttribute('aria-expanded', 'true')
})
