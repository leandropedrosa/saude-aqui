-- =====================================================================
-- Saúde Aqui: schema do banco de dados
--
-- Este arquivo roda UMA VEZ, quando o volume do Postgres está vazio
-- (é o mecanismo /docker-entrypoint-initdb.d da imagem oficial).
-- Os dados são preenchidos pelo coletor, a partir do CNES/DATASUS.
--
-- Modelo:
--   unidade   - estabelecimentos públicos de saúde do município
--   ocupacao  - tabela CBO (lida de db/ocupacoes.csv): diz quais
--               ocupações aparecem no site (coluna "atendimento")
--   vinculo   - profissional X unidade X ocupação em uma competência
--               (mês de referência do CNES)
--   coleta    - registro de cada execução do coletor
--
-- PRIVACIDADE: nunca gravamos CNS (Cartão SUS), CPF ou número de
-- registro em conselho. Só nome, ocupação e carga horária.
-- =====================================================================

SET TIME ZONE 'America/Sao_Paulo';

-- ---------------------------------------------------------------------
-- Execuções do coletor (uma linha por execução, com sucesso ou erro)
-- ---------------------------------------------------------------------
CREATE TABLE coleta (
    id                   SERIAL PRIMARY KEY,
    fonte                TEXT        NOT NULL,          -- ex.: 'CNES/DATASUS PF'
    competencia          DATE,                          -- 1º dia do mês de referência
    url_origem           TEXT,
    hash_sha256          CHAR(64),                      -- hash do arquivo baixado
    baixado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    status               TEXT        NOT NULL
        CHECK (status IN ('em_andamento', 'sucesso', 'sem_novidade', 'erro')),
    erro                 TEXT,
    avisos               TEXT,                          -- ex.: escala nova publicada no portal
    registros_importados INTEGER     NOT NULL DEFAULT 0
);

-- O coletor consulta "esse arquivo já foi processado com sucesso?"
CREATE INDEX idx_coleta_hash ON coleta (hash_sha256) WHERE status = 'sucesso';

-- ---------------------------------------------------------------------
-- Unidades de saúde
-- Dados vêm da API de dados abertos do CNES. As colunas podem ser
-- corrigidas manualmente em db/unidades.csv (o coletor aplica os ajustes).
-- ---------------------------------------------------------------------
CREATE TABLE unidade (
    id              SERIAL PRIMARY KEY,
    cnes            CHAR(7)     NOT NULL UNIQUE,        -- código CNES (7 dígitos)
    nome            TEXT        NOT NULL,
    tipo            TEXT,                               -- ex.: 'Unidade Básica de Saúde'
    endereco        TEXT,
    bairro          TEXT,
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION,
    telefone        TEXT,
    turno_codigo    CHAR(2),                            -- código do CNES (02, 03, 04, 06...)
    turno_descricao TEXT,                               -- texto oficial do CNES
    horario         TEXT,                               -- manual (unidades.csv); tem prioridade
    horario_portal  TEXT,                               -- texto do portal da Prefeitura (2026+)
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,  -- FALSE = não aparece no site
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_unidade_bairro ON unidade (bairro);

-- ---------------------------------------------------------------------
-- Ocupações (CBO 2002). Sincronizada a partir de db/ocupacoes.csv.
-- Para esconder uma ocupação do site, mude "incluir" para "nao" no CSV
-- e rode o coletor com --forcar. Não apague linhas.
-- ---------------------------------------------------------------------
CREATE TABLE ocupacao (
    cbo         CHAR(6) PRIMARY KEY,
    nome        TEXT    NOT NULL,        -- ex.: 'Médico pediatra' (funciona como especialidade)
    categoria   TEXT    NOT NULL,        -- ex.: 'Medicina', 'Enfermagem', 'Odontologia'
    atendimento BOOLEAN NOT NULL         -- TRUE = aparece no site
);

-- ---------------------------------------------------------------------
-- Vínculos: "fulano atende na unidade X como ocupação Y, N horas/semana"
--
-- Não existe tabela "profissional" porque, sem CNS/CPF (que não
-- guardamos de propósito), não há um identificador confiável da pessoa.
-- O nome é guardado diretamente no vínculo.
-- ---------------------------------------------------------------------
CREATE TABLE vinculo (
    id                    SERIAL PRIMARY KEY,
    unidade_id            INTEGER  NOT NULL REFERENCES unidade (id),
    profissional          TEXT     NOT NULL,             -- nome como está no CNES
    cbo                   CHAR(6)  NOT NULL REFERENCES ocupacao (cbo),
    carga_horaria_semanal SMALLINT NOT NULL DEFAULT 0,   -- soma ambulatorial + hospitalar + outras
    competencia           DATE     NOT NULL,             -- 1º dia do mês de referência do CNES
    fonte                 TEXT     NOT NULL DEFAULT 'CNES/DATASUS',
    coleta_id             INTEGER  REFERENCES coleta (id),

    -- Reprocessar o mesmo arquivo não duplica registros (o coletor faz upsert)
    CONSTRAINT uq_vinculo UNIQUE (competencia, unidade_id, profissional, cbo)
);

CREATE INDEX idx_vinculo_competencia ON vinculo (competencia);
CREATE INDEX idx_vinculo_unidade     ON vinculo (unidade_id, competencia);
CREATE INDEX idx_vinculo_cbo         ON vinculo (cbo);

-- ---------------------------------------------------------------------
-- Arquivos publicados no portal de escalas da Prefeitura (2026 em diante).
-- Cada arquivo é verificado UMA vez: se não for a "Listagem de Profissionais"
-- do CNES, é marcado como possível escala e gera um aviso na coleta.
-- ---------------------------------------------------------------------
CREATE TABLE arquivo_portal (
    midia             TEXT PRIMARY KEY,                 -- nome do arquivo no portal
    portal_unidade_id TEXT,
    unidade_nome      TEXT,
    data_inicio       DATE,
    data_fim          DATE,
    titulo            TEXT,
    tipo              TEXT NOT NULL
        CHECK (tipo IN ('listagem_cnes', 'possivel_escala', 'erro')),
    verificado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Distância em km entre dois pontos (fórmula de Haversine).
-- Usamos isso no lugar de PostGIS: para ~50 unidades é mais que suficiente.
-- ---------------------------------------------------------------------
CREATE FUNCTION distancia_km(lat1 DOUBLE PRECISION, lng1 DOUBLE PRECISION,
                             lat2 DOUBLE PRECISION, lng2 DOUBLE PRECISION)
RETURNS DOUBLE PRECISION
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
    SELECT 2 * 6371 * asin(sqrt(
        -- LEAST evita erro de arredondamento (valor 1.0000000001 em asin)
        LEAST(1.0,
            sin(radians(lat2 - lat1) / 2) ^ 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lng2 - lng1) / 2) ^ 2
        )
    ));
$$;

COMMENT ON FUNCTION distancia_km IS 'Distância em km pela fórmula de Haversine (raio da Terra = 6371 km)';
