-- =====================================================================
-- DADOS FICTÍCIOS para testes e desenvolvimento do front-end.
-- Nomes de unidades e de profissionais são INVENTADOS.
-- As coordenadas ficam dentro de Cidade Ocidental, só para o mapa ter sentido.
--
-- Carregar no banco de desenvolvimento:
--   docker compose exec -T db psql -U saude_aqui -d saude_aqui < db/dados_ficticios.sql
--
-- Os testes da API (api/tests) dependem destes dados: ao mudar algo
-- aqui, rode os testes de novo.
-- =====================================================================

BEGIN;

INSERT INTO ocupacao (cbo, nome, categoria, atendimento) VALUES
    ('225125', 'Médico clínico',                             'Medicina',            TRUE),
    ('225124', 'Médico pediatra',                            'Medicina',            TRUE),
    ('225142', 'Médico da estratégia de saúde da família',   'Medicina',            TRUE),
    ('223505', 'Enfermeiro',                                 'Enfermagem',          TRUE),
    ('322205', 'Técnico de enfermagem',                      'Enfermagem',          TRUE),
    ('223293', 'Cirurgião-dentista da estratégia de saúde da família', 'Odontologia', TRUE),
    ('223710', 'Nutricionista',                              'Nutrição',            TRUE),
    ('515105', 'Agente comunitário de saúde',                'Agente comunitário',  FALSE)
ON CONFLICT (cbo) DO NOTHING;

INSERT INTO coleta (id, fonte, competencia, url_origem, hash_sha256, baixado_em, status, registros_importados) VALUES
    (1, 'FICTÍCIO', '2026-08-01', 'ficticio://PFGO2608', repeat('a', 64), '2026-10-05 06:15:00-03', 'sucesso', 4),
    (2, 'FICTÍCIO', '2026-09-01', 'ficticio://PFGO2609', repeat('b', 64), '2026-11-05 06:15:00-03', 'sucesso', 9),
    (3, 'FICTÍCIO', NULL,         'ficticio://PFGO2609', repeat('b', 64), '2026-11-10 06:15:00-03', 'sem_novidade', 0);
SELECT setval('coleta_id_seq', 3);

-- id 1..3: ativas com coordenadas | id 4: oculta (ativo = FALSE) | id 5: sem coordenadas
INSERT INTO unidade (id, cnes, nome, tipo, endereco, bairro, lat, lng, telefone,
                     turno_codigo, turno_descricao, horario, ativo) VALUES
    (1, '9000001', 'UBS FICTÍCIA CENTRO', 'Unidade Básica de Saúde', 'Quadra 10, Lote 1', 'CENTRO',
        -16.0920, -47.9260, '(61) 3600-0001', '03', 'ATENDIMENTOS NOS TURNOS DA MANHA E A TARDE', NULL, TRUE),
    (2, '9000002', 'UBS FICTÍCIA JARDIM ABC', 'Unidade Básica de Saúde', 'Rua 5, s/n', 'JARDIM ABC',
        -16.0640, -47.9560, NULL, '02', 'ATENDIMENTO SOMENTE A TARDE', 'Seg a sex, 13h às 19h', TRUE),
    (3, '9000003', 'HOSPITAL FICTÍCIO', 'Hospital', 'Área Especial 1', 'CENTRO',
        -16.0980, -47.9370, '(61) 3600-0003', '06', 'ATENDIMENTO CONTINUO DE 24 HORAS/DIA', NULL, TRUE),
    (4, '9000004', 'SETOR ADMINISTRATIVO FICTÍCIO', 'Central de Gestão', 'Quadra 1', 'PARQUE OCULTO',
        -16.0900, -47.9300, NULL, '03', NULL, NULL, FALSE),
    (5, '9000005', 'UBS FICTÍCIA SEM MAPA', 'Unidade Básica de Saúde', 'Zona rural', 'ZONA RURAL',
        NULL, NULL, NULL, '03', 'ATENDIMENTOS NOS TURNOS DA MANHA E A TARDE', NULL, TRUE);
SELECT setval('unidade_id_seq', 5);

-- Competência atual: setembro/2026
INSERT INTO vinculo (unidade_id, profissional, cbo, carga_horaria_semanal, competencia, coleta_id) VALUES
    (1, 'MARIA EXEMPLO DA SILVA',     '225142', 40, '2026-09-01', 2),
    (1, 'JOAO FICTICIO DOS SANTOS',   '223505', 40, '2026-09-01', 2),
    (1, 'ANA TESTE DE OLIVEIRA',      '223293', 40, '2026-09-01', 2),
    (1, 'PEDRO AGENTE COMUNITARIO',   '515105', 40, '2026-09-01', 2),  -- não deve aparecer (atendimento = FALSE)
    (2, 'CARLA EXEMPLO PEREIRA',      '225125', 20, '2026-09-01', 2),
    (3, 'LUCAS FICTICIO PEDIATRA',    '225124', 24, '2026-09-01', 2),
    (3, 'BEATRIZ EXEMPLO E SOUZA',    '322205', 36, '2026-09-01', 2),
    (4, 'OCULTO DA UNIDADE INATIVA',  '225125', 40, '2026-09-01', 2),  -- unidade oculta
    (5, 'RITA SEM MAPA',              '223505', 40, '2026-09-01', 2);

-- Competência antiga: agosto/2026 (não deve aparecer em nenhuma consulta)
INSERT INTO vinculo (unidade_id, profissional, cbo, carga_horaria_semanal, competencia, coleta_id) VALUES
    (1, 'MARIA EXEMPLO DA SILVA',     '225142', 40, '2026-08-01', 1),
    (2, 'ANTIGO NUTRICIONISTA',       '223710', 20, '2026-08-01', 1);

COMMIT;
