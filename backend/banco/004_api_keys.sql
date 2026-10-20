-- API keys: acesso programático à API (scripts/integrações) sem tela de login.
-- A chave pertence a um usuário e age com o perfil dele. Guardamos só o hash (SHA-256); a chave
-- completa só é mostrada uma vez, na criação. Idempotente.

CREATE SEQUENCE IF NOT EXISTS "unifit".api_keys_id_seq;
CREATE TABLE IF NOT EXISTS "unifit".api_keys (
    id bigint DEFAULT nextval('"unifit".api_keys_id_seq'::regclass) NOT NULL,
    usuario_id bigint NOT NULL,
    nome character varying(80) NOT NULL,
    prefixo character varying(16) NOT NULL,      -- início visível da chave, só para identificar na lista
    token_hash character(64) NOT NULL,           -- SHA-256 da chave completa
    ativo boolean DEFAULT true NOT NULL,
    expira_em timestamp with time zone,          -- opcional; null = não expira
    ultimo_uso_em timestamp with time zone,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT api_keys_pkey PRIMARY KEY (id),
    CONSTRAINT api_keys_token_hash_key UNIQUE (token_hash)
);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'api_keys_usuario_id_fkey') THEN
        ALTER TABLE "unifit".api_keys ADD CONSTRAINT api_keys_usuario_id_fkey
            FOREIGN KEY (usuario_id) REFERENCES "unifit".usuarios(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS api_keys_usuario_idx ON "unifit".api_keys (usuario_id);
