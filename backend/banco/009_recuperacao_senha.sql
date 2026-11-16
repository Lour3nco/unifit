-- "Esqueci a senha": links de troca de senha enviados por e-mail ou SMS. Idempotente.
-- Guarda só o hash (SHA-256) do token: quem lê o banco não consegue usar os links.
-- Cada link vale por pouco tempo (expira_em) e uma única vez (usado_em).
CREATE SEQUENCE IF NOT EXISTS "unifit".senha_tokens_id_seq;
CREATE TABLE IF NOT EXISTS "unifit".senha_tokens (
    id bigint DEFAULT nextval('"unifit".senha_tokens_id_seq'::regclass) NOT NULL,
    usuario_id bigint NOT NULL,
    token_hash character(64) NOT NULL,
    canal character varying(10) NOT NULL,
    expira_em timestamp with time zone NOT NULL,
    usado_em timestamp with time zone,
    criado_em timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT senha_tokens_pkey PRIMARY KEY (id),
    CONSTRAINT senha_tokens_hash_key UNIQUE (token_hash),
    CONSTRAINT senha_tokens_canal_check CHECK (canal IN ('email', 'sms')),
    CONSTRAINT senha_tokens_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES "unifit".usuarios(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS senha_tokens_usuario_idx ON "unifit".senha_tokens (usuario_id);
