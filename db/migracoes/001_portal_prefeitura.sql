-- Migração para bancos criados antes da integração com o portal da Prefeitura.
-- (Bancos novos já recebem tudo pelo db/init.sql.)
--   docker compose exec -T db psql -U saude_aqui -d saude_aqui < db/migracoes/001_portal_prefeitura.sql

ALTER TABLE coleta  ADD COLUMN IF NOT EXISTS avisos TEXT;
ALTER TABLE unidade ADD COLUMN IF NOT EXISTS horario_portal TEXT;

CREATE TABLE IF NOT EXISTS arquivo_portal (
    midia             TEXT PRIMARY KEY,
    portal_unidade_id TEXT,
    unidade_nome      TEXT,
    data_inicio       DATE,
    data_fim          DATE,
    titulo            TEXT,
    tipo              TEXT NOT NULL
        CHECK (tipo IN ('listagem_cnes', 'possivel_escala', 'erro')),
    verificado_em     TIMESTAMPTZ NOT NULL DEFAULT now()
);
