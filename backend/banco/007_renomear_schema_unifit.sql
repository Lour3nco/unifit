-- Renomeia o schema do banco de "gymIA" para "unifit" (rebranding do sistema para UniFit).
-- Atômico: tabelas, sequências e tipos vão junto. Idempotente: se já foi renomeado, não faz nada.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'gymIA') THEN
        ALTER SCHEMA "gymIA" RENAME TO unifit;
    END IF;
END $$;
