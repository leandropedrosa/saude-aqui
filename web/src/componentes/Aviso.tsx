import type { Status } from '../api'
import { formatarCompetencia, formatarData } from '../util'

/**
 * Aviso fixo sobre a origem e os limites dos dados, com a data da última
 * atualização. Fica sempre visível no topo do painel.
 */
export function Aviso({ status }: { status: Status | null }) {
  return (
    <div className="aviso" role="note">
      <p>
        Mostramos os profissionais <strong>vinculados</strong> a cada unidade no cadastro
        oficial (CNES), não quem está de plantão hoje.{' '}
        <strong>Confirme por telefone antes de ir.</strong>
      </p>
      {status?.competencia && (
        <p className="aviso-data">
          Dados de {formatarCompetencia(status.competencia)}
          {status.ultima_atualizacao && <> · atualizado em {formatarData(status.ultima_atualizacao)}</>}
        </p>
      )}
    </div>
  )
}
