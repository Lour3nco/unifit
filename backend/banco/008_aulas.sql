-- Aulas & Agenda: grade semanal recorrente + reservas/presença dos alunos. Idempotente.

-- Definição da aula (recorrente): dia da semana + horário fixo.
-- dia_semana: 0=Segunda ... 6=Domingo.
CREATE SEQUENCE IF NOT EXISTS "unifit".aulas_id_seq;
CREATE TABLE IF NOT EXISTS "unifit".aulas (
    id bigint DEFAULT nextval('"unifit".aulas_id_seq'::regclass) NOT NULL,
    nome character varying(80) NOT NULL,
    instrutor_id bigint,
    dia_semana smallint NOT NULL,
    hora_inicio time NOT NULL,
    hora_fim time NOT NULL,
    capacidade smallint NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT aulas_pkey PRIMARY KEY (id),
    CONSTRAINT aulas_dia_check CHECK (dia_semana BETWEEN 0 AND 6),
    CONSTRAINT aulas_cap_check CHECK (capacidade > 0),
    CONSTRAINT aulas_hora_check CHECK (hora_fim > hora_inicio)
);

-- Reserva de um aluno para uma ocorrência (aula + data). presente = compareceu (check-in).
CREATE SEQUENCE IF NOT EXISTS "unifit".aula_reservas_id_seq;
CREATE TABLE IF NOT EXISTS "unifit".aula_reservas (
    id bigint DEFAULT nextval('"unifit".aula_reservas_id_seq'::regclass) NOT NULL,
    aula_id bigint NOT NULL,
    aluno_id bigint NOT NULL,
    data date NOT NULL,
    presente boolean DEFAULT false NOT NULL,
    presenca_em timestamp with time zone,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT aula_reservas_pkey PRIMARY KEY (id),
    CONSTRAINT aula_reservas_unica UNIQUE (aula_id, aluno_id, data)
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'aulas_instrutor_id_fkey') THEN
        ALTER TABLE "unifit".aulas ADD CONSTRAINT aulas_instrutor_id_fkey
            FOREIGN KEY (instrutor_id) REFERENCES "unifit".usuarios(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'aula_reservas_aula_id_fkey') THEN
        ALTER TABLE "unifit".aula_reservas ADD CONSTRAINT aula_reservas_aula_id_fkey
            FOREIGN KEY (aula_id) REFERENCES "unifit".aulas(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'aula_reservas_aluno_id_fkey') THEN
        ALTER TABLE "unifit".aula_reservas ADD CONSTRAINT aula_reservas_aluno_id_fkey
            FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS aula_reservas_ocorrencia_idx ON "unifit".aula_reservas (aula_id, data);
CREATE INDEX IF NOT EXISTS aula_reservas_aluno_idx ON "unifit".aula_reservas (aluno_id, data DESC);
