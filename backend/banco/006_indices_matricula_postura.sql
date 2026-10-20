-- 006: índices para as consultas mais usadas, uma matrícula ativa por aluno e status da análise de postura.
-- Pode rodar mais de uma vez (IF NOT EXISTS).

-- Índices: o Postgres não cria índice sozinho nas chaves estrangeiras.
CREATE INDEX IF NOT EXISTS checkins_aluno_data_idx ON "unifit".checkins (aluno_id, data_hora DESC);
CREATE INDEX IF NOT EXISTS checkins_data_idx ON "unifit".checkins (data_hora);
CREATE INDEX IF NOT EXISTS matriculas_aluno_idx ON "unifit".matriculas (aluno_id, data_inicio DESC);
CREATE INDEX IF NOT EXISTS pagamentos_matricula_idx ON "unifit".pagamentos (matricula_id);
CREATE INDEX IF NOT EXISTS pagamentos_status_venc_idx ON "unifit".pagamentos (status, data_vencimento);
CREATE INDEX IF NOT EXISTS previsoes_evasao_data_idx ON "unifit".previsoes_evasao (data_previsao);
CREATE INDEX IF NOT EXISTS sessoes_postura_aluno_idx ON "unifit".sessoes_postura (aluno_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS treinos_aluno_idx ON "unifit".treinos (aluno_id);

-- Uma matrícula "ativa" por aluno, garantida pelo banco (antes era só no código: dois cliques criavam duas).
-- Antes do índice, encerra as ativas repetidas, mantendo a mais recente de cada aluno.
UPDATE "unifit".matriculas m SET status = 'encerrada'
WHERE m.status = 'ativa' AND EXISTS (
    SELECT 1 FROM "unifit".matriculas n
    WHERE n.aluno_id = m.aluno_id AND n.status = 'ativa' AND (n.data_inicio, n.id) > (m.data_inicio, m.id));
CREATE UNIQUE INDEX IF NOT EXISTS matriculas_uma_ativa_por_aluno ON "unifit".matriculas (aluno_id) WHERE status = 'ativa';

-- Análise de postura em segundo plano: a linha nasce "processando" e vira "concluida" ou "erro".
ALTER TABLE "unifit".sessoes_postura ADD COLUMN IF NOT EXISTS status character varying(20) DEFAULT 'concluida' NOT NULL;
ALTER TABLE "unifit".sessoes_postura ADD COLUMN IF NOT EXISTS erro text;
