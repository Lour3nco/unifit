-- data_saida foi criada sem fuso; data_hora (a entrada) tem fuso. Iguala as duas.
-- Os valores antigos foram gravados em UTC (fuso da sessão do Supabase), por isso o AT TIME ZONE 'UTC'.
DO $$ BEGIN
    IF (SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'unifit' AND table_name = 'checkins' AND column_name = 'data_saida') = 'timestamp without time zone' THEN
        ALTER TABLE "unifit".checkins ALTER COLUMN data_saida TYPE timestamptz USING data_saida AT TIME ZONE 'UTC';
    END IF;
END $$;
