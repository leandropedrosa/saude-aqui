// =====================================================================
// Mapa com Leaflet + OpenStreetMap (gratuito, sem chave de API).
//
// O <MapContainer> é montado UMA vez só, ao abrir o site. Trocar
// filtros só atualiza os marcadores, sem recriar o mapa.
//
// Regras do OpenStreetMap: manter a atribuição visível (o Leaflet já faz)
// e uso leve dos servidores de tiles. Se o tráfego crescer, troque
// VITE_TILES_URL por um provedor com plano gratuito (MapTiler, Stadia, Carto).
// =====================================================================

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo } from 'react'
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip, ZoomControl, useMap } from 'react-leaflet'
import type { Posicao, Unidade } from '../api'
import { formatarTitulo } from '../util'

const TILES_URL = import.meta.env.VITE_TILES_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILES_ATRIBUICAO = import.meta.env.VITE_TILES_ATRIBUICAO ||
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

// Centro aproximado de Cidade Ocidental (GO)
const CENTRO_INICIAL: [number, number] = [-16.085, -47.935]

// Largura do painel lateral no desktop (igual ao CSS), para não esconder marcadores atrás dele
const LARGURA_PAINEL = 440
const ehDesktop = () => window.matchMedia('(min-width: 768px)').matches

/** Ícone do marcador: um "pino" em SVG; o selecionado é maior e de outra cor. */
function criarIcone(selecionado: boolean, hospital: boolean) {
  const tamanho = selecionado ? 44 : 34
  const simbolo = hospital
    ? '<path fill="#fff" d="M9 7h2v3h2V7h2v8h-2v-3h-2v3H9z"/>'
    : '<path fill="#fff" d="M11 6.5h2v3h3v2h-3v3h-2v-3H8v-2h3z"/>'
  return L.divIcon({
    className: `marcador${selecionado ? ' marcador-selecionado' : ''}`,
    html: `<svg viewBox="0 0 24 30" width="${tamanho}" height="${tamanho * 1.25}" aria-hidden="true">
             <path d="M12 0C5.4 0 0 5.2 0 11.7 0 20.4 12 30 12 30s12-9.6 12-18.3C24 5.2 18.6 0 12 0z"/>
             ${simbolo}
           </svg>`,
    iconSize: [tamanho, tamanho * 1.25],
    iconAnchor: [tamanho / 2, tamanho * 1.25], // a ponta do pino fica na coordenada
    tooltipAnchor: [0, -tamanho * 1.15],
  })
}

/** Leva o ponto ao centro da área visível (descontando o painel no desktop). */
function voarPara(mapa: L.Map, lat: number, lng: number, zoom: number) {
  if (!ehDesktop()) {
    mapa.flyTo([lat, lng], zoom, { duration: 0.6 })
    return
  }
  // Desloca o centro para a esquerda, pois o painel cobre o lado esquerdo do mapa
  const ponto = mapa.project([lat, lng], zoom).subtract([LARGURA_PAINEL / 2, 0])
  mapa.flyTo(mapa.unproject(ponto, zoom), zoom, { duration: 0.6 })
}

interface Props {
  unidades: Unidade[]
  selecionada: number | null
  aoSelecionar: (id: number) => void
  posicao: Posicao | null
}

/** Componente interno com acesso ao objeto do mapa (useMap) para mover a câmera. */
function ControleCamera({ unidades, selecionada, posicao }: Omit<Props, 'aoSelecionar'>) {
  const mapa = useMap()

  // Quando a lista muda (filtros/posição), enquadra todos os marcadores
  const chaveLista = unidades.map((u) => u.id).join(',')
  useEffect(() => {
    const pontos: [number, number][] = unidades
      .filter((u) => u.lat !== null && u.lng !== null)
      .map((u) => [u.lat!, u.lng!])
    if (posicao) pontos.push([posicao.lat, posicao.lng])
    if (pontos.length === 0) return
    mapa.fitBounds(pontos, {
      maxZoom: 16,
      paddingTopLeft: ehDesktop() ? [LARGURA_PAINEL + 20, 40] : [30, 50],
      paddingBottomRight: [40, 40],
    })
  }, [chaveLista, posicao, mapa])

  // Quando uma unidade é selecionada (na lista ou no mapa), centraliza nela
  useEffect(() => {
    const u = unidades.find((x) => x.id === selecionada)
    if (u?.lat != null && u.lng != null) voarPara(mapa, u.lat, u.lng, Math.max(mapa.getZoom(), 15))
  }, [selecionada, mapa])

  return null
}

export function Mapa({ unidades, selecionada, aoSelecionar, posicao }: Props) {
  // Os ícones são criados uma vez só (4 combinações possíveis)
  const icones = useMemo(() => ({
    normal: criarIcone(false, false),
    normalHospital: criarIcone(false, true),
    selecionado: criarIcone(true, false),
    selecionadoHospital: criarIcone(true, true),
  }), [])

  return (
    <MapContainer
      center={CENTRO_INICIAL}
      zoom={13}
      className="mapa"
      zoomControl={false}
      aria-label="Mapa das unidades de saúde"
    >
      <TileLayer url={TILES_URL} attribution={TILES_ATRIBUICAO} maxZoom={19} />
      <ZoomControl position="bottomright" />
      <ControleCamera unidades={unidades} selecionada={selecionada} posicao={posicao} />

      {unidades.filter((u) => u.lat !== null && u.lng !== null).map((u) => {
        const ativo = u.id === selecionada
        const hospital = !!u.tipo?.toLowerCase().includes('hospital')
        const icone = ativo
          ? (hospital ? icones.selecionadoHospital : icones.selecionado)
          : (hospital ? icones.normalHospital : icones.normal)
        return (
          <Marker
            key={u.id}
            position={[u.lat!, u.lng!]}
            icon={icone}
            zIndexOffset={ativo ? 1000 : 0}
            title={formatarTitulo(u.nome)}
            alt={formatarTitulo(u.nome)}
            eventHandlers={{ click: () => aoSelecionar(u.id) }}
          >
            {ativo && (
              <Tooltip permanent direction="top" className="rotulo-marcador">
                {formatarTitulo(u.nome)}
              </Tooltip>
            )}
          </Marker>
        )
      })}

      {posicao && (
        <CircleMarker
          center={[posicao.lat, posicao.lng]}
          radius={9}
          pathOptions={{ color: '#fff', weight: 3, fillColor: '#1a73e8', fillOpacity: 1 }}
        >
          <Tooltip>Você está aqui</Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  )
}
