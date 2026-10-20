-- Estrutura do schema unifit (gerado por exportar_schema.py; não editar à mão)
CREATE SCHEMA IF NOT EXISTS "unifit";

CREATE TYPE "unifit".perfil_usuario AS ENUM ('admin', 'instrutor', 'aluno', 'recepcao');
CREATE TYPE "unifit".status_matricula AS ENUM ('ativa', 'trancada', 'cancelada', 'encerrada');
CREATE TYPE "unifit".status_pagamento AS ENUM ('pendente', 'pago', 'atrasado', 'cancelado');

CREATE SEQUENCE IF NOT EXISTS "unifit".alunos_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".api_keys_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".alunos_numero_matricula_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".checkins_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".exercicios_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".matriculas_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".pagamentos_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".planos_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".previsoes_evasao_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".sessoes_postura_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".treino_itens_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".treino_sessao_itens_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".treino_sessoes_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".treinos_id_seq;
CREATE SEQUENCE IF NOT EXISTS "unifit".usuarios_id_seq;

CREATE TABLE "unifit".alunos (
    id bigint DEFAULT nextval('"unifit".alunos_id_seq'::regclass) NOT NULL,
    usuario_id bigint,
    nome character varying(120) NOT NULL,
    cpf character(11),
    data_nascimento date,
    sexo character(1),
    telefone character varying(20),
    email character varying(150),
    altura_cm numeric(5,2),
    peso_kg numeric(5,2),
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    numero_matricula character varying(12) DEFAULT (to_char(now(), 'YYYY'::text) || lpad((nextval('"unifit".alunos_numero_matricula_seq'::regclass))::text, 6, '0'::text)) NOT NULL,
    CONSTRAINT alunos_cpf_key UNIQUE (cpf),
    CONSTRAINT alunos_numero_matricula_key UNIQUE (numero_matricula),
    CONSTRAINT alunos_usuario_id_key UNIQUE (usuario_id),
    CONSTRAINT alunos_pkey PRIMARY KEY (id),
    CONSTRAINT alunos_sexo_check CHECK ((sexo = ANY (ARRAY['M'::bpchar, 'F'::bpchar, 'O'::bpchar])))
);

CREATE TABLE "unifit".api_keys (
    id bigint DEFAULT nextval('"unifit".api_keys_id_seq'::regclass) NOT NULL,
    usuario_id bigint NOT NULL,
    nome character varying(80) NOT NULL,
    prefixo character varying(16) NOT NULL,
    token_hash character(64) NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    expira_em timestamp with time zone,
    ultimo_uso_em timestamp with time zone,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT api_keys_pkey PRIMARY KEY (id),
    CONSTRAINT api_keys_token_hash_key UNIQUE (token_hash)
);

CREATE TABLE "unifit".checkins (
    id bigint DEFAULT nextval('"unifit".checkins_id_seq'::regclass) NOT NULL,
    aluno_id bigint NOT NULL,
    data_hora timestamp with time zone DEFAULT now() NOT NULL,
    data_saida timestamp with time zone,
    CONSTRAINT checkins_pkey PRIMARY KEY (id)
);

CREATE TABLE "unifit".exercicios (
    id bigint DEFAULT nextval('"unifit".exercicios_id_seq'::regclass) NOT NULL,
    nome character varying(120) NOT NULL,
    grupo_muscular character varying(60),
    descricao text,
    CONSTRAINT exercicios_nome_key UNIQUE (nome),
    CONSTRAINT exercicios_pkey PRIMARY KEY (id)
);

CREATE TABLE "unifit".matriculas (
    id bigint DEFAULT nextval('"unifit".matriculas_id_seq'::regclass) NOT NULL,
    aluno_id bigint NOT NULL,
    plano_id bigint NOT NULL,
    data_inicio date NOT NULL,
    data_fim date,
    status "unifit".status_matricula DEFAULT 'ativa'::"unifit".status_matricula NOT NULL,
    CONSTRAINT matriculas_pkey PRIMARY KEY (id),
    CONSTRAINT matriculas_check CHECK (((data_fim IS NULL) OR (data_fim >= data_inicio)))
);

CREATE TABLE "unifit".pagamentos (
    id bigint DEFAULT nextval('"unifit".pagamentos_id_seq'::regclass) NOT NULL,
    matricula_id bigint NOT NULL,
    valor numeric(10,2) NOT NULL,
    data_vencimento date NOT NULL,
    data_pagamento date,
    status "unifit".status_pagamento DEFAULT 'pendente'::"unifit".status_pagamento NOT NULL,
    forma_pagamento character varying(30),
    CONSTRAINT pagamentos_pkey PRIMARY KEY (id),
    CONSTRAINT pagamentos_valor_check CHECK ((valor >= (0)::numeric))
);

CREATE TABLE "unifit".planos (
    id bigint DEFAULT nextval('"unifit".planos_id_seq'::regclass) NOT NULL,
    nome character varying(80) NOT NULL,
    valor numeric(10,2) NOT NULL,
    duracao_dias integer NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    CONSTRAINT planos_nome_key UNIQUE (nome),
    CONSTRAINT planos_pkey PRIMARY KEY (id),
    CONSTRAINT planos_duracao_dias_check CHECK ((duracao_dias > 0)),
    CONSTRAINT planos_valor_check CHECK ((valor >= (0)::numeric))
);

CREATE TABLE "unifit".previsoes_evasao (
    id bigint DEFAULT nextval('"unifit".previsoes_evasao_id_seq'::regclass) NOT NULL,
    aluno_id bigint NOT NULL,
    data_previsao date NOT NULL,
    probabilidade numeric(5,4) NOT NULL,
    modelo_versao character varying(40),
    CONSTRAINT previsoes_evasao_aluno_id_data_previsao_key UNIQUE (aluno_id, data_previsao),
    CONSTRAINT previsoes_evasao_pkey PRIMARY KEY (id),
    CONSTRAINT previsoes_evasao_probabilidade_check CHECK (((probabilidade >= (0)::numeric) AND (probabilidade <= (1)::numeric)))
);

