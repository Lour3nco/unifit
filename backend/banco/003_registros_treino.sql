-- Registros de execução de treino (evolução do aluno): o que ele fez e quanto fez em cada sessão.
-- Idempotente: pode rodar de novo no Supabase.

-- Uma sessão = um dia em que o aluno executou uma ficha de treino.
CREATE SEQUENCE IF NOT EXISTS "unifit".treino_sessoes_id_seq;
CREATE TABLE IF NOT EXISTS "unifit".treino_sessoes (
    id bigint DEFAULT nextval('"unifit".treino_sessoes_id_seq'::regclass) NOT NULL,
    treino_id bigint NOT NULL,
    aluno_id bigint NOT NULL,
    data_hora timestamp with time zone DEFAULT now() NOT NULL,
    observacao text,
    registrado_por bigint,  -- usuarios.id de quem lançou (aluno ou instrutor)
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT treino_sessoes_pkey PRIMARY KEY (id)
);

-- O que foi feito em cada exercício daquela sessão (séries/repetições/carga realizados).
CREATE SEQUENCE IF NOT EXISTS "unifit".treino_sessao_itens_id_seq;
CREATE TABLE IF NOT EXISTS "unifit".treino_sessao_itens (
    id bigint DEFAULT nextval('"unifit".treino_sessao_itens_id_seq'::regclass) NOT NULL,
    sessao_id bigint NOT NULL,
    exercicio_id bigint NOT NULL,
    ordem smallint DEFAULT 1 NOT NULL,
    series smallint,
    repeticoes smallint,
    carga_kg numeric(6,2),
    CONSTRAINT treino_sessao_itens_pkey PRIMARY KEY (id),
    CONSTRAINT treino_sessao_itens_series_check CHECK ((series IS NULL OR series >= 0)),
    CONSTRAINT treino_sessao_itens_repeticoes_check CHECK ((repeticoes IS NULL OR repeticoes >= 0))
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'treino_sessoes_treino_id_fkey') THEN
        ALTER TABLE "unifit".treino_sessoes ADD CONSTRAINT treino_sessoes_treino_id_fkey
            FOREIGN KEY (treino_id) REFERENCES "unifit".treinos(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'treino_sessoes_aluno_id_fkey') THEN
        ALTER TABLE "unifit".treino_sessoes ADD CONSTRAINT treino_sessoes_aluno_id_fkey
            FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'treino_sessoes_registrado_por_fkey') THEN
        ALTER TABLE "unifit".treino_sessoes ADD CONSTRAINT treino_sessoes_registrado_por_fkey
            FOREIGN KEY (registrado_por) REFERENCES "unifit".usuarios(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'treino_sessao_itens_sessao_id_fkey') THEN
        ALTER TABLE "unifit".treino_sessao_itens ADD CONSTRAINT treino_sessao_itens_sessao_id_fkey
            FOREIGN KEY (sessao_id) REFERENCES "unifit".treino_sessoes(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'treino_sessao_itens_exercicio_id_fkey') THEN
        ALTER TABLE "unifit".treino_sessao_itens ADD CONSTRAINT treino_sessao_itens_exercicio_id_fkey
            FOREIGN KEY (exercicio_id) REFERENCES "unifit".exercicios(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS treino_sessoes_aluno_idx ON "unifit".treino_sessoes (aluno_id, data_hora DESC);
CREATE INDEX IF NOT EXISTS treino_sessao_itens_sessao_idx ON "unifit".treino_sessao_itens (sessao_id);
