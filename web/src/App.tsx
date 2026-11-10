// =====================================================================
// Tela principal: mapa + painel (lista lateral no desktop, gaveta
// inferior no celular). Aqui fica o "estado" do site: filtros, posição,
// unidade selecionada. Os componentes só exibem e avisam mudanças.
// =====================================================================

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  buscarBairros, buscarEspecialidades, buscarStatus, buscarUnidades,
  type Especialidade, type Filtros as TipoFiltros, type Posicao, type Status, type Unidade,
} from './api'
import { Aviso } from './componentes/Aviso'
import { Filtros } from './componentes/Filtros'
import { IconeLocalizacao } from './componentes/Icones'
import { ListaUnidades } from './componentes/ListaUnidades'
import { Mapa } from './componentes/Mapa'
import { filtrarPorTexto } from './util'

const FILTROS_INICIAIS: TipoFiltros = { bairro: '', especialidade: '' }

export default function App() {
  // Dados carregados uma vez
  const [status, setStatus] = useState<Status | null>(null)
  const [bairros, setBairros] = useState<string[]>([])
  const [especialidades, setEspecialidades] = useState<Especialidade[]>([])

  // Escolhas da pessoa
  const [filtros, setFiltros] = useState<TipoFiltros>(FILTROS_INICIAIS)
  const [busca, setBusca] = useState('')
  const [posicao, setPosicao] = useState<Posicao | null>(null)
  const [selecionada, setSelecionada] = useState<number | null>(null)

  // Resultado da consulta
  const [unidades, setUnidades] = useState<Unidade[]>([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState<string | null>(null)
  const [tentativa, setTentativa] = useState(0) // muda para "tentar de novo"

  // Localização e gaveta (celular)
  const [localizando, setLocalizando] = useState(false)
  const [mensagemLocal, setMensagemLocal] = useState<string | null>(null)
  const [gavetaCheia, setGavetaCheia] = useState(false)
  const refBairro = useRef<HTMLSelectElement>(null)

  // 1) Dados de apoio: status, bairros e especialidades (uma vez só)
  useEffect(() => {
    buscarStatus().then(setStatus).catch(() => setStatus(null))
    buscarBairros().then(setBairros).catch(() => setBairros([]))
    buscarEspecialidades().then(setEspecialidades).catch(() => setEspecialidades([]))
  }, [])

  // 2) Unidades: consulta de novo sempre que filtros ou posição mudarem.
  //    O AbortController cancela a consulta anterior se a pessoa mudar o filtro rápido.
  useEffect(() => {
    const controle = new AbortController()
    setCarregando(true)
    setErro(null)
    buscarUnidades(filtros, posicao, controle.signal)
      .then((r) => {
        setUnidades(r.unidades)
        // Se a unidade selecionada sumiu com o filtro, desmarca
        setSelecionada((atual) => (r.unidades.some((u) => u.id === atual) ? atual : null))
      })
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setErro('Não foi possível carregar as unidades.')
      })
      .finally(() => {
        if (!controle.signal.aborted) setCarregando(false)
      })
    return () => controle.abort()
  }, [filtros, posicao, tentativa])

  // Clicar de novo na mesma unidade fecha o cartão
  const aoSelecionar = useCallback((id: number) => {
    setSelecionada((atual) => (atual === id ? null : id))
  }, [])

  function usarLocalizacao() {
    if (!('geolocation' in navigator)) {
      setMensagemLocal('Seu navegador não informa a localização. Escolha seu bairro na lista.')
      refBairro.current?.focus()
      return
    }
    setLocalizando(true)
    setMensagemLocal(null)
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setPosicao({ lat: p.coords.latitude, lng: p.coords.longitude })
        setLocalizando(false)
      },
      () => {
        setLocalizando(false)
        setMensagemLocal('Não foi possível obter sua localização. Escolha seu bairro na lista.')
        refBairro.current?.focus()
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 5 * 60 * 1000 },
    )
  }

  const visiveis = filtrarPorTexto(unidades, busca)
  const temFiltro = !!(filtros.bairro || filtros.especialidade || busca)

  return (
    <div className={`app${gavetaCheia ? ' gaveta-cheia' : ''}`}>
      <div className="area-mapa">
        <Mapa unidades={visiveis} selecionada={selecionada} aoSelecionar={aoSelecionar} posicao={posicao} />
        <button
          type="button"
          className="botao-mapa-localizar"
          onClick={usarLocalizacao}
          aria-label="Usar minha localização"
          title="Usar minha localização"
        >
          <IconeLocalizacao />
        </button>
      </div>

      <aside className="painel" aria-label="Busca e lista de unidades">
        <button
          type="button"
          className="alca"
          onClick={() => setGavetaCheia((v) => !v)}
          aria-label={gavetaCheia ? 'Mostrar mais o mapa' : 'Expandir a lista'}
          aria-expanded={gavetaCheia}
        >
          <span />
        </button>

        <header className="cabecalho">
          <h1>Saúde Aqui</h1>
          <p>Unidades públicas de saúde de Cidade Ocidental (GO)</p>
        </header>

        <Aviso status={status} />

        {/* Daqui para baixo o conteúdo rola; cabeçalho e aviso ficam sempre visíveis */}
        <div className="painel-rolagem">
        <Filtros
          ref={refBairro}
          filtros={filtros}
          aoMudarFiltros={setFiltros}
          busca={busca}
          aoMudarBusca={setBusca}
          bairros={bairros}
          especialidades={especialidades}
          aoUsarLocalizacao={usarLocalizacao}
          localizando={localizando}
          usandoLocalizacao={posicao !== null}
        />
        {mensagemLocal && <p className="mensagem-local" role="alert">{mensagemLocal}</p>}

        <div className="lista-cabecalho">
          <h2>{posicao ? 'Unidades mais próximas' : 'Unidades de saúde'}</h2>
          <p aria-live="polite">
            {carregando ? 'Carregando…' : `${visiveis.length} ${visiveis.length === 1 ? 'encontrada' : 'encontradas'}`}
          </p>
        </div>

        <div className="lista-rolagem">
          {erro ? (
            <div className="estado">
              <p>{erro}</p>
              <button type="button" className="botao" onClick={() => setTentativa((n) => n + 1)}>
                Tentar de novo
              </button>
            </div>
          ) : !carregando && visiveis.length === 0 ? (
            <div className="estado">
              <p>Nenhuma unidade encontrada com esses filtros.</p>
              {temFiltro && (
                <button type="button" className="botao" onClick={() => { setFiltros(FILTROS_INICIAIS); setBusca('') }}>
                  Limpar filtros
                </button>
              )}
            </div>
          ) : (
            <ListaUnidades unidades={visiveis} selecionada={selecionada} aoSelecionar={aoSelecionar} />
          )}
        </div>
        </div>
      </aside>
    </div>
  )
}
