// Ícones em SVG embutido (sem biblioteca extra). aria-hidden: são decorativos.

type Props = { tamanho?: number }

/** Casa com cruz: unidades básicas, academias, CAPS etc. */
export function IconeUnidade({ tamanho = 28 }: Props) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M12 3 2 11h3v10h14V11h3L12 3Zm1.5 15h-3v-3h-3v-3h3V9h3v3h3v3h-3v3Z" />
    </svg>
  )
}

/** Prédio com "H": hospitais. */
export function IconeHospital({ tamanho = 28 }: Props) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M4 3h16v18h-6v-4h-4v4H4V3Zm5 3v8h2v-3h2v3h2V6h-2v3h-2V6H9Z" />
    </svg>
  )
}

/** Mira: "usar minha localização". */
export function IconeLocalizacao({ tamanho = 22 }: Props) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm9 3h-2.07A7 7 0 0 0 13 5.07V3h-2v2.07A7 7 0 0 0 5.07 11H3v2h2.07A7 7 0 0 0 11 18.93V21h2v-2.07A7 7 0 0 0 18.93 13H21v-2Zm-9 6a5 5 0 1 1 0-10 5 5 0 0 1 0 10Z" />
    </svg>
  )
}

/** Lupa: campo de busca. */
export function IconeBusca({ tamanho = 20 }: Props) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M10 3a7 7 0 0 1 5.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1 1 10 3Zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z" />
    </svg>
  )
}

/** Escolhe o ícone pelo tipo da unidade. */
export function IconeDoTipo({ tipo, tamanho }: { tipo: string | null } & Props) {
  return tipo?.toLowerCase().includes('hospital')
    ? <IconeHospital tamanho={tamanho} />
    : <IconeUnidade tamanho={tamanho} />
}