CREATE TABLE "unifit".sessoes_postura (
    id bigint DEFAULT nextval('"unifit".sessoes_postura_id_seq'::regclass) NOT NULL,
    aluno_id bigint NOT NULL,
    exercicio_id bigint,
    video_nome character varying(255),
    fps_original numeric(6,2),
    fps_processado numeric(6,2),
    duracao_seg numeric(8,2),
    resultado jsonb,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sessoes_postura_pkey PRIMARY KEY (id)
);

CREATE TABLE "unifit".treino_itens (
    id bigint DEFAULT nextval('"unifit".treino_itens_id_seq'::regclass) NOT NULL,
    treino_id bigint NOT NULL,
    exercicio_id bigint NOT NULL,
    ordem smallint DEFAULT 1 NOT NULL,
    series smallint NOT NULL,
    repeticoes smallint NOT NULL,
    carga_kg numeric(6,2),
    descanso_seg smallint,
    CONSTRAINT treino_itens_pkey PRIMARY KEY (id),
    CONSTRAINT treino_itens_repeticoes_check CHECK ((repeticoes > 0)),
    CONSTRAINT treino_itens_series_check CHECK ((series > 0))
);

CREATE TABLE "unifit".treino_sessoes (
    id bigint DEFAULT nextval('"unifit".treino_sessoes_id_seq'::regclass) NOT NULL,
    treino_id bigint NOT NULL,
    aluno_id bigint NOT NULL,
    data_hora timestamp with time zone DEFAULT now() NOT NULL,
    observacao text,
    registrado_por bigint,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT treino_sessoes_pkey PRIMARY KEY (id)
);

CREATE TABLE "unifit".treino_sessao_itens (
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

CREATE TABLE "unifit".treinos (
    id bigint DEFAULT nextval('"unifit".treinos_id_seq'::regclass) NOT NULL,
    aluno_id bigint NOT NULL,
    instrutor_id bigint,
    nome character varying(80) NOT NULL,
    objetivo character varying(120),
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    CONSTRAINT treinos_pkey PRIMARY KEY (id)
);

CREATE TABLE "unifit".usuarios (
    id bigint DEFAULT nextval('"unifit".usuarios_id_seq'::regclass) NOT NULL,
    nome character varying(120) NOT NULL,
    email character varying(150) NOT NULL,
    senha_hash character varying(255) NOT NULL,
    perfil "unifit".perfil_usuario DEFAULT 'aluno'::"unifit".perfil_usuario NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT usuarios_email_key UNIQUE (email),
    CONSTRAINT usuarios_pkey PRIMARY KEY (id)
);

ALTER TABLE "unifit".alunos ADD CONSTRAINT alunos_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES "unifit".usuarios(id) ON DELETE SET NULL;
ALTER TABLE "unifit".api_keys ADD CONSTRAINT api_keys_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES "unifit".usuarios(id) ON DELETE CASCADE;
ALTER TABLE "unifit".checkins ADD CONSTRAINT checkins_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".matriculas ADD CONSTRAINT matriculas_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".matriculas ADD CONSTRAINT matriculas_plano_id_fkey FOREIGN KEY (plano_id) REFERENCES "unifit".planos(id);
ALTER TABLE "unifit".pagamentos ADD CONSTRAINT pagamentos_matricula_id_fkey FOREIGN KEY (matricula_id) REFERENCES "unifit".matriculas(id) ON DELETE CASCADE;
ALTER TABLE "unifit".previsoes_evasao ADD CONSTRAINT previsoes_evasao_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".sessoes_postura ADD CONSTRAINT sessoes_postura_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".sessoes_postura ADD CONSTRAINT sessoes_postura_exercicio_id_fkey FOREIGN KEY (exercicio_id) REFERENCES "unifit".exercicios(id);
ALTER TABLE "unifit".treino_itens ADD CONSTRAINT treino_itens_exercicio_id_fkey FOREIGN KEY (exercicio_id) REFERENCES "unifit".exercicios(id);
ALTER TABLE "unifit".treino_itens ADD CONSTRAINT treino_itens_treino_id_fkey FOREIGN KEY (treino_id) REFERENCES "unifit".treinos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".treino_sessoes ADD CONSTRAINT treino_sessoes_treino_id_fkey FOREIGN KEY (treino_id) REFERENCES "unifit".treinos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".treino_sessoes ADD CONSTRAINT treino_sessoes_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".treino_sessoes ADD CONSTRAINT treino_sessoes_registrado_por_fkey FOREIGN KEY (registrado_por) REFERENCES "unifit".usuarios(id) ON DELETE SET NULL;
ALTER TABLE "unifit".treino_sessao_itens ADD CONSTRAINT treino_sessao_itens_sessao_id_fkey FOREIGN KEY (sessao_id) REFERENCES "unifit".treino_sessoes(id) ON DELETE CASCADE;
ALTER TABLE "unifit".treino_sessao_itens ADD CONSTRAINT treino_sessao_itens_exercicio_id_fkey FOREIGN KEY (exercicio_id) REFERENCES "unifit".exercicios(id);
ALTER TABLE "unifit".treinos ADD CONSTRAINT treinos_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES "unifit".alunos(id) ON DELETE CASCADE;
ALTER TABLE "unifit".treinos ADD CONSTRAINT treinos_instrutor_id_fkey FOREIGN KEY (instrutor_id) REFERENCES "unifit".usuarios(id) ON DELETE SET NULL;
